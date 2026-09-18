# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Sphinx extension to generate markdown files alongside HTML files.

This extension hooks into the Sphinx build process to create markdown versions
of all documents using the sphinx_markdown_builder.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from contextlib import nullcontext
from dataclasses import dataclass
from enum import Enum
from importlib.metadata import PackageNotFoundError, metadata
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import docutils.nodes
from sphinx.application import Sphinx
from sphinx.errors import ExtensionError
from sphinx.util import logging
from sphinx.util.matching import patmatch
from sphinx.util.osutil import relative_uri

from .extract_prose import extract_prose
from .markdown_builder import (
    LINK_TARGETS_FILENAME,
    LINK_TOKEN_PREFIX,
    SUPPRESS_UNKNOWN_NODE_WARNINGS_CONFIG,
    LinkTarget,
    SphinxLlmMarkdownBuilder,
    validate_suppress_unknown_node_warnings,
)
from .summary import DEFAULT_API_KEY_ENV
from .version import __version__

logger = logging.getLogger(__name__)
LINK_TOKEN_PATTERN = re.compile(rf"{re.escape(LINK_TOKEN_PREFIX)}[0-9a-f]{{32}}")
UNKNOWN_NODE_WARNING_PATTERN = re.compile(
    r"^(?:(?P<source>.+?):(?:(?P<line>[0-9]+):|:)\s+)?WARNING:\s+"
    r"(?P<message>unknown node type: .+)$"
)
SUMMARY_CACHE_VERSION = 1
SITEMAP_TEXT_TRANSLATION = str.maketrans(
    {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\\": "&#92;",
        "[": "&#91;",
        "]": "&#93;",
        "`": "&#96;",
        "*": "&#42;",
        "_": "&#95;",
    }
)


def _serialize_sitemap_text(value: str) -> str:
    """Return one-line text that is safe inside a generated file-list entry."""
    value = re.sub(r"[^\S\r\n]*(?:\r\n?|\n)+[^\S\r\n]*", " ", value).strip()
    escaped = []
    for index, character in enumerate(value):
        if (
            character == "_"
            and index > 0
            and index + 1 < len(value)
            and value[index - 1].isalnum()
            and value[index + 1].isalnum()
        ):
            escaped.append(character)
        else:
            escaped.append(character.translate(SITEMAP_TEXT_TRANSLATION))
    return "".join(escaped)


def _serialize_sitemap_destination(value: str) -> str:
    """Quote a generated URI without changing its existing URI structure."""
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", value) or value.startswith("//"):
        parsed = urlsplit(value)
        return urlunsplit(
            (
                parsed.scheme,
                quote(parsed.netloc, safe="!$&'*+,-.:;=@[]%"),
                quote(parsed.path, safe="/%"),
                quote(parsed.query, safe="!$&'*+,-./:;=?@_~%"),
                quote(parsed.fragment, safe="!$&'*+,-./:;=?@_~%"),
            )
        )

    path_and_query, fragment_separator, fragment = value.partition("#")
    path, query_separator, query = path_and_query.partition("?")
    destination = quote(path, safe="/%")
    if query_separator:
        destination += "?" + quote(query, safe="!$&'*+,-./:;=?@_~%")
    if fragment_separator:
        destination += "#" + quote(fragment, safe="!$&'*+,-./:;=?@_~%")
    return destination


def _serialize_sitemap_entry(
    label: str, destination: str, description: str | None = None
) -> str:
    """Serialize one generated llms.txt file-list entry."""
    entry = (
        f"- [{_serialize_sitemap_text(label)}]"
        f"({_serialize_sitemap_destination(destination)})"
    )
    if description is not None:
        entry += f": {_serialize_sitemap_text(extract_prose(description))}"
    return entry


def _published_html_path(app: Sphinx, docname: str) -> PurePosixPath:
    """Return a document's canonical HTML output path below the build root."""
    outdir = Path(app.builder.outdir).resolve()
    output_path = Path(app.builder.get_outfilename(docname)).resolve()
    try:
        relative_path = output_path.relative_to(outdir)
    except ValueError as exc:
        raise ExtensionError(
            f"HTML output path for document {docname!r} escapes the build directory"
        ) from exc
    return PurePosixPath(relative_path.as_posix())


def _nested_index_paths(app: Sphinx, docnames: Iterable[str]) -> set[PurePosixPath]:
    """Return all generated indexes implied by published document paths."""
    indexes = {PurePosixPath("llms.txt")}
    for docname in docnames:
        output_directory = _published_html_path(app, docname).parent
        for directory in (output_directory, *output_directory.parents):
            if directory == PurePosixPath("."):
                break
            indexes.add(directory / "llms.txt")
    return indexes


def _most_specific_index_path(
    page_output_path: PurePosixPath,
    index_paths: Iterable[PurePosixPath],
) -> PurePosixPath:
    """Select the deepest generated index whose directory contains a page."""
    if page_output_path.is_absolute() or ".." in page_output_path.parts:
        raise ExtensionError("HTML output path must be relative to the build directory")

    page_directory = page_output_path.parent
    candidates = []
    for index_path in index_paths:
        if (
            index_path.is_absolute()
            or ".." in index_path.parts
            or index_path.name != "llms.txt"
        ):
            raise ExtensionError(
                "Generated llms.txt index paths must stay within the build directory"
            )
        index_directory = index_path.parent
        if index_directory == PurePosixPath(".") or (
            index_directory == page_directory
            or index_directory in page_directory.parents
        ):
            candidates.append(index_path)

    return max(
        candidates, key=lambda path: len(path.parts), default=PurePosixPath("llms.txt")
    )


def _validated_exclude_patterns(app: Sphinx) -> list[str]:
    """Return validated document patterns excluded from generated indexes."""
    exclude_patterns = getattr(app.config, "llms_txt_exclude", [])
    if exclude_patterns is None or isinstance(exclude_patterns, str):
        raise ExtensionError(
            "llms_txt_exclude must be an iterable of strings, not None or a string"
        )
    if not isinstance(exclude_patterns, Iterable):
        raise ExtensionError("llms_txt_exclude must be an iterable of strings")
    patterns = list(exclude_patterns)
    if not all(isinstance(pattern, str) for pattern in patterns):
        raise ExtensionError("llms_txt_exclude must be an iterable of strings")
    return patterns


def get_llms_txt_index_path(app: Sphinx, docname: str) -> PurePosixPath:
    """Return the most-specific generated ``llms.txt`` covering a document.

    The path is POSIX and relative to the HTML build root so discovery metadata
    can render it relative to the current page. The root index is the fallback.
    """
    if not getattr(app.config, "llms_txt_nested_enabled", True):
        return PurePosixPath("llms.txt")

    exclude_patterns = _validated_exclude_patterns(app)
    included_docnames = (
        candidate
        for candidate in app.env.found_docs
        if not any(patmatch(candidate, pattern) for pattern in exclude_patterns)
    )
    index_paths = _nested_index_paths(app, included_docnames)
    return _most_specific_index_path(_published_html_path(app, docname), index_paths)


@dataclass(frozen=True)
class SummaryOptions:
    """Effective configuration for llms.txt page-summary generation."""

    enabled: bool
    provider: str
    model: str
    base_url: str
    api_key_env: str
    allow_insecure_auth: bool
    max_input_chars: int
    timeout: int
    cache_path: str


class MarkdownLayout(str, Enum):
    """Published Markdown path layout."""

    APPEND = "append"
    APPEND_NO_SLASH = "append-no-slash"
    REPLACE = "replace"


SUFFIX_MODE_ALIASES = {"both": "auto"}
SUFFIX_MODES = ("auto", "append", "replace", "file-suffix", "url-suffix")
SUPPORTED_SUFFIX_MODES = (*SUFFIX_MODES, *SUFFIX_MODE_ALIASES)
DEPRECATED_SUFFIX_MODES = {
    "both": "auto",
    "file-suffix": "append",
    "url-suffix": "append",
}


def normalize_suffix_mode(suffix_mode: str) -> str:
    """Return the effective v2 suffix mode for a configured value."""
    effective_mode = SUFFIX_MODE_ALIASES.get(suffix_mode, suffix_mode)
    if effective_mode not in SUFFIX_MODES:
        valid_modes = ", ".join(repr(mode) for mode in SUPPORTED_SUFFIX_MODES)
        raise ExtensionError(
            f"Invalid llms_txt_suffix_mode: {suffix_mode!r}. "
            f"Must be one of: {valid_modes}"
        )
    return effective_mode


def resolve_markdown_targets(
    builder_name: str,
    docname: str,
    suffix_mode: str,
    outdir: Path,
) -> tuple[dict[MarkdownLayout, Path], MarkdownLayout]:
    """Resolve every published target and the canonical layout for a document."""
    effective_mode = normalize_suffix_mode(suffix_mode)
    doc_path = Path(docname)

    if builder_name == "dirhtml":
        if doc_path == Path("index"):
            html_target = outdir / "index.html"
            append_no_slash_target = outdir / "index.md"
            has_no_slash_url = False
        elif doc_path.name == "index":
            html_target = outdir / doc_path.parent / "index.html"
            append_no_slash_target = (
                outdir / doc_path.parent.parent / f"{doc_path.parent.name}.md"
            )
            has_no_slash_url = True
        else:
            html_target = outdir / doc_path / "index.html"
            append_no_slash_target = outdir / doc_path.parent / f"{doc_path.name}.md"
            has_no_slash_url = True
    else:
        html_target = outdir / doc_path.parent / f"{doc_path.name}.html"
        append_no_slash_target = Path(f"{html_target}.md")
        has_no_slash_url = False

    append_target = Path(f"{html_target}.md")
    replace_target = html_target.with_suffix(".md")

    if effective_mode == "replace":
        return {MarkdownLayout.REPLACE: replace_target}, MarkdownLayout.REPLACE
    if effective_mode == "file-suffix":
        return {MarkdownLayout.APPEND: append_target}, MarkdownLayout.APPEND
    if effective_mode == "url-suffix":
        if builder_name != "dirhtml":
            return {MarkdownLayout.APPEND: append_target}, MarkdownLayout.APPEND
        return (
            {MarkdownLayout.APPEND_NO_SLASH: append_no_slash_target},
            MarkdownLayout.APPEND_NO_SLASH,
        )
    targets = {MarkdownLayout.APPEND: append_target}
    if effective_mode == "append":
        if has_no_slash_url:
            targets[MarkdownLayout.APPEND_NO_SLASH] = append_no_slash_target
        return targets, MarkdownLayout.APPEND
    if effective_mode == "auto":
        if has_no_slash_url:
            targets[MarkdownLayout.APPEND_NO_SLASH] = append_no_slash_target
        targets[MarkdownLayout.REPLACE] = replace_target
        return targets, MarkdownLayout.APPEND
    raise AssertionError(f"Unhandled normalized suffix mode: {effective_mode!r}")


class MarkdownGenerator:
    """Generates markdown files using sphinx_markdown_builder."""

    def __init__(self, app: Sphinx):
        self.app = app
        self.generated_markdown_files = []  # Track generated markdown files
        self._docname_by_output_file: dict[Path, str] = {}  # output file → docname
        self._markdown_file_by_docname: dict[str, Path] = {}
        self._link_target_by_token: dict[str, LinkTarget] = {}
        self.outdir = None
        self.md_build_dir = None
        self.md_build_process = None
        self.md_build_logfile = None
        self.parallel = None
        self._summary_cache: dict[str, dict[str, str]] | None = None
        self._loaded_summary_cache_path: Path | None = None
        self._generated_llms_full_path: Path | None = None

    def setup(self):
        """Set up the extension."""
        self.app.connect("builder-inited", self.build_llms_txt)

    def add_discovery_metadata(
        self,
        app: Sphinx,
        pagename: str,
        templatename: str,
        context: dict[str, Any],
        doctree: docutils.nodes.document | None,
    ) -> None:
        """Advertise the canonical Markdown page and its covering llms.txt."""
        if pagename not in app.env.found_docs:
            return

        targets, canonical_layout = self._target_paths_for_docname(pagename)
        page_uri = app.builder.get_target_uri(pagename)
        markdown_href = html.escape(
            relative_uri(
                page_uri,
                targets[canonical_layout].relative_to(self.outdir).as_posix(),
            ),
            quote=True,
        )
        llms_txt_path = get_llms_txt_index_path(app, pagename)
        llms_txt_href = html.escape(
            relative_uri(page_uri, llms_txt_path.as_posix()), quote=True
        )
        context["metatags"] = context.get("metatags", "") + (
            f'\n<link rel="alternate" type="text/markdown" '
            f'href="{markdown_href}">'
            f'\n<link rel="describedby" href="{llms_txt_href}">'
        )

    def build_llms_txt(self, app: Sphinx):
        """Generate markdown files using sphinx_markdown_builder and concatenate them into llms.txt."""
        if not getattr(self.app.config, "llms_txt_enabled", True):
            logger.info(
                "llms.txt generation is disabled (llms_txt_enabled=False), skipping..."
            )
            return

        self.outdir = Path(app.builder.outdir)
        self.md_build_dir = self.outdir / "_markdown_build"
        self.parallel = getattr(self.app.config, "llms_txt_build_parallel", True)
        configured_suffix_mode = getattr(
            self.app.config, "llms_txt_suffix_mode", "auto"
        )
        self.suffix_mode = normalize_suffix_mode(configured_suffix_mode)
        if configured_suffix_mode in DEPRECATED_SUFFIX_MODES:
            logger.info(
                "llms_txt_suffix_mode=%r is deprecated; use %r instead",
                configured_suffix_mode,
                DEPRECATED_SUFFIX_MODES[configured_suffix_mode],
            )

        if app.builder and app.builder.name == "markdown":
            return

        if not app.builder or app.builder.name not in ["html", "dirhtml"]:
            logger.info(
                "llms.txt generation only works with HTML builders (html or dirhtml), skipping..."
            )
            return

        self.app.connect("html-page-context", self.add_discovery_metadata)

        # Start the markdown builder subproces in the background
        if self.parallel:
            self.build_markdown_files()
        else:
            logger.info(
                "Option llms_txt_build_parallel is set to False, will build markdown files after the primary build is finished"
            )
            self.app.connect("build-finished", self.build_markdown_files, priority=100)
        # Once the primary build is finished, combine the markdown files
        self.app.connect("build-finished", self.combine_builds, priority=101)

    def combine_builds(self, app: Sphinx, exception: Exception | None):
        """Combine the markdown files into llms-full.txt and llms.txt and merge the build outputs together."""
        if exception:
            logger.warning("Skipping build combination due to build error")
            try:
                # Don't leave a markdown build subprocess behind (parallel mode).
                if self.md_build_process and self.md_build_process.poll() is None:
                    logger.info("Terminating markdown build subprocess...")
                    self.md_build_process.terminate()
                    try:
                        self.md_build_process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        logger.warning(
                            "Markdown build subprocess did not exit after terminate(); "
                            "killing it"
                        )
                        self.md_build_process.kill()
                        self.md_build_process.wait()
            finally:
                if self.md_build_dir and self.md_build_dir.exists():
                    shutil.rmtree(self.md_build_dir)
            return

        if not self.md_build_process:
            logger.warning(
                "Markdown build process not found, skipping build output combination"
            )
            return

        if self.md_build_process.poll() is None:
            logger.info("Waiting for markdown build subprocess to finish...")
            self.md_build_process.wait()
            logger.info("Markdown build subprocess finished")

        remaining_log, relayed_warning_count = self._relay_unknown_node_warnings()
        if (
            relayed_warning_count
            and self.app.warningiserror
            and hasattr(logging, "skip_warningiserror")
        ):
            # Sphinx 5-7 normally raise on the first warning, even during
            # build-finished.  The relay defers that fail-fast behavior so all
            # child diagnostics are emitted and combination can clean up, then
            # records the warnings-as-errors result explicitly.
            self.app.statuscode = 1
        try:
            if self.md_build_process.returncode != 0:
                logger.error(
                    f"Markdown build subprocess failed with return code {self.md_build_process.returncode},"
                )
                if remaining_log.strip():
                    logger.error(remaining_log)
                return

            # Copy markdown files to the main output directory
            self.copy_markdown_files()

            # Concatenate all markdown files into llms-full.txt
            self._generated_llms_full_path = None
            if getattr(self.app.config, "llms_txt_full_build", False):
                self._generated_llms_full_path = self.build_llms_full_txt()

            # Create llms.txt from a custom source or the generated sitemap
            custom_sitemap = getattr(self.app.config, "llms_txt_override_source", "")
            nested_enabled = getattr(self.app.config, "llms_txt_nested_enabled", True)
            sorted_sitemap_files = self._sorted_sitemap_files(
                self.generated_markdown_files
            )
            if custom_sitemap:
                self.build_custom_llms_txt()
            else:
                self.create_sitemap(sorted_sitemap_files)
            if nested_enabled:
                self.create_nested_sitemaps(sorted_sitemap_files)
        finally:
            # Clean up temporary build directory
            if self.md_build_dir.exists():
                shutil.rmtree(self.md_build_dir)

    def _relay_unknown_node_warnings(self) -> tuple[str, int]:
        """Relay child unknown-node warnings and return all other log output."""
        with open(
            self.md_build_logfile.name, encoding="utf-8", errors="replace"
        ) as logfile:
            lines = logfile.read().splitlines()

        remaining_lines = []
        relayed_warning_count = 0
        skip_warningiserror = getattr(logging, "skip_warningiserror", None)
        warning_context = (
            skip_warningiserror()
            if skip_warningiserror and self.app.warningiserror
            else nullcontext()
        )
        with warning_context:
            for line in lines:
                match = UNKNOWN_NODE_WARNING_PATTERN.match(line)
                if match is None:
                    remaining_lines.append(line)
                    continue

                source = match.group("source")
                line_number = match.group("line")
                # A tuple is interpreted as ``(docname, line)`` by Sphinx, but
                # the subprocess reports a source path.  Keep the already-
                # resolved location as a string so Sphinx does not append the
                # source suffix.
                location = f"{source}:{line_number or ''}" if source else None
                logger.warning(match.group("message"), location=location)
                relayed_warning_count += 1

        return "\n".join(remaining_lines), relayed_warning_count

    def build_markdown_files(
        self, app: Sphinx | None = None, exception: Exception | None = None
    ):
        """Start the markdown sub-build unless the primary build failed."""
        if exception is not None:
            logger.info("Skipping markdown build because the primary build failed")
            return

        # Create temporary markdown build directory
        self.md_build_dir.mkdir(exist_ok=True)
        self.md_build_logfile = tempfile.NamedTemporaryFile(
            mode="w", delete=False, prefix="sphinx_llm_output_", suffix=".log"
        )
        try:
            # Build markdown files using the sphinx-llm markdown builder.
            # The configuration directory is passed explicitly as it does not
            # necessarily live in the source directory (sphinx-build -c option).
            sphinx_build_cmd = [
                sys.executable,
                "-m",
                "sphinx",
                "-b",
                SphinxLlmMarkdownBuilder.name,
                "-t",
                "sphinx_llm_markdown",
                "-c",
                str(self.app.confdir),
                str(self.app.srcdir),
                str(self.md_build_dir),
            ]

            # Propagate the tags of the primary build so that conditional
            # content (e.g. ".. only::" directives) renders the same in the
            # markdown output. This intentionally includes the dynamic tags
            # derived from the primary builder (e.g. "html", "format_html"):
            # the markdown output this way stays faithful to the HTML pages it
            # complements.
            for tag in self.app.tags:
                sphinx_build_cmd += ["-t", tag]

            # Preserve command-line configuration overrides from the primary
            # build. Without forwarding these, the markdown sub-build reloads
            # conf.py defaults and can behave differently from the HTML build.
            for name, value in self.app.config.overrides.items():
                if isinstance(value, bool):
                    value = "1" if value else "0"
                sphinx_build_cmd += ["-D", f"{name}={value}"]

            # When building sequentially we can reuse the doctree directory from the primary build
            # but in parallel builds these may clobber each other so we need to use a separate one
            if not self.parallel:
                sphinx_build_cmd.append("-d")
                sphinx_build_cmd.append(str(self.app.doctreedir))

            logger.info(
                f"Spawning additional sphinx subprocess to build markdown files for llms.txt: {' '.join(sphinx_build_cmd)}"
            )
            try:
                logger.info(
                    f"Subprocess output available at: {self.md_build_logfile.name}"
                )

                with self.md_build_logfile:
                    self.md_build_process = subprocess.Popen(
                        sphinx_build_cmd,
                        stdout=self.md_build_logfile,
                        stderr=self.md_build_logfile,
                    )
            except Exception as exc:
                logger.error(f"Failed to run sphinx-build subprocess: {exc}")
        except Exception as e:
            logger.error(f"Failed to generate markdown files: {e}")

    def _get_target_paths(
        self, md_file: Path
    ) -> tuple[dict[MarkdownLayout, Path], MarkdownLayout]:
        """Determine target file locations for a Markdown build output."""
        rel_path = md_file.relative_to(self.md_build_dir)
        return self._target_paths_for_docname(rel_path.with_suffix("").as_posix())

    def _is_excluded(self, docname: str) -> bool:
        """Check whether a document is excluded from llms.txt and llms-full.txt."""
        return any(
            patmatch(docname, pattern)
            for pattern in _validated_exclude_patterns(self.app)
        )

    def copy_markdown_files(self):
        """Copy markdown files from build directory to output directory."""
        md_files = sorted(self.md_build_dir.rglob("*.md"))
        self.generated_markdown_files = []
        self._docname_by_output_file = {}
        num_excluded = 0
        self._markdown_file_by_docname = {}
        link_targets_path = self.md_build_dir / LINK_TARGETS_FILENAME
        self._link_target_by_token = json.loads(
            link_targets_path.read_text(encoding="utf-8")
        )

        plans = []
        target_owners: dict[Path, tuple[str, MarkdownLayout]] = {}
        for md_file in md_files:
            target_files, primary_layout = self._get_target_paths(md_file)
            docname = self._get_docname_from_md_file(md_file)
            self._markdown_file_by_docname[docname] = md_file
            plans.append((md_file, docname, target_files, primary_layout))
            for layout, target_file in target_files.items():
                owner = target_owners.get(target_file)
                if owner is not None:
                    owner_docname, owner_layout = owner
                    relative_target = target_file.relative_to(self.outdir).as_posix()
                    raise ExtensionError(
                        f"Documents {owner_docname!r} ({owner_layout.value}) and "
                        f"{docname!r} ({layout.value}) resolve to the same published "
                        f"Markdown path {relative_target!r}"
                    )
                target_owners[target_file] = (docname, layout)

        for md_file, docname, target_files, primary_layout in plans:
            primary_target = target_files[primary_layout]
            content = md_file.read_text(encoding="utf-8")

            # Write the file with links for its published location.
            for layout, target_file in target_files.items():
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(
                    self._materialize_links(
                        content,
                        source_docname=docname,
                        source_target=target_file,
                        target_layout=layout,
                    ),
                    encoding="utf-8",
                )

            # Documents matching one of the llms_txt_exclude patterns still
            # get their individual markdown files (copied above) but are left
            # out of llms.txt and llms-full.txt.
            if self._is_excluded(docname):
                num_excluded += 1
                continue

            # Only add the primary target to avoid duplicates in llms-full.txt
            self.generated_markdown_files.append(primary_target)
            self._docname_by_output_file[primary_target] = docname

        logger.info(f"Generated {len(self.generated_markdown_files)} context files")
        if num_excluded:
            logger.info(
                f"Excluded {num_excluded} documents from llms.txt and llms-full.txt"
            )

    def _target_paths_for_docname(
        self, docname: str
    ) -> tuple[dict[MarkdownLayout, Path], MarkdownLayout]:
        builder_name = self.app.builder.name if self.app.builder else "html"
        return resolve_markdown_targets(
            builder_name, docname, self.suffix_mode, self.outdir
        )

    def _markdown_http_base(self) -> str:
        return (
            self.app.config._raw_config.get("markdown_http_base")
            or getattr(self.app.config, "markdown_http_base", "")
        ).rstrip("/")

    def _materialize_links(
        self,
        content: str,
        source_docname: str,
        source_target: Path | None,
        target_layout: MarkdownLayout | None,
    ) -> str:
        """Resolve document link tokens for one published location."""

        def replace_link(match: re.Match) -> str:
            token = match.group(0)
            link_target = self._link_target_by_token.get(token)
            if link_target is None:
                return token

            target_docname = link_target["docname"]
            fragment = link_target["fragment"]
            if (
                source_target is not None
                and target_docname == source_docname
                and fragment
            ):
                return f"#{fragment}"

            target_files, primary_layout = self._target_paths_for_docname(
                target_docname
            )
            selected_layout = target_layout or primary_layout
            target_file = target_files.get(
                selected_layout, target_files[primary_layout]
            )
            relative_target = target_file.relative_to(self.outdir).as_posix()
            http_base = self._markdown_http_base()
            if http_base:
                uri = f"{http_base}/{relative_target}"
            elif source_target is None:
                uri = relative_target
            else:
                source_dir = source_target.parent.relative_to(self.outdir).as_posix()
                uri = posixpath.relpath(relative_target, start=source_dir or ".")

            if fragment:
                uri = f"{uri}#{fragment}"
            return uri

        return LINK_TOKEN_PATTERN.sub(replace_link, content)

    def build_llms_full_txt(self) -> Path:
        # Concatenate all markdown files into llms-full.txt
        llms_txt_path = self.outdir / "llms-full.txt"
        with open(llms_txt_path, "w", encoding="utf-8") as llms_txt:
            # Sort files to ensure index.html.md comes first
            sorted_files = sorted(
                self.generated_markdown_files,
                key=lambda path: (
                    path.relative_to(self.outdir).as_posix()
                    not in {"index.html.md", "index.md"},
                    path.relative_to(self.outdir).as_posix(),
                ),
            )

            for md_file in sorted_files:
                docname = self._docname_by_output_file[md_file]
                content = self._markdown_file_by_docname[docname].read_text(
                    encoding="utf-8"
                )
                content = self._materialize_links(
                    content,
                    source_docname=docname,
                    source_target=None,
                    target_layout=None,
                )
                relative_path = md_file.relative_to(self.outdir).as_posix()
                llms_txt.write(f"# {relative_path}\n\n")
                llms_txt.write(content)
                llms_txt.write("\n\n")
        logger.info(f"Concatenated full context into: {llms_txt_path}")
        return llms_txt_path

    def build_custom_llms_txt(self):
        """Write a configured rendered source document to llms.txt."""
        configured_source = str(self.app.config.llms_txt_override_source)
        normalized_source = configured_source.replace("\\", "/").removeprefix("./")
        candidate_docnames = [normalized_source]
        without_suffix = str(Path(normalized_source).with_suffix(""))
        if without_suffix != normalized_source:
            candidate_docnames.append(without_suffix)

        docname = next(
            (
                candidate
                for candidate in candidate_docnames
                if candidate in self._markdown_file_by_docname
            ),
            None,
        )
        if docname is None:
            raise ExtensionError(
                f"llms_txt_override_source {configured_source!r} did not match a rendered "
                "Sphinx document"
            )
        if self._is_excluded(docname):
            raise ExtensionError(
                f"llms_txt_override_source {configured_source!r} matches "
                "llms_txt_exclude"
            )

        source_file = self._markdown_file_by_docname[docname]
        content = source_file.read_text(encoding="utf-8")
        _, primary_layout = self._target_paths_for_docname(docname)
        llms_txt_path = self.outdir / "llms.txt"
        llms_txt_path.write_text(
            self._materialize_links(
                content,
                source_docname=docname,
                source_target=llms_txt_path,
                target_layout=primary_layout,
            ),
            encoding="utf-8",
        )
        logger.info(
            "Created llms.txt from configured source document: %s", configured_source
        )

    def get_project_description(self) -> str:
        """Get the description of the project."""
        project_title = getattr(self.app.config, "project", "Documentation")
        if (
            hasattr(self.app.config, "llms_txt_description")
            and self.app.config.llms_txt_description
        ):
            return self.app.config.llms_txt_description

        try:
            meta_description = metadata(project_title).get("Description")
            if meta_description:
                return meta_description
        except PackageNotFoundError:
            pass

        if hasattr(self.app.config, "html_title") and self.app.config.html_title:
            return self.app.config.html_title

        return f"Documentation for {project_title}"

    def _sorted_sitemap_files(self, files: Iterable[Path]) -> list[Path]:
        """Sort a sitemap subset by the global toctree and orphan order."""
        toctree_order = {
            docname: index
            for index, docname in enumerate(self.app.env.collect_relations())
        }
        return sorted(
            files,
            key=lambda path: (
                toctree_order.get(
                    self._docname_by_output_file[path], len(toctree_order)
                ),
                self._docname_by_output_file[path],
            ),
        )

    def _sitemap_url(self, md_file: Path, llms_txt_path: Path) -> str:
        """Return a canonical Markdown target URL from one sitemap location."""
        relative_target = md_file.relative_to(self.outdir).as_posix()
        http_base = self._markdown_http_base()
        if http_base:
            return f"{http_base}/{quote(relative_target, safe='/')}"
        index_directory = llms_txt_path.parent.relative_to(self.outdir).as_posix()
        relative_url = posixpath.relpath(relative_target, start=index_directory or ".")
        return quote(relative_url, safe="/")

    def _top_level_sitemap_url(self, llms_txt_path: Path) -> str:
        """Return the top-level index URL from a nested sitemap location."""
        http_base = self._markdown_http_base()
        if http_base:
            return f"{http_base}/llms.txt"
        index_directory = llms_txt_path.parent.relative_to(self.outdir).as_posix()
        return posixpath.relpath("llms.txt", start=index_directory or ".")

    def _write_sitemap(
        self,
        llms_txt_path: Path,
        files: Iterable[Path],
        *,
        subsection: bool = False,
    ) -> None:
        """Write the common page listing for one Markdown sitemap."""
        llms_txt_path.parent.mkdir(parents=True, exist_ok=True)
        with open(llms_txt_path, "w", encoding="utf-8") as sitemap:
            project_title = getattr(self.app.config, "project", "Documentation")
            sitemap.write(f"# {project_title}\n\n")

            for line in self.get_project_description().strip().split("\n"):
                sitemap.write(f"> {line}\n")
            sitemap.write("\n\n")

            if hasattr(self.app.config, "copyright") and self.app.config.copyright:
                sitemap.write(f"{self.app.config.copyright}\n\n")

            pages_heading = "Pages in this subsection" if subsection else "Pages"
            sitemap.write(f"## {pages_heading}\n\n")
            for md_file in files:
                title = self.extract_title_from_markdown(md_file)
                url = self._sitemap_url(md_file, llms_txt_path)
                sitemap.write(
                    _serialize_sitemap_entry(
                        title, url, self.get_page_description(md_file)
                    )
                    + "\n"
                )
            if subsection:
                top_level_url = self._top_level_sitemap_url(llms_txt_path)
                sitemap.write(
                    "\n## Optional\n\n"
                    + _serialize_sitemap_entry(
                        "Top-level llms.txt",
                        top_level_url,
                        "Complete documentation index.",
                    )
                    + "\n"
                )

    def create_sitemap(self, files: Iterable[Path] | None = None) -> None:
        """Create the root Markdown sitemap in ``llms.txt``."""
        llms_txt_path = self.outdir / "llms.txt"
        if files is None:
            files = self._sorted_sitemap_files(self.generated_markdown_files)
        self._write_sitemap(llms_txt_path, files)
        # List llms-full.txt only when this build generated the file. Custom root
        # indexes do not call this method and therefore remain unmodified.
        if (
            self._generated_llms_full_path is not None
            and self._generated_llms_full_path.is_file()
        ):
            http_base = self._markdown_http_base()
            full_url = f"{http_base}/llms-full.txt" if http_base else "llms-full.txt"
            with open(llms_txt_path, "a", encoding="utf-8") as sitemap:
                sitemap.write(
                    "\n## Optional\n\n"
                    + _serialize_sitemap_entry(
                        "llms-full.txt",
                        full_url,
                        "Complete documentation in a single file.",
                    )
                    + "\n"
                )
        logger.info(f"Created llms.txt sitemap: {llms_txt_path}")

    def create_nested_sitemaps(self, files: Iterable[Path] | None = None) -> None:
        """Create scoped indexes below the HTML build root."""
        if files is None:
            files = self._sorted_sitemap_files(self.generated_markdown_files)
        files_by_scope: dict[PurePosixPath, list[Path]] = {}
        for md_file in files:
            page_directory = _published_html_path(
                self.app, self._docname_by_output_file[md_file]
            ).parent
            for scope in (page_directory, *page_directory.parents):
                if scope == PurePosixPath("."):
                    break
                files_by_scope.setdefault(scope, []).append(md_file)

        for scope in sorted(files_by_scope, key=lambda path: path.parts):
            output_path = self.outdir.joinpath(*scope.parts, "llms.txt")
            self._write_sitemap(output_path, files_by_scope[scope], subsection=True)
            logger.info(f"Created nested llms.txt sitemap: {output_path}")

    def extract_title_from_markdown(self, md_file: Path) -> str:
        """Extract the title from a markdown file."""
        try:
            with open(md_file, encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")

                # Look for the first heading (starts with #)
                for line in lines:
                    line = line.strip()
                    if line.startswith("#"):
                        title = line.lstrip("#").strip()
                        return title

                # If no heading found, try to get title from filename
                base_name = md_file.stem.replace(".html", "")
                if base_name == "index":
                    return "Home"
                return base_name.replace("_", " ").title()
        except Exception:
            # Fallback to filename without extension
            base_name = md_file.stem.replace(".html", "")
            if base_name == "index":
                return "Home"
            return base_name.replace("_", " ").title()

    def _get_docname_from_md_file(self, md_file: Path) -> str:
        """Return the Sphinx docname for a markdown build output file."""
        rel_path = md_file.relative_to(self.md_build_dir)
        return rel_path.with_suffix("").as_posix()

    def get_page_description(self, md_file: Path) -> str:
        """Get a brief description of the page content.

        If the source page defines an ``html_meta`` description (via
        ``.. meta:: :description:`` in rST or ``html_meta:`` frontmatter in
        MyST), that value is used.  Otherwise the first 100 characters of the
        first meaningful paragraph in the generated markdown are returned.
        """
        docname = self._docname_by_output_file.get(md_file, "")
        if docname:
            try:
                doctree = self.app.env.get_doctree(docname)
                for node in doctree.traverse(docutils.nodes.meta):
                    content = node.get("content")
                    if (
                        node.get("name") == "description"
                        and isinstance(content, str)
                        and content.strip()
                    ):
                        return content.strip()
            except Exception:
                logger.exception(
                    "Failed to read html_meta description from doctree for '%s'; "
                    "falling back to content-based description",
                    docname,
                )

        if docname and self._summary_enabled():
            return self.generate_page_summary(docname, md_file)

        return self.extract_description_from_markdown(md_file)

    def _configured_summary_value(
        self, config_name: str, env_name: str, default: Any
    ) -> Any:
        """Resolve one option as ``-D``, environment, conf.py, then default."""
        config = self.app.config
        if config_name in getattr(config, "overrides", {}):
            return getattr(config, config_name)
        if env_name in os.environ:
            return os.environ[env_name]
        return getattr(config, config_name, default)

    @staticmethod
    def _parse_summary_bool(value: Any, env_name: str) -> bool:
        """Parse a bool from Sphinx or an environment variable."""
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
        raise ExtensionError(
            f"{env_name} must be a boolean value such as 1, 0, true, or false"
        )

    @staticmethod
    def _parse_summary_positive_int(value: Any, env_name: str) -> int:
        """Parse a positive integer summary setting."""
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = 0
        if parsed <= 0:
            raise ExtensionError(f"{env_name} must be a positive integer")
        return parsed

    def _summary_enabled(self) -> bool:
        """Return whether page summaries are explicitly enabled."""
        env_name = "SPHINX_LLM_SUMMARY_ENABLED"
        value = self._configured_summary_value(
            "llms_txt_summary_enabled", env_name, False
        )
        return self._parse_summary_bool(value, env_name)

    def _get_summary_options(self) -> SummaryOptions:
        """Return validated effective page-summary configuration."""
        provider = str(
            self._configured_summary_value(
                "llms_txt_summary_provider",
                "SPHINX_LLM_SUMMARY_PROVIDER",
                "openai-compatible",
            )
        ).strip()
        if provider != "openai-compatible":
            raise ExtensionError(
                "Invalid llms.txt summary provider "
                f"{provider!r}; only 'openai-compatible' is supported"
            )

        model = str(
            self._configured_summary_value(
                "llms_txt_summary_model", "SPHINX_LLM_SUMMARY_MODEL", ""
            )
        ).strip()
        base_url = str(
            self._configured_summary_value(
                "llms_txt_summary_base_url", "SPHINX_LLM_SUMMARY_BASE_URL", ""
            )
        ).strip()
        api_key_env = str(
            self._configured_summary_value(
                "llms_txt_summary_api_key_env",
                "SPHINX_LLM_SUMMARY_API_KEY_ENV",
                DEFAULT_API_KEY_ENV,
            )
        ).strip()
        allow_insecure_auth_env = "SPHINX_LLM_SUMMARY_ALLOW_INSECURE_AUTH"
        allow_insecure_auth = self._parse_summary_bool(
            self._configured_summary_value(
                "llms_txt_summary_allow_insecure_auth",
                allow_insecure_auth_env,
                False,
            ),
            allow_insecure_auth_env,
        )
        max_input_env = "SPHINX_LLM_SUMMARY_MAX_INPUT_CHARS"
        max_input_chars = self._parse_summary_positive_int(
            self._configured_summary_value(
                "llms_txt_summary_max_input_chars", max_input_env, 12_000
            ),
            max_input_env,
        )
        timeout_env = "SPHINX_LLM_SUMMARY_TIMEOUT"
        timeout = self._parse_summary_positive_int(
            self._configured_summary_value("llms_txt_summary_timeout", timeout_env, 60),
            timeout_env,
        )
        cache_path = str(
            self._configured_summary_value(
                "llms_txt_summary_cache_path",
                "SPHINX_LLM_SUMMARY_CACHE_PATH",
                "",
            )
        ).strip()
        return SummaryOptions(
            enabled=self._summary_enabled(),
            provider=provider,
            model=model,
            base_url=base_url,
            api_key_env=api_key_env,
            allow_insecure_auth=allow_insecure_auth,
            max_input_chars=max_input_chars,
            timeout=timeout,
            cache_path=cache_path,
        )

    @property
    def _summary_cache_path(self) -> Path:
        """Return the configured cache path, defaulting under the doctree dir."""
        configured = self._get_summary_options().cache_path
        if not configured:
            return Path(self.app.doctreedir) / "sphinx-llm-page-summaries.json"
        path = Path(configured)
        if not path.is_absolute():
            path = Path(self.app.confdir) / path
        return path

    def _load_summary_cache(self) -> dict[str, dict[str, str]]:
        """Load the versioned cache, recovering from bad or old files."""
        cache_path = self._summary_cache_path
        if (
            self._summary_cache is not None
            and self._loaded_summary_cache_path == cache_path
        ):
            return self._summary_cache

        self._summary_cache = {}
        self._loaded_summary_cache_path = cache_path
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if (
                isinstance(payload, dict)
                and payload.get("version") == SUMMARY_CACHE_VERSION
                and isinstance(payload.get("summaries"), dict)
            ):
                self._summary_cache = payload["summaries"]
            else:
                logger.warning(
                    "Ignoring incompatible llms.txt page summary cache at %s",
                    cache_path,
                )
        except FileNotFoundError:
            pass
        except (OSError, TypeError, ValueError):
            logger.warning(
                "Could not read the llms.txt page summary cache at %s; "
                "summaries will be regenerated",
                cache_path,
            )
        return self._summary_cache

    def _save_summary_cache(self) -> None:
        """Atomically persist the page-summary cache."""
        cache_path = self._summary_cache_path
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": SUMMARY_CACHE_VERSION,
            "summaries": self._load_summary_cache(),
        }
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=cache_path.parent,
                prefix=f".{cache_path.name}.",
                delete=False,
            ) as cache_file:
                temporary_path = Path(cache_file.name)
                json.dump(payload, cache_file, indent=2, sort_keys=True)
            temporary_path.replace(cache_path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _summary_fingerprint(
        markdown: str,
        options: SummaryOptions,
        prompt_version: int,
        reasoning_effort: str,
    ) -> str:
        """Hash complete Markdown and all non-secret generation parameters."""
        settings = {
            "allow_insecure_auth": options.allow_insecure_auth,
            "base_url": options.base_url,
            "max_input_chars": options.max_input_chars,
            "model": options.model,
            "prompt_version": prompt_version,
            "provider": options.provider,
            "reasoning_effort": reasoning_effort,
            "timeout": options.timeout,
        }
        fingerprint_input = json.dumps(settings, sort_keys=True) + "\0" + markdown
        return hashlib.sha256(fingerprint_input.encode()).hexdigest()

    def generate_page_summary(self, docname: str, md_file: Path) -> str:
        """Generate or retrieve a cached summary from final Markdown."""
        options = self._get_summary_options()
        if not options.model:
            raise ExtensionError(
                "No llms.txt summary model is configured; set "
                "llms_txt_summary_model or SPHINX_LLM_SUMMARY_MODEL"
            )

        # These helpers do not import the optional OpenAI dependency. Importing
        # them only after opt-in keeps normal builds isolated from provider code.
        from .summary import (
            DEFAULT_REASONING_EFFORT,
            SUMMARY_PROMPT_VERSION,
            InsecureEndpointError,
            MalformedSummaryResponseError,
            MissingGenerationDependenciesError,
        )

        markdown = md_file.read_text(encoding="utf-8")
        fingerprint = self._summary_fingerprint(
            markdown,
            options,
            SUMMARY_PROMPT_VERSION,
            DEFAULT_REASONING_EFFORT,
        )
        cache = self._load_summary_cache()
        record = cache.get(docname)
        if (
            isinstance(record, dict)
            and record.get("fingerprint") == fingerprint
            and isinstance(record.get("summary"), str)
            and record["summary"].strip()
        ):
            return record["summary"]

        if options.api_key_env and not os.environ.get(options.api_key_env):
            raise ExtensionError(
                "No llms.txt summary API key is configured; set the environment "
                f"variable named by llms_txt_summary_api_key_env ({options.api_key_env!r})"
            )

        logger.info(
            "Generating llms.txt summary for '%s' with %s at %s",
            docname,
            options.model,
            options.base_url or "the default OpenAI endpoint",
        )
        try:
            # Imported only for an enabled cache miss, keeping normal builds free
            # of the optional provider dependency.
            from openai import APIError

            from .summary import summarize_text

            summary = " ".join(
                summarize_text(
                    markdown[: options.max_input_chars],
                    options.model,
                    base_url=options.base_url,
                    api_key_env=options.api_key_env,
                    reasoning_effort=DEFAULT_REASONING_EFFORT,
                    timeout=options.timeout,
                    use_environment_defaults=False,
                    allow_insecure_auth=options.allow_insecure_auth,
                ).split()
            )
        except ImportError:
            raise ExtensionError(
                "LLM summarization requires the optional generation dependencies. "
                "Install them with 'pip install sphinx-llm[gen]'."
            ) from None
        except MissingGenerationDependenciesError:
            raise ExtensionError(
                "LLM summarization requires the optional generation dependencies. "
                "Install them with 'pip install sphinx-llm[gen]'."
            ) from None
        except MalformedSummaryResponseError:
            raise ExtensionError(
                "The OpenAI-compatible endpoint returned a malformed or empty "
                f"summary for document {docname!r}"
            ) from None
        except InsecureEndpointError:
            raise ExtensionError(
                "Refusing to send the llms.txt summary API key to a non-loopback "
                f"endpoint over plain HTTP for document {docname!r}; use HTTPS or "
                "a loopback URL, or explicitly set "
                "llms_txt_summary_allow_insecure_auth=True or "
                "SPHINX_LLM_SUMMARY_ALLOW_INSECURE_AUTH=1"
            ) from None
        except ExtensionError:
            raise ExtensionError(
                f"Failed to generate an llms.txt summary for document {docname!r}; "
                "check the provider configuration and credentials"
            ) from None
        except APIError:
            raise ExtensionError(
                f"Failed to generate an llms.txt summary for document {docname!r}; "
                "check the provider configuration and credentials"
            ) from None
        if not summary:
            raise ExtensionError(
                f"The provider returned an empty llms.txt summary for document {docname!r}"
            )

        cache[docname] = {"fingerprint": fingerprint, "summary": summary}
        try:
            self._save_summary_cache()
        except OSError as error:
            logger.warning(
                "Could not persist the llms.txt page summary cache; "
                "summaries will be regenerated on the next build: %s",
                error,
            )
        return summary

    @staticmethod
    def extract_description_from_markdown(md_file: Path) -> str:
        """Extract a content-based description from a markdown file.

        Returns the first 100 characters of the first meaningful paragraph,
        or a filename-based fallback if no suitable paragraph is found.
        """
        try:
            with open(md_file, encoding="utf-8") as f:
                content = extract_prose(f.read())
                lines = content.split("\n")
                anchor = re.compile(r"^<a\b[^>]*>\s*</a>$", re.IGNORECASE)

                # Skip HTML comments and look for the first meaningful paragraph
                for line in lines:
                    line = line.strip()
                    # Skip empty lines, headings, anchors, and HTML comments
                    if (
                        line
                        and not line.startswith("#")
                        and not line.startswith("<!--")
                        and not line.startswith("-->")
                        and not line.startswith("..")
                        and not anchor.match(line)
                        and len(line) > 10
                    ):  # Ensure it's substantial content
                        return line[:100] + "..." if len(line) > 100 else line

                # Fallback descriptions based on filename
                base_name = md_file.stem.replace(".html", "")
                if base_name == "index":
                    return "Main documentation page"
                elif base_name == "test":
                    return "Testing and example page"
                else:
                    return "Page content"
        except Exception:
            # Fallback descriptions based on filename
            base_name = md_file.stem.replace(".html", "")
            if base_name == "index":
                return "Main documentation page"
            elif base_name == "test":
                return "Testing and example page"
            else:
                return "Page content"


def setup(app: Sphinx) -> dict[str, Any]:
    """Set up the Sphinx extension."""
    app.setup_extension("sphinx_llm.summary")
    if app.tags.has("sphinx_llm_markdown"):
        app.setup_extension("sphinx_markdown_builder")
        app.add_builder(SphinxLlmMarkdownBuilder)
    app.add_config_value("llms_txt_enabled", True, "")
    app.add_config_value("llms_txt_description", "", "env")
    app.add_config_value("llms_txt_build_parallel", True, "env")
    app.add_config_value("llms_txt_suffix_mode", "auto", "env")
    app.add_config_value("llms_txt_full_build", False, "env")
    app.add_config_value("llms_txt_nested_enabled", True, "env")
    app.add_config_value("llms_txt_exclude", [], "env")
    app.add_config_value("llms_txt_override_source", "", "env")
    app.add_config_value(
        SUPPRESS_UNKNOWN_NODE_WARNINGS_CONFIG,
        False,
        "env",
        types=(bool, list, tuple),
    )
    app.connect("config-inited", validate_suppress_unknown_node_warnings)
    if "markdown_http_base" not in app.config.values:
        app.add_config_value("markdown_http_base", "", "env")
    generator = MarkdownGenerator(app)
    generator.setup()

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
