# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Sphinx extension to generate markdown files alongside HTML files.

This extension hooks into the Sphinx build process to create markdown versions
of all documents using the sphinx_markdown_builder.
"""

import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from importlib.metadata import PackageNotFoundError, metadata
from pathlib import Path
from typing import Any, Optional, Union

import docutils.nodes
from sphinx.application import Sphinx
from sphinx.errors import ExtensionError
from sphinx.util import logging
from sphinx.util.matching import patmatch

from .markdown_builder import (
    LINK_TARGETS_FILENAME,
    LINK_TOKEN_PREFIX,
    LinkTarget,
    SphinxLlmMarkdownBuilder,
)
from .summary import DEFAULT_API_KEY_ENV
from .version import __version__

logger = logging.getLogger(__name__)
LINK_TOKEN_PATTERN = re.compile(rf"{re.escape(LINK_TOKEN_PREFIX)}[0-9a-f]{{32}}")
SUMMARY_CACHE_VERSION = 1


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

    FILE_SUFFIX = "file-suffix"
    URL_SUFFIX = "url-suffix"
    REPLACE = "replace"
    HTML = "html"


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
        self._summary_cache: Optional[dict[str, dict[str, str]]] = None
        self._loaded_summary_cache_path: Optional[Path] = None

    def setup(self):
        """Set up the extension."""
        self.app.connect("builder-inited", self.build_llms_txt)

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
        self.suffix_mode = getattr(self.app.config, "llms_txt_suffix_mode", "auto")

        # Backward compatibility: treat "both" as "auto"
        if self.suffix_mode == "both":
            self.suffix_mode = "auto"

        # Validate suffix_mode configuration
        valid_modes = {"file-suffix", "url-suffix", "auto", "replace"}
        if self.suffix_mode not in valid_modes:
            raise ExtensionError(
                f"Invalid llms_txt_suffix_mode: {self.suffix_mode!r}. "
                f"Must be one of {valid_modes}"
            )

        if app.builder and app.builder.name == "markdown":
            return

        if not app.builder or app.builder.name not in ["html", "dirhtml"]:
            logger.info(
                "llms.txt generation only works with HTML builders (html or dirhtml), skipping..."
            )
            return

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

    def combine_builds(self, app: Sphinx, exception: Union[Exception, None]):
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

        if self.md_build_process.returncode != 0:
            logger.error(
                f"Markdown build subprocess failed with return code {self.md_build_process.returncode},"
            )
            with open(self.md_build_logfile.name, encoding="utf-8") as logfile:
                logger.error(logfile.read())
            return

        try:
            # Copy markdown files to the main output directory
            self.copy_markdown_files()

            # Concatenate all markdown files into llms-full.txt
            if getattr(self.app.config, "llms_txt_full_build", True):
                self.build_llms_full_txt()

            # Create llms.txt from a custom source or the generated sitemap
            if getattr(self.app.config, "llms_txt_override_source", ""):
                self.build_custom_llms_txt()
            else:
                self.create_sitemap()
        finally:
            # Clean up temporary build directory
            if self.md_build_dir.exists():
                shutil.rmtree(self.md_build_dir)

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

    def _determine_suffix_targets(
        self, file_suffix_target: Path, url_suffix_target: Path
    ) -> tuple[dict[MarkdownLayout, Path], MarkdownLayout]:
        """Determine target file paths based on suffix mode.

        Returns:
            Tuple of (targets by layout, primary layout)
        """
        if self.suffix_mode == "file-suffix":
            return (
                {MarkdownLayout.FILE_SUFFIX: file_suffix_target},
                MarkdownLayout.FILE_SUFFIX,
            )
        elif self.suffix_mode == "url-suffix":
            return (
                {MarkdownLayout.URL_SUFFIX: url_suffix_target},
                MarkdownLayout.URL_SUFFIX,
            )
        elif self.suffix_mode == "auto":
            return (
                {
                    MarkdownLayout.FILE_SUFFIX: file_suffix_target,
                    MarkdownLayout.URL_SUFFIX: url_suffix_target,
                },
                MarkdownLayout.FILE_SUFFIX,
            )
        raise ExtensionError(
            f"Unhandled suffix mode in _determine_suffix_targets: {self.suffix_mode!r}"
        )

    def _get_dirhtml_root_index_targets(
        self, new_name: str
    ) -> tuple[dict[MarkdownLayout, Path], MarkdownLayout]:
        """Get targets for root index file in dirhtml builder."""
        if self.suffix_mode == "replace":
            replace_target = self.outdir / "index.md"
            return {MarkdownLayout.REPLACE: replace_target}, MarkdownLayout.REPLACE

        file_suffix_target = self.outdir / new_name  # index.html.md
        url_suffix_target = self.outdir / "index.md"  # index.md
        return self._determine_suffix_targets(file_suffix_target, url_suffix_target)

    def _get_dirhtml_nested_index_targets(
        self, rel_path: Path, new_name: str
    ) -> tuple[dict[MarkdownLayout, Path], MarkdownLayout]:
        """Get targets for nested index file in dirhtml builder (e.g., subdir/index.rst)."""
        if self.suffix_mode == "replace":
            replace_target = self.outdir / rel_path.parent / "index.md"
            return {MarkdownLayout.REPLACE: replace_target}, MarkdownLayout.REPLACE

        file_suffix_target = (
            self.outdir / rel_path.parent / new_name
        )  # subdir/index.html.md
        url_suffix_target = self.outdir / f"{rel_path.parent}.md"  # subdir.md
        return self._determine_suffix_targets(file_suffix_target, url_suffix_target)

    def _get_dirhtml_non_index_targets(
        self, rel_path: Path
    ) -> tuple[dict[MarkdownLayout, Path], MarkdownLayout]:
        """Get targets for non-index file in dirhtml builder."""
        if self.suffix_mode == "replace":
            replace_target = self.outdir / rel_path.with_suffix("") / "index.md"
            return {MarkdownLayout.REPLACE: replace_target}, MarkdownLayout.REPLACE

        file_suffix_target = self.outdir / rel_path.with_suffix("") / "index.html.md"
        url_suffix_target = self.outdir / rel_path.with_suffix(".md")
        return self._determine_suffix_targets(file_suffix_target, url_suffix_target)

    def _get_html_targets(
        self, rel_path: Path, base_name: str, new_name: str
    ) -> tuple[dict[MarkdownLayout, Path], MarkdownLayout]:
        """Get targets for html builder."""
        if self.suffix_mode == "replace":
            # Replace mode: foo.md (replace .html with .md)
            replace_target = (
                self.outdir / rel_path.parent / f"{base_name}.md"
                if rel_path.parent != Path(".")
                else self.outdir / f"{base_name}.md"
            )
            return {MarkdownLayout.REPLACE: replace_target}, MarkdownLayout.REPLACE

        # Default behavior: foo.html.md
        target_file = (
            self.outdir / rel_path.parent / new_name
            if rel_path.parent != Path(".")
            else self.outdir / new_name
        )
        return {MarkdownLayout.HTML: target_file}, MarkdownLayout.HTML

    def _get_target_paths(
        self, md_file: Path
    ) -> tuple[dict[MarkdownLayout, Path], MarkdownLayout]:
        """Determine target file locations based on builder and file type.

        Returns:
            Tuple of (targets by layout, primary layout)
        """
        rel_path = md_file.relative_to(self.md_build_dir)
        base_name = rel_path.stem
        new_name = f"{base_name}.html.md"

        if self.app.builder and self.app.builder.name == "dirhtml":
            # dirhtml builder has special handling for index files
            if base_name == "index" and rel_path.parent == Path("."):
                return self._get_dirhtml_root_index_targets(new_name)
            elif base_name == "index":
                return self._get_dirhtml_nested_index_targets(rel_path, new_name)
            else:
                return self._get_dirhtml_non_index_targets(rel_path)
        else:
            # Other builders (html) use simpler path structure
            return self._get_html_targets(rel_path, base_name, new_name)

    def _is_excluded(self, docname: str) -> bool:
        """Check whether a document is excluded from llms.txt and llms-full.txt."""
        exclude_patterns = getattr(self.app.config, "llms_txt_exclude", [])
        if exclude_patterns is None or isinstance(exclude_patterns, str):
            raise ExtensionError(
                "llms_txt_exclude must be an iterable of strings, not None or a string"
            )
        if not isinstance(exclude_patterns, Iterable):
            raise ExtensionError("llms_txt_exclude must be an iterable of strings")
        exclude_patterns = list(exclude_patterns)
        if not all(isinstance(pattern, str) for pattern in exclude_patterns):
            raise ExtensionError("llms_txt_exclude must be an iterable of strings")
        return any(patmatch(docname, pattern) for pattern in exclude_patterns)

    def copy_markdown_files(self):
        """Copy markdown files from build directory to output directory."""
        md_files = list(self.md_build_dir.rglob("*.md"))
        self.generated_markdown_files = []
        self._docname_by_output_file = {}
        num_excluded = 0
        self._markdown_file_by_docname = {}
        link_targets_path = self.md_build_dir / LINK_TARGETS_FILENAME
        self._link_target_by_token = json.loads(
            link_targets_path.read_text(encoding="utf-8")
        )

        for md_file in md_files:
            target_files, primary_layout = self._get_target_paths(md_file)
            primary_target = target_files[primary_layout]
            docname = self._get_docname_from_md_file(md_file)
            content = md_file.read_text(encoding="utf-8")
            self._markdown_file_by_docname[docname] = md_file

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
        markdown_file = self.md_build_dir / f"{docname}.md"
        return self._get_target_paths(markdown_file)

    def _markdown_http_base(self) -> str:
        return (
            self.app.config._raw_config.get("markdown_http_base")
            or getattr(self.app.config, "markdown_http_base", "")
        ).rstrip("/")

    def _materialize_links(
        self,
        content: str,
        source_docname: str,
        source_target: Optional[Path],
        target_layout: Optional[MarkdownLayout],
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
            try:
                target_file = target_files[selected_layout]
            except KeyError as exc:
                raise ExtensionError(
                    f"Document {target_docname!r} does not have the "
                    f"{selected_layout.value!r} Markdown layout"
                ) from exc
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

    def build_llms_full_txt(self):
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

    def create_sitemap(self):
        """Create a markdown sitemap in llms.txt."""
        llms_txt_path = self.outdir / "llms.txt"

        with open(llms_txt_path, "w", encoding="utf-8") as sitemap:
            # Write the title
            project_title = getattr(self.app.config, "project", "Documentation")
            sitemap.write(f"# {project_title}\n\n")

            # Add description
            for line in self.get_project_description().strip().split("\n"):
                sitemap.write(f"> {line}\n")
            sitemap.write("\n\n")

            # Add project details if available
            if hasattr(self.app.config, "copyright") and self.app.config.copyright:
                sitemap.write(f"{self.app.config.copyright}\n\n")

            # Write the main content section
            sitemap.write("## Pages\n\n")

            # Follow the Sphinx toctree, with orphaned documents sorted last.
            toctree_order = {
                docname: index
                for index, docname in enumerate(self.app.env.collect_relations())
            }
            sorted_files = sorted(
                self.generated_markdown_files,
                key=lambda path: (
                    toctree_order.get(
                        self._docname_by_output_file[path], len(toctree_order)
                    ),
                    self._docname_by_output_file[path],
                ),
            )

            # Read markdown_http_base from raw conf.py values, so it works
            # even when sphinx_markdown_builder is not listed in extensions
            # (it is only loaded in the markdown subprocess build).
            http_base = self._markdown_http_base()

            for md_file in sorted_files:
                # Extract title from the markdown file
                title = self.extract_title_from_markdown(md_file)

                # Create the URL based either on
                # - the relative path from output directory, or
                # - markdown_http_base + the relative path
                rel_path = md_file.relative_to(self.outdir)
                if http_base:
                    url = f"{http_base}/{rel_path}"
                else:
                    url = str(rel_path)

                # Write the link
                sitemap.write(
                    f"- [{title}]({url}): {self.get_page_description(md_file)}\n"
                )

            # Link to llms-full.txt when it was also generated
            if getattr(self.app.config, "llms_txt_full_build", True):
                if http_base:
                    full_url = f"{http_base}/llms-full.txt"
                else:
                    full_url = "llms-full.txt"
                sitemap.write(
                    f"\n---\n\nFor more comprehensive documentation, see [llms-full.txt]({full_url})\n"
                )

            logger.info(f"Created llms.txt sitemap: {llms_txt_path}")

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
        temporary_path: Optional[Path] = None
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
                content = f.read()
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
    app.add_config_value("llms_txt_full_build", True, "env")
    app.add_config_value("llms_txt_exclude", [], "env")
    app.add_config_value("llms_txt_override_source", "", "env")
    generator = MarkdownGenerator(app)
    generator.setup()

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
