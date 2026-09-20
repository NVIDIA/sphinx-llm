# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the sphinx_llm.txt module.
"""

from __future__ import annotations

import posixpath
import re
import shutil
import subprocess
import tempfile
from collections.abc import Generator, Iterable
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import docutils.nodes
import pytest
from sphinx.application import Sphinx
from sphinx.errors import ExtensionError

from sphinx_llm.markdown_builder import LINK_TARGETS_FILENAME
from sphinx_llm.txt import MarkdownGenerator, get_llms_txt_index_path


class _ToctreeLinkParser(HTMLParser):
    """Collect links from toctree wrappers in generated HTML."""

    def __init__(self):
        super().__init__()
        self._div_depth = 0
        self._toctree_depth = None
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "div":
            self._div_depth += 1
            classes = (attributes.get("class") or "").split()
            if self._toctree_depth is None and "toctree-wrapper" in classes:
                self._toctree_depth = self._div_depth
        elif tag == "a" and self._toctree_depth is not None:
            href = attributes.get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):
        if tag != "div":
            return
        if self._toctree_depth == self._div_depth:
            self._toctree_depth = None
        self._div_depth -= 1


class _DiscoveryLinkParser(HTMLParser):
    """Collect links from the head of generated HTML."""

    def __init__(self):
        super().__init__()
        self._in_head = False
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "head":
            self._in_head = True
        elif tag == "link" and self._in_head:
            self.links.append(dict(attrs))

    def handle_endtag(self, tag):
        if tag == "head":
            self._in_head = False


def _discovery_links(path: Path) -> list[dict[str, str]]:
    parser = _DiscoveryLinkParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.links


def _sitemap_section_entries(path: Path, heading: str) -> list[tuple[str, str]]:
    """Return one sitemap section's titles and targets in source order."""
    content = path.read_text(encoding="utf-8")
    section = re.search(
        rf"^## {re.escape(heading)}\n\n(?P<body>.*?)(?=^## |\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    assert section is not None
    return re.findall(
        r"^- \[([^]]+)]\(([^)]+)\):",
        section.group("body"),
        re.MULTILINE,
    )


def _sitemap_entries(path: Path) -> dict[str, str]:
    """Return the page section's titles and targets in source order."""
    content = path.read_text(encoding="utf-8")
    headings = [
        heading
        for heading in ("Pages", "Pages in this subsection")
        if f"## {heading}\n\n" in content
    ]
    assert len(headings) == 1
    return dict(_sitemap_section_entries(path, headings[0]))


def _build_sphinx(
    builder: str, confoverrides: dict | None = None
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Build Sphinx documentation into a temporary directory.

    Yields:
        Tuple of (Sphinx app, temporary build directory path, source directory path)
    """
    docs_source_dir = Path(__file__).parent.parent.parent.parent / "docs" / "source"
    overrides = {"llms_txt_build_parallel": True}
    if confoverrides:
        overrides.update(confoverrides)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        build_dir = temp_path / "build"
        doctree_dir = temp_path / "doctrees"

        app = Sphinx(
            srcdir=str(docs_source_dir),
            confdir=str(docs_source_dir),
            outdir=str(build_dir),
            doctreedir=str(doctree_dir),
            buildername=builder,
            warningiserror=False,
            freshenv=True,
            confoverrides=overrides,
        )
        app.build()
        yield app, build_dir, docs_source_dir


def assert_file_exists_with_content(path: Path) -> None:
    """Assert a file exists and is non-empty."""
    assert path.exists(), f"File not found: {path}"
    assert path.stat().st_size > 0, f"File is empty: {path}"


def get_non_index_rst_files(source_dir: Path) -> list[Path]:
    """Get all non-index RST files from source directory."""
    rst_files = [f for f in source_dir.rglob("*.rst") if f.stem != "index"]
    assert len(rst_files) > 0, "No non-index RST files found in source directory"
    return rst_files


@pytest.fixture(
    params=[
        ("html", True),
        ("dirhtml", True),
        ("html", False),
        ("dirhtml", False),
    ]
)
def sphinx_build(request) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Build Sphinx docs with different builder and parallel combinations."""
    builder, parallel = request.param
    yield from _build_sphinx(builder, {"llms_txt_build_parallel": parallel})


@pytest.fixture(
    params=[
        (builder, parallel, full_setting)
        for builder in ("html", "dirhtml")
        for parallel in (True, False)
        for full_setting in (None, False, True)
    ]
)
def sphinx_build_llms_full_matrix(
    request,
) -> Generator[tuple[Sphinx, Path, Path, bool | None], None, None]:
    """Build every supported llms-full setting and build-mode combination."""
    builder, parallel, full_setting = request.param
    overrides = {"llms_txt_build_parallel": parallel}
    if full_setting is not None:
        overrides["llms_txt_full_build"] = full_setting
    for app, build_dir, source_dir in _build_sphinx(builder, overrides):
        yield app, build_dir, source_dir, full_setting


@pytest.fixture
def sphinx_build_with_suffix_mode_config(
    request,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Build Sphinx docs with specific llms_txt_suffix_mode configuration."""
    builder, suffix_mode = request.param
    yield from _build_sphinx(builder, {"llms_txt_suffix_mode": suffix_mode})


@pytest.fixture
def llms_txt_override_build(
    builder: str,
    parallel: bool,
    override_source: str,
    suffix_mode: str | None,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Build docs with a custom llms.txt source and explicit build settings."""
    overrides = {
        "llms_txt_build_parallel": parallel,
        "llms_txt_full_build": True,
        "llms_txt_override_source": override_source,
    }
    if suffix_mode is not None:
        overrides["llms_txt_suffix_mode"] = suffix_mode
    yield from _build_sphinx(builder, overrides)


@pytest.fixture(params=[None, False], ids=["default", "disabled"])
def llms_txt_override_build_without_full(
    request,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Build overridden llms.txt with default or disabled full output."""
    overrides = {
        "llms_txt_build_parallel": False,
        "llms_txt_override_source": "index.rst",
    }
    if request.param is not None:
        overrides["llms_txt_full_build"] = request.param
    yield from _build_sphinx(
        "html",
        overrides,
    )


def test_markdown_generator_init(sphinx_build):
    """Test MarkdownGenerator initialization."""
    app, _, _ = sphinx_build
    generator = MarkdownGenerator(app)
    assert generator.app == app
    assert generator.md_build_logfile is None


def test_markdown_generator_setup(sphinx_build):
    """Test that setup connects to the correct events."""
    app, _, _ = sphinx_build
    generator = MarkdownGenerator(app)

    connect_calls = []
    original_connect = app.connect

    def record_connect(event, callback):
        connect_calls.append((event, callback))
        return original_connect(event, callback)

    app.connect = record_connect
    generator.setup()

    events = [call[0] for call in connect_calls]
    assert "builder-inited" in events


def test_combine_builds_with_exception(sphinx_build):
    """Test that combine_builds returns early on exception."""
    app, _, _ = sphinx_build
    generator = MarkdownGenerator(app)
    generator.combine_builds(app, Exception("fail"))


def test_combine_builds_terminates_orphan_subprocess_on_exception(sphinx_build):
    """Test that a failed primary build terminates a running markdown sub-build."""
    app, _, _ = sphinx_build
    generator = MarkdownGenerator(app)
    process = MagicMock()
    process.poll.return_value = None
    generator.md_build_process = process
    generator.md_build_dir = Path(app.outdir) / "_markdown_build_failure"
    generator.md_build_dir.mkdir()

    generator.combine_builds(app, Exception("primary build failed"))

    process.terminate.assert_called_once_with()
    process.wait.assert_called_once_with(timeout=10)
    process.kill.assert_not_called()
    assert not generator.md_build_dir.exists()


def test_combine_builds_kills_unresponsive_subprocess_on_exception(sphinx_build):
    """Test that an unresponsive markdown sub-build is killed and reaped."""
    app, _, _ = sphinx_build
    generator = MarkdownGenerator(app)
    process = MagicMock()
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired("sphinx", 10), None]
    generator.md_build_process = process

    generator.combine_builds(app, Exception("primary build failed"))

    process.terminate.assert_called_once_with()
    process.kill.assert_called_once_with()
    assert process.wait.call_args_list == [call(timeout=10), call()]


def test_build_markdown_files_skips_failed_primary_build(sphinx_build):
    """Test that a failed primary build does not start a sequential sub-build."""
    app, _, _ = sphinx_build
    generator = MarkdownGenerator(app)

    with patch("sphinx_llm.txt.subprocess.Popen") as popen:
        generator.build_markdown_files(app, Exception("primary build failed"))

    popen.assert_not_called()


def test_boolean_config_overrides_use_sphinx_cli_values(tmp_path):
    """Boolean overrides must use Sphinx's ``1`` and ``0`` CLI syntax."""
    app = SimpleNamespace(
        config=SimpleNamespace(overrides={"probe_true": True, "probe_false": False}),
        confdir=tmp_path / "conf",
        srcdir=tmp_path / "source",
        doctreedir=tmp_path / "doctrees",
        tags=(),
    )
    generator = MarkdownGenerator(app)
    generator.md_build_dir = tmp_path / "markdown"
    generator.parallel = True

    with (tmp_path / "markdown.log").open("w") as logfile:
        with (
            patch("sphinx_llm.txt.tempfile.NamedTemporaryFile", return_value=logfile),
            patch("sphinx_llm.txt.subprocess.Popen") as popen,
        ):
            generator.build_markdown_files()

    command = popen.call_args.args[0]
    assert command[-4:] == ["-D", "probe_true=1", "-D", "probe_false=0"]


def test_rst_files_have_corresponding_output_files(sphinx_build):
    """Test that all RST files have corresponding HTML and HTML.MD files in output."""
    app, build_dir, source_dir = sphinx_build

    rst_files = list(source_dir.rglob("*.rst"))
    assert len(rst_files) > 0, "No RST files found in source directory"

    for rst_file in rst_files:
        rel_path = rst_file.relative_to(source_dir)

        html_or_index = rel_path.stem == "index" or app.builder.name == "html"
        html_name = (
            rel_path.with_suffix(".html")
            if html_or_index
            else rel_path.with_suffix("") / "index.html"
        )
        html_md_name = html_name.with_suffix(".html.md")

        assert_file_exists_with_content(build_dir / html_name)
        assert_file_exists_with_content(build_dir / html_md_name)


def test_llms_txt_sitemap_links_exist(sphinx_build):
    """Test that all markdown pages listed in the llms.txt sitemap actually exist."""
    _, build_dir, _ = sphinx_build

    llms_txt_path = build_dir / "llms.txt"
    assert llms_txt_path.exists(), f"llms.txt not found: {llms_txt_path}"

    content = llms_txt_path.read_text(encoding="utf-8")

    url_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    matches = re.findall(url_pattern, content)
    assert len(matches) > 0, "No URLs found in llms.txt sitemap"

    for _, url in matches:
        # Limit the check to relative paths
        if not url.startswith(("http://", "https://")):
            assert_file_exists_with_content(build_dir / url)


def test_llms_txt_sitemap_follows_toctree_order(sphinx_build):
    """Test that pages in llms.txt follow the order in the HTML index."""
    _, build_dir, _ = sphinx_build

    parser = _ToctreeLinkParser()
    parser.feed((build_dir / "index.html").read_text(encoding="utf-8"))

    html_page_urls = []
    for href in parser.links:
        page_url = href.partition("#")[0]
        if not page_url or page_url.startswith(("http://", "https://")):
            continue
        if page_url not in html_page_urls:
            html_page_urls.append(page_url)

    assert html_page_urls, "No page links found in the HTML toctree"

    expected_markdown_urls = ["index.html.md"]
    for page_url in html_page_urls:
        if page_url.endswith("/"):
            page_url = f"{page_url}index.html"
        expected_markdown_urls.append(f"{page_url}.md")

    content = (build_dir / "llms.txt").read_text(encoding="utf-8")
    llms_page_urls = [
        match.group(1)
        for line in content.splitlines()
        if (match := re.match(r"^- \[[^]]+\]\(([^)]+)\):", line))
    ]

    assert llms_page_urls[: len(expected_markdown_urls)] == expected_markdown_urls


def test_llms_txt_does_not_use_anchor_tag_as_description(sphinx_build):
    """Test that anchor-only HTML tags are not used as page descriptions in llms.txt."""
    _, build_dir, _ = sphinx_build

    llms_txt_path = build_dir / "llms.txt"
    content = llms_txt_path.read_text(encoding="utf-8")

    assert (
        re.search(
            r"""^-\s+\[[^\]]*\]\([^)]*\):\s*<a\s+id=["'][^"']+["'][^>]*></a>""",
            content,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        is None
    )


@pytest.fixture(
    params=[
        ("html", "https://example.com/docs/", "append"),
        ("html", "https://example.com/docs/", "replace"),
        ("dirhtml", "https://example.com/docs/", "auto"),
        ("dirhtml", "https://example.com/docs/", "replace"),
        # A trailing slash on the base is optional.
        ("dirhtml", "https://example.com/docs", "url-suffix"),
    ]
)
def sphinx_build_with_http_base(
    request,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Build Sphinx docs with markdown_http_base set."""
    builder, http_base, suffix_mode = request.param
    yield from _build_sphinx(
        builder,
        {
            "markdown_http_base": http_base,
            "llms_txt_suffix_mode": suffix_mode,
            "llms_txt_full_build": True,
        },
    )


def test_llms_txt_sitemap_uses_markdown_http_base(sphinx_build_with_http_base):
    """Test that llms.txt links are absolute when markdown_http_base is configured."""
    app, build_dir, _ = sphinx_build_with_http_base

    http_base = getattr(app.config, "markdown_http_base", "").rstrip("/")

    llms_txt_path = build_dir / "llms.txt"
    assert llms_txt_path.exists(), f"llms.txt not found: {llms_txt_path}"

    content = llms_txt_path.read_text(encoding="utf-8")
    url_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    matches = re.findall(url_pattern, content)
    assert len(matches) > 0, "No URLs found in llms.txt sitemap"

    for _, url in matches:
        assert url.startswith(http_base), (
            f"Expected URL to start with {http_base!r}, got {url!r}"
        )
        # The path after the base should point to an existing markdown file
        rel = url[len(http_base) :].lstrip("/")
        assert_file_exists_with_content(build_dir / rel)


@pytest.mark.parametrize(
    "sphinx_build_with_suffix_mode_config",
    [
        ("dirhtml", "file-suffix"),
        ("dirhtml", "url-suffix"),
        ("dirhtml", "auto"),
        ("dirhtml", "both"),
    ],
    indirect=True,
)
def test_dirhtml_suffix_mode_configuration(sphinx_build_with_suffix_mode_config):
    """Test that llms_txt_suffix_mode configuration controls which markdown files are generated.

    Also tests that 'both' mode works as a backward-compatible alias for 'auto'.
    """
    app, build_dir, source_dir = sphinx_build_with_suffix_mode_config
    suffix_mode = app.config.llms_txt_suffix_mode

    # "both" is treated as "auto" internally
    effective_mode = "auto" if suffix_mode == "both" else suffix_mode

    rst_files = get_non_index_rst_files(source_dir)

    for rst_file in rst_files:
        rel_path = rst_file.relative_to(source_dir)

        file_suffix_md = build_dir / rel_path.with_suffix("") / "index.html.md"
        url_suffix_md = build_dir / rel_path.with_suffix(".md")

        if effective_mode == "file-suffix":
            assert_file_exists_with_content(file_suffix_md)
            assert not url_suffix_md.exists(), (
                f"URL-suffix file should not exist with suffix_mode='file-suffix': {url_suffix_md}"
            )
        elif effective_mode == "url-suffix":
            assert_file_exists_with_content(url_suffix_md)
            assert not file_suffix_md.exists(), (
                f"File-suffix file should not exist with suffix_mode='url-suffix': {file_suffix_md}"
            )
        elif effective_mode == "auto":
            assert_file_exists_with_content(file_suffix_md)
            assert_file_exists_with_content(url_suffix_md)

    # Root index should always be generated regardless of suffix mode
    index_file_suffix_md = build_dir / "index.html.md"
    index_url_suffix_md = build_dir / "index.md"

    if effective_mode == "file-suffix":
        assert_file_exists_with_content(index_file_suffix_md)
        assert not index_url_suffix_md.exists(), (
            "Root index url-suffix file should not exist with suffix_mode='file-suffix'"
        )
    elif effective_mode == "url-suffix":
        assert_file_exists_with_content(index_url_suffix_md)
        assert not index_file_suffix_md.exists(), (
            "Root index file-suffix file should not exist with suffix_mode='url-suffix'"
        )
    elif effective_mode == "auto":
        assert_file_exists_with_content(index_file_suffix_md)
        assert_file_exists_with_content(index_url_suffix_md)


@pytest.mark.parametrize(
    ("builder", "suffix_mode", "docname", "expected_paths"),
    [
        ("html", "append", "index", ("index.html.md",)),
        ("html", "replace", "guide/page", ("guide/page.md",)),
        ("html", "auto", "guide/page", ("guide/page.html.md", "guide/page.md")),
        ("html", "both", "guide/page", ("guide/page.html.md", "guide/page.md")),
        ("html", "file-suffix", "guide/page", ("guide/page.html.md",)),
        ("html", "url-suffix", "guide/page", ("guide/page.html.md",)),
        ("dirhtml", "append", "index", ("index.html.md",)),
        (
            "dirhtml",
            "append",
            "guide/index",
            ("guide.md", "guide/index.html.md"),
        ),
        (
            "dirhtml",
            "append",
            "guide/page",
            ("guide/page.md", "guide/page/index.html.md"),
        ),
        ("dirhtml", "replace", "index", ("index.md",)),
        ("dirhtml", "replace", "guide/index", ("guide/index.md",)),
        ("dirhtml", "replace", "guide/page", ("guide/page/index.md",)),
        ("dirhtml", "auto", "index", ("index.html.md", "index.md")),
        (
            "dirhtml",
            "auto",
            "guide/index",
            ("guide.md", "guide/index.html.md", "guide/index.md"),
        ),
        (
            "dirhtml",
            "both",
            "guide/page",
            ("guide/page.md", "guide/page/index.html.md", "guide/page/index.md"),
        ),
        ("dirhtml", "file-suffix", "guide/page", ("guide/page/index.html.md",)),
        ("dirhtml", "url-suffix", "guide/page", ("guide/page.md",)),
    ],
)
def test_suffix_mode_path_planner_transforms_docname(
    tmp_path: Path,
    builder: str,
    suffix_mode: str,
    docname: str,
    expected_paths: tuple[str, ...],
):
    generator = MarkdownGenerator(
        SimpleNamespace(builder=SimpleNamespace(name=builder))
    )
    generator.outdir = tmp_path / "output"
    generator.md_build_dir = tmp_path / "markdown"
    generator.suffix_mode = suffix_mode

    targets, _ = generator._target_paths_for_docname(docname)
    actual_paths = tuple(
        sorted(
            path.relative_to(generator.outdir).as_posix() for path in targets.values()
        )
    )

    assert actual_paths == tuple(sorted(expected_paths))


@pytest.mark.parametrize(
    ("builder", "suffix_mode", "canonical_layout"),
    [
        ("html", "append", "append"),
        ("html", "replace", "replace"),
        ("html", "auto", "append"),
        ("html", "both", "append"),
        ("html", "file-suffix", "append"),
        ("html", "url-suffix", "append"),
        ("dirhtml", "append", "append"),
        ("dirhtml", "replace", "replace"),
        ("dirhtml", "auto", "append"),
        ("dirhtml", "both", "append"),
        ("dirhtml", "file-suffix", "append"),
        ("dirhtml", "url-suffix", "append-no-slash"),
    ],
)
def test_suffix_mode_path_planner_selects_canonical_layout(
    tmp_path: Path,
    builder: str,
    suffix_mode: str,
    canonical_layout: str,
):
    generator = MarkdownGenerator(
        SimpleNamespace(builder=SimpleNamespace(name=builder))
    )
    generator.outdir = tmp_path / "output"
    generator.md_build_dir = tmp_path / "markdown"
    generator.suffix_mode = suffix_mode

    targets, selected_layout = generator._target_paths_for_docname("guide/page")

    assert selected_layout.value == canonical_layout
    assert targets[selected_layout].is_relative_to(generator.outdir)


@pytest.mark.parametrize(
    ("builder", "suffix_mode", "docname", "expected_target"),
    [
        ("html", "append", "api/v1.0", "api/v1.0.html.md"),
        ("html", "replace", "api/v1.0", "api/v1.0.md"),
        ("dirhtml", "append", "api/v1.0", "api/v1.0/index.html.md"),
        ("dirhtml", "replace", "api/v1.0", "api/v1.0/index.md"),
        ("dirhtml", "url-suffix", "api/v1.0", "api/v1.0.md"),
        ("dirhtml", "url-suffix", "api/v1.0/index", "api/v1.0.md"),
    ],
)
def test_suffix_mode_path_planner_preserves_dotted_docnames(
    tmp_path: Path,
    builder: str,
    suffix_mode: str,
    docname: str,
    expected_target: str,
):
    generator = MarkdownGenerator(
        SimpleNamespace(builder=SimpleNamespace(name=builder))
    )
    generator.outdir = tmp_path / "output"
    generator.md_build_dir = tmp_path / "markdown"
    generator.suffix_mode = suffix_mode

    targets, canonical_layout = generator._target_paths_for_docname(docname)

    assert (
        targets[canonical_layout].relative_to(generator.outdir).as_posix()
        == expected_target
    )


@pytest.mark.parametrize(
    ("builder", "suffix_mode", "expected_paths", "canonical_paths"),
    [
        (
            "html",
            "append",
            ("index.html.md", "guide/index.html.md", "guide/page.html.md"),
            ("index.html.md", "guide/index.html.md", "guide/page.html.md"),
        ),
        (
            "html",
            "replace",
            ("index.md", "guide/index.md", "guide/page.md"),
            ("index.md", "guide/index.md", "guide/page.md"),
        ),
        (
            "html",
            "auto",
            (
                "index.html.md",
                "index.md",
                "guide/index.html.md",
                "guide/index.md",
                "guide/page.html.md",
                "guide/page.md",
            ),
            ("index.html.md", "guide/index.html.md", "guide/page.html.md"),
        ),
        (
            "html",
            "both",
            (
                "index.html.md",
                "index.md",
                "guide/index.html.md",
                "guide/index.md",
                "guide/page.html.md",
                "guide/page.md",
            ),
            ("index.html.md", "guide/index.html.md", "guide/page.html.md"),
        ),
        (
            "html",
            "file-suffix",
            ("index.html.md", "guide/index.html.md", "guide/page.html.md"),
            ("index.html.md", "guide/index.html.md", "guide/page.html.md"),
        ),
        (
            "html",
            "url-suffix",
            ("index.html.md", "guide/index.html.md", "guide/page.html.md"),
            ("index.html.md", "guide/index.html.md", "guide/page.html.md"),
        ),
        (
            "dirhtml",
            "append",
            (
                "index.html.md",
                "guide.md",
                "guide/index.html.md",
                "guide/page.md",
                "guide/page/index.html.md",
            ),
            ("index.html.md", "guide/index.html.md", "guide/page/index.html.md"),
        ),
        (
            "dirhtml",
            "replace",
            ("index.md", "guide/index.md", "guide/page/index.md"),
            ("index.md", "guide/index.md", "guide/page/index.md"),
        ),
        (
            "dirhtml",
            "auto",
            (
                "index.html.md",
                "index.md",
                "guide.md",
                "guide/index.html.md",
                "guide/index.md",
                "guide/page.md",
                "guide/page/index.html.md",
                "guide/page/index.md",
            ),
            ("index.html.md", "guide/index.html.md", "guide/page/index.html.md"),
        ),
        (
            "dirhtml",
            "both",
            (
                "index.html.md",
                "index.md",
                "guide.md",
                "guide/index.html.md",
                "guide/index.md",
                "guide/page.md",
                "guide/page/index.html.md",
                "guide/page/index.md",
            ),
            ("index.html.md", "guide/index.html.md", "guide/page/index.html.md"),
        ),
        (
            "dirhtml",
            "file-suffix",
            ("index.html.md", "guide/index.html.md", "guide/page/index.html.md"),
            ("index.html.md", "guide/index.html.md", "guide/page/index.html.md"),
        ),
        (
            "dirhtml",
            "url-suffix",
            ("index.md", "guide.md", "guide/page.md"),
            ("index.md", "guide.md", "guide/page.md"),
        ),
    ],
)
def test_suffix_mode_build_publishes_exact_artifacts_and_one_entry_per_page(
    tmp_path: Path,
    builder: str,
    suffix_mode: str,
    expected_paths: tuple[str, ...],
    canonical_paths: tuple[str, ...],
):
    source_dir = tmp_path / "source"
    guide_dir = source_dir / "guide"
    guide_dir.mkdir(parents=True)
    (source_dir / "conf.py").write_text(
        'extensions = ["sphinx_llm.txt"]\n'
        'project = "Suffix matrix"\n'
        'root_doc = "index"\n'
        "llms_txt_build_parallel = False\n"
        "llms_txt_full_build = True\n"
        f'llms_txt_suffix_mode = "{suffix_mode}"\n',
        encoding="utf-8",
    )
    (source_dir / "index.rst").write_text(
        "Index\n=====\n\n.. toctree::\n\n   guide/index\n   guide/page\n",
        encoding="utf-8",
    )
    (guide_dir / "index.rst").write_text(
        "Guide\n=====\n\nSee :doc:`Page <page>`.\n", encoding="utf-8"
    )
    (guide_dir / "page.rst").write_text(
        "Page\n====\n\nSee :doc:`Guide <index>`.\n", encoding="utf-8"
    )
    output_dir = tmp_path / "output"
    app = Sphinx(
        srcdir=str(source_dir),
        confdir=str(source_dir),
        outdir=str(output_dir),
        doctreedir=str(tmp_path / "doctrees"),
        buildername=builder,
        warningiserror=False,
        freshenv=True,
    )
    app.build()

    actual_paths = {
        path.relative_to(output_dir).as_posix() for path in output_dir.rglob("*.md")
    }
    assert actual_paths == set(expected_paths)

    sitemap = (output_dir / "llms.txt").read_text(encoding="utf-8")
    sitemap_paths = tuple(
        match.group(1)
        for line in sitemap.splitlines()
        if (match := re.match(r"^- \[[^]]+\]\(([^)]+)\):", line))
        and match.group(1) != "llms-full.txt"
    )
    assert sitemap_paths == canonical_paths
    assert len(sitemap_paths) == 3

    llms_full = (output_dir / "llms-full.txt").read_text(encoding="utf-8")
    for relative_path in canonical_paths:
        assert f"# {relative_path}\n" in llms_full
    for relative_path in set(expected_paths) - set(canonical_paths):
        assert f"# {relative_path}\n" not in llms_full


def test_suffix_modes_preserve_unowned_output_files(tmp_path: Path):
    """Candidate paths not owned by sphinx-llm are never removed."""
    source_dir = tmp_path / "source"
    guide_dir = source_dir / "guide"
    extra_dir = source_dir / "extra" / "guide" / "page"
    guide_dir.mkdir(parents=True)
    extra_dir.mkdir(parents=True)
    (source_dir / "conf.py").write_text(
        'extensions = ["sphinx_llm.txt"]\n'
        'project = "Unowned output"\n'
        'root_doc = "index"\n'
        "llms_txt_build_parallel = False\n"
        'llms_txt_suffix_mode = "append"\n'
        'html_extra_path = ["extra"]\n',
        encoding="utf-8",
    )
    (source_dir / "index.rst").write_text(
        "Index\n=====\n\n.. toctree::\n\n   guide/page\n", encoding="utf-8"
    )
    (guide_dir / "page.rst").write_text("Page\n====\n", encoding="utf-8")
    sentinel = "User-supplied suffix-like asset\n"
    (extra_dir / "index.md").write_text(sentinel, encoding="utf-8")
    output_dir = tmp_path / "output"
    app = Sphinx(
        srcdir=str(source_dir),
        confdir=str(source_dir),
        outdir=str(output_dir),
        doctreedir=str(tmp_path / "doctrees"),
        buildername="dirhtml",
        warningiserror=False,
        freshenv=True,
    )
    app.build()

    assert (output_dir / "guide/page.md").is_file()
    assert (output_dir / "guide/page/index.html.md").is_file()
    assert (output_dir / "guide/page/index.md").read_text(encoding="utf-8") == sentinel


def test_selected_markdown_output_paths_are_extension_owned(tmp_path: Path):
    """Generated Markdown replaces an extra asset at a selected output path."""
    source_dir = tmp_path / "source"
    extra_dir = source_dir / "extra" / "guide"
    extra_dir.mkdir(parents=True)
    (source_dir / "conf.py").write_text(
        'extensions = ["sphinx_llm.txt"]\n'
        'project = "Selected output"\n'
        'root_doc = "index"\n'
        "llms_txt_build_parallel = False\n"
        'llms_txt_suffix_mode = "append"\n'
        'html_extra_path = ["extra"]\n',
        encoding="utf-8",
    )
    (source_dir / "index.rst").write_text(
        "Index\n=====\n\n.. toctree::\n\n   guide/page\n", encoding="utf-8"
    )
    (source_dir / "guide").mkdir()
    (source_dir / "guide/page.rst").write_text(
        "Generated page\n==============\n", encoding="utf-8"
    )
    sentinel = "User-supplied selected-path asset\n"
    (extra_dir / "page.md").write_text(sentinel, encoding="utf-8")
    output_dir = tmp_path / "output"

    app = Sphinx(
        srcdir=str(source_dir),
        confdir=str(source_dir),
        outdir=str(output_dir),
        doctreedir=str(tmp_path / "doctrees"),
        buildername="dirhtml",
        warningiserror=False,
        freshenv=True,
    )
    app.build()

    generated = (output_dir / "guide/page.md").read_text(encoding="utf-8")
    assert generated != sentinel
    assert "# Generated page" in generated


@pytest.mark.parametrize(
    "suffix_mode",
    [
        "append",
        "replace",
        "auto",
        "file-suffix",
        "url-suffix",
        "both",
    ],
)
def test_dirhtml_rejects_colliding_published_markdown_targets(
    tmp_path: Path, suffix_mode: str
):
    """Published layouts cannot silently overwrite another document."""
    generator = MarkdownGenerator(
        SimpleNamespace(
            builder=SimpleNamespace(name="dirhtml"),
            config=SimpleNamespace(llms_txt_exclude=[]),
        )
    )
    generator.outdir = tmp_path / "output"
    generator.md_build_dir = tmp_path / "markdown"
    generator.md_build_dir.mkdir()
    generator.suffix_mode = suffix_mode
    (generator.md_build_dir / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (generator.md_build_dir / "guide").mkdir()
    (generator.md_build_dir / "guide/index.md").write_text(
        "# Guide index\n", encoding="utf-8"
    )
    (generator.md_build_dir / LINK_TARGETS_FILENAME).write_text("{}", encoding="utf-8")

    with pytest.raises(ExtensionError, match="same published Markdown path"):
        generator.copy_markdown_files()
    assert not generator.outdir.exists()


@pytest.mark.parametrize(
    ("suffix_mode", "page_links", "canonical_page", "canonical_target"),
    [
        pytest.param(
            "append",
            {
                "guide/page.md": "target.md",
                "guide/page/index.html.md": "../target/index.html.md",
            },
            "guide/page/index.html.md",
            "guide/target/index.html.md",
            id="append",
        ),
        pytest.param(
            "replace",
            {"guide/page/index.md": "../target/index.md"},
            "guide/page/index.md",
            "guide/target/index.md",
            id="replace",
        ),
        pytest.param(
            "url-suffix",
            {"guide/page.md": "target.md"},
            "guide/page.md",
            "guide/target.md",
            id="url-suffix",
        ),
        pytest.param(
            "auto",
            {
                "guide/page/index.html.md": "../target/index.html.md",
                "guide/page.md": "target.md",
                "guide/page/index.md": "../target/index.md",
            },
            "guide/page/index.html.md",
            "guide/target/index.html.md",
            id="auto",
        ),
    ],
)
def test_dirhtml_links_match_published_locations(
    tmp_path: Path,
    suffix_mode: str,
    page_links: dict[str, str],
    canonical_page: str,
    canonical_target: str,
):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    guide_dir = source_dir / "guide"
    guide_dir.mkdir(parents=True)

    (source_dir / "conf.py").write_text(
        'extensions = ["sphinx_llm.txt"]\n'
        'project = "Link test"\n'
        'root_doc = "index"\n'
        "llms_txt_build_parallel = False\n"
        f'llms_txt_suffix_mode = "{suffix_mode}"\n'
        "llms_txt_full_build = True\n"
        "markdown_anchor_sections = True\n",
        encoding="utf-8",
    )
    (source_dir / "index.rst").write_text(
        "Index\n=====\n\n.. toctree::\n\n   guide/page\n   guide/target\n",
        encoding="utf-8",
    )
    (guide_dir / "page.rst").write_text(
        "Page\n"
        "====\n\n"
        "See :doc:`Target <target>`.\n\n"
        ".. _page-details:\n\n"
        "Details\n"
        "-------\n\n"
        "See :ref:`Details <page-details>`.\n\n"
        "The URI ``sphinx-llm:example`` is literal content.\n\n"
        ".. code-block:: text\n\n"
        "   sphinx-llm:example\n\n"
        "`Custom scheme <sphinx-llm:example>`_\n",
        encoding="utf-8",
    )
    (guide_dir / "target.rst").write_text(
        "Target\n======\n",
        encoding="utf-8",
    )

    app = Sphinx(
        srcdir=str(source_dir),
        confdir=str(source_dir),
        outdir=str(output_dir),
        doctreedir=str(tmp_path / "doctrees"),
        buildername="dirhtml",
        warningiserror=False,
        freshenv=True,
    )
    app.build()
    assert "llms-markdown" not in app.registry.builders

    page_contents = []
    for page_path, target_path in page_links.items():
        content = (output_dir / page_path).read_text(encoding="utf-8")
        assert f"[Target]({target_path})" in content
        assert "[Details](#page-details)" in content
        page_contents.append(content)

    llms_full = (output_dir / "llms-full.txt").read_text(encoding="utf-8")
    assert f"# {canonical_page}" in llms_full
    assert f"[Target]({canonical_target})" in llms_full
    assert f"[Details]({canonical_page}#page-details)" in llms_full
    for content in (*page_contents, llms_full):
        assert "`sphinx-llm:example`" in content
        assert "[Custom scheme](sphinx-llm:example)" in content
        assert "sphinx-llm:example\n```" in content
        assert re.search(r"sphinx-llm:[0-9a-f]{32}", content) is None


@pytest.mark.parametrize("suffix_mode", ["append", "auto"])
def test_dirhtml_no_slash_artifact_links_to_root_canonical_target(
    tmp_path: Path, suffix_mode: str
):
    source_dir = tmp_path / "source"
    guide_dir = source_dir / "guide"
    guide_dir.mkdir(parents=True)
    (source_dir / "conf.py").write_text(
        'extensions = ["sphinx_llm.txt"]\n'
        'project = "Root link test"\n'
        'root_doc = "index"\n'
        "llms_txt_build_parallel = False\n"
        f'llms_txt_suffix_mode = "{suffix_mode}"\n',
        encoding="utf-8",
    )
    (source_dir / "index.rst").write_text(
        "Index\n=====\n\n.. toctree::\n\n   guide/page\n", encoding="utf-8"
    )
    (guide_dir / "page.rst").write_text(
        "Page\n====\n\nSee :doc:`Home </index>`.\n", encoding="utf-8"
    )

    output_dir = tmp_path / "output"
    app = Sphinx(
        srcdir=str(source_dir),
        confdir=str(source_dir),
        outdir=str(output_dir),
        doctreedir=str(tmp_path / "doctrees"),
        buildername="dirhtml",
        warningiserror=False,
        freshenv=True,
    )
    app.build()

    content = (output_dir / "guide/page.md").read_text(encoding="utf-8")
    assert "[Home](../index.html.md)" in content


@pytest.mark.parametrize(
    "parallel",
    [
        pytest.param(True, id="parallel"),
        pytest.param(False, id="sequential"),
    ],
)
@pytest.mark.parametrize(
    (
        "builder",
        "override_source",
        "suffix_mode",
        "expected_page_paths",
        "expected_link",
    ),
    [
        pytest.param(
            "html",
            "index.rst",
            None,
            ("index.html.md", "index.md", "test.html.md", "test.md"),
            "test.html.md",
            id="html",
        ),
        pytest.param(
            "html",
            "index.rst",
            "replace",
            ("index.md", "test.md"),
            "test.md",
            id="html-replace",
        ),
        pytest.param(
            "dirhtml",
            "index",
            "auto",
            (
                "index.html.md",
                "index.md",
                "test.md",
                "test/index.html.md",
                "test/index.md",
            ),
            "test/index.html.md",
            id="dirhtml-auto",
        ),
        pytest.param(
            "dirhtml",
            "index",
            "append",
            ("index.html.md", "test.md", "test/index.html.md"),
            "test/index.html.md",
            id="dirhtml-append",
        ),
        pytest.param(
            "dirhtml",
            "index",
            "both",
            (
                "index.html.md",
                "index.md",
                "test.md",
                "test/index.html.md",
                "test/index.md",
            ),
            "test/index.html.md",
            id="dirhtml-both",
        ),
        pytest.param(
            "dirhtml",
            "index",
            "file-suffix",
            ("index.html.md", "test/index.html.md"),
            "test/index.html.md",
            id="dirhtml-file-suffix",
        ),
        pytest.param(
            "dirhtml",
            "index",
            "url-suffix",
            ("index.md", "test.md"),
            "test.md",
            id="dirhtml-url-suffix",
        ),
        pytest.param(
            "dirhtml",
            "index",
            "replace",
            ("index.md", "test/index.md"),
            "test/index.md",
            id="dirhtml-replace",
        ),
    ],
)
def test_llms_txt_override_source_preserves_other_outputs(
    llms_txt_override_build,
    expected_page_paths: tuple[str, ...],
    expected_link: str,
):
    """A rendered custom source replaces only the generated llms.txt sitemap."""
    _, output_dir, _ = llms_txt_override_build

    llms_txt = (output_dir / "llms.txt").read_text(encoding="utf-8")
    assert "# Welcome to sphinx-llm" in llms_txt
    assert f"]({expected_link})" in llms_txt
    assert "## Pages" not in llms_txt
    assert "llms-full.txt" not in llms_txt

    for page_path in expected_page_paths:
        assert_file_exists_with_content(output_dir / page_path)

    llms_full = output_dir / "llms-full.txt"
    assert_file_exists_with_content(llms_full)
    assert "# Welcome to sphinx-llm" in llms_full.read_text(encoding="utf-8")


def test_llms_txt_override_source_respects_full_build(
    llms_txt_override_build_without_full,
):
    """A custom llms.txt does not force llms-full.txt generation."""
    _, output_dir, _ = llms_txt_override_build_without_full

    llms_txt = (output_dir / "llms.txt").read_text(encoding="utf-8")
    assert "# Welcome to sphinx-llm" in llms_txt
    assert "## Pages" not in llms_txt
    assert "llms-full.txt" not in llms_txt
    assert not (output_dir / "llms-full.txt").exists()


def test_missing_llms_txt_override_source_raises_error(tmp_path: Path):
    """A configured source must identify a rendered Sphinx document."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "conf.py").write_text(
        'extensions = ["sphinx_llm.txt"]\n'
        'project = "Custom llms.txt test"\n'
        "llms_txt_build_parallel = False\n"
        'llms_txt_override_source = "missing.rst"\n',
        encoding="utf-8",
    )
    (source_dir / "index.rst").write_text("Index\n=====\n", encoding="utf-8")

    app = Sphinx(
        srcdir=str(source_dir),
        confdir=str(source_dir),
        outdir=str(tmp_path / "output"),
        doctreedir=str(tmp_path / "doctrees"),
        buildername="html",
        warningiserror=False,
        freshenv=True,
    )

    with pytest.raises(
        ExtensionError, match=r"llms_txt_override_source 'missing\.rst'"
    ):
        app.build()


@pytest.mark.parametrize(
    "sphinx_build_with_suffix_mode_config",
    [("html", "replace"), ("dirhtml", "replace")],
    indirect=True,
)
def test_replace_suffix_mode(sphinx_build_with_suffix_mode_config):
    """Test that replace mode replaces .html with .md for both html and dirhtml builders."""
    app, build_dir, source_dir = sphinx_build_with_suffix_mode_config

    rst_files = list(source_dir.rglob("*.rst"))
    assert len(rst_files) > 0, "No RST files found in source directory"

    for rst_file in rst_files:
        rel_path = rst_file.relative_to(source_dir)

        if app.builder.name == "dirhtml":
            if rel_path.stem == "index":
                if rel_path.parent == Path("."):
                    replace_md = build_dir / "index.md"
                else:
                    replace_md = build_dir / rel_path.parent / "index.md"
            else:
                replace_md = build_dir / rel_path.with_suffix("") / "index.md"
        else:
            replace_md = build_dir / rel_path.with_suffix(".md")

        assert_file_exists_with_content(replace_md)

        # Ensure .html.md files do NOT exist with replace mode
        if app.builder.name == "html":
            html_md = build_dir / rel_path.with_suffix(".html.md")
        elif rel_path.stem == "index":
            if rel_path.parent == Path("."):
                html_md = build_dir / "index.html.md"
            else:
                html_md = build_dir / rel_path.parent / "index.html.md"
        else:
            html_md = build_dir / rel_path.with_suffix("") / "index.html.md"

        assert not html_md.exists(), (
            f"File with .html.md extension should not exist in replace mode: {html_md}"
        )


@pytest.mark.parametrize("suffix_mode", ["invalid-mode", "legacy-url"])
def test_invalid_suffix_mode_raises_error(suffix_mode: str):
    """Test that invalid llms_txt_suffix_mode values raise an error."""
    with pytest.raises(ExtensionError, match="Invalid llms_txt_suffix_mode"):
        list(_build_sphinx("dirhtml", {"llms_txt_suffix_mode": suffix_mode}))


@pytest.mark.parametrize("exclude_patterns", [None, "apples", ["**", None], [1]])
def test_invalid_exclude_raises_error(exclude_patterns):
    """Test that llms_txt_exclude must be an iterable of document patterns."""
    generator = MarkdownGenerator(
        SimpleNamespace(config=SimpleNamespace(llms_txt_exclude=exclude_patterns))
    )
    with pytest.raises(ExtensionError, match="llms_txt_exclude must be an iterable"):
        generator._is_excluded("apples")


@pytest.mark.parametrize("builder", ["html", "dirhtml"])
def test_llms_txt_disabled(builder):
    """Test that setting llms_txt_enabled=False prevents the extension from running.

    Spies on MarkdownGenerator.combine_builds. If the early return
    in build_llms_txt happens, combine_builds is never connected
    to build-finished, and its call count stays at zero.
    """
    docs_source_dir = Path(__file__).parent.parent.parent.parent / "docs" / "source"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        with patch.object(MarkdownGenerator, "combine_builds") as mock_combine:
            app = Sphinx(
                srcdir=str(docs_source_dir),
                confdir=str(docs_source_dir),
                outdir=str(tmp_path / "build"),
                doctreedir=str(tmp_path / "doctrees"),
                buildername=builder,
                warningiserror=False,
                freshenv=True,
                confoverrides={
                    "llms_txt_build_parallel": False,
                    "llms_txt_enabled": False,
                },
            )
            app.build()

        assert mock_combine.call_count == 0, (
            f"combine_builds was called {mock_combine.call_count} time(s) "
            "despite llms_txt_enabled=False — extension ran when it should not have"
        )


@pytest.mark.parametrize(
    ("builder", "suffix_mode", "parallel", "root_markdown", "nested_markdown"),
    [
        pytest.param(
            "html",
            "auto",
            True,
            "index.html.md",
            "example.html.md",
            id="html-auto-parallel",
        ),
        pytest.param(
            "html",
            "append",
            False,
            "index.html.md",
            "example.html.md",
            id="html-append-sequential",
        ),
        pytest.param(
            "html",
            "replace",
            False,
            "index.md",
            "example.md",
            id="html-replace-sequential",
        ),
        pytest.param(
            "dirhtml",
            "auto",
            True,
            "index.html.md",
            "index.html.md",
            id="dirhtml-auto",
        ),
        pytest.param(
            "dirhtml",
            "append",
            False,
            "index.html.md",
            "index.html.md",
            id="dirhtml-append",
        ),
        pytest.param(
            "dirhtml",
            "both",
            False,
            "index.html.md",
            "index.html.md",
            id="dirhtml-both",
        ),
        pytest.param(
            "dirhtml",
            "file-suffix",
            True,
            "index.html.md",
            "index.html.md",
            id="dirhtml-file-suffix",
        ),
        pytest.param(
            "dirhtml",
            "url-suffix",
            False,
            "index.md",
            "../example.md",
            id="dirhtml-url-suffix",
        ),
        pytest.param(
            "dirhtml",
            "replace",
            True,
            "index.md",
            "index.md",
            id="dirhtml-replace",
        ),
    ],
)
def test_html_pages_have_discovery_metadata(
    builder: str,
    suffix_mode: str,
    parallel: bool,
    root_markdown: str,
    nested_markdown: str,
):
    """Every HTML page discovers its canonical Markdown and covering llms.txt."""
    build = _build_sphinx(
        builder,
        {
            "llms_txt_suffix_mode": suffix_mode,
            "llms_txt_build_parallel": parallel,
        },
    )
    _, build_dir, _ = next(build)
    pages = {
        build_dir / "index.html": (root_markdown, "llms.txt"),
        (
            build_dir / "nested/example.html"
            if builder == "html"
            else build_dir / "nested/example/index.html"
        ): (
            nested_markdown,
            "llms.txt",
        ),
    }

    for html_path, (expected_markdown, expected_llms_txt) in pages.items():
        links = _discovery_links(html_path)
        alternates = [
            link
            for link in links
            if link.get("rel") == "alternate" and link.get("type") == "text/markdown"
        ]
        describedby = [link for link in links if link.get("rel") == "describedby"]

        assert alternates == [
            {
                "rel": "alternate",
                "type": "text/markdown",
                "href": expected_markdown,
            }
        ]
        assert describedby == [{"rel": "describedby", "href": expected_llms_txt}]
        for link in (*alternates, *describedby):
            target = html_path.parent / link["href"]
            assert_file_exists_with_content(target)


@pytest.mark.parametrize(
    ("builder", "suffix_mode", "parallel", "index_target", "example_target"),
    [
        ("html", "auto", False, "index.html.md", "example.html.md"),
        ("html", "replace", True, "index.md", "example.md"),
        ("dirhtml", "auto", True, "index.html.md", "example/index.html.md"),
        (
            "dirhtml",
            "file-suffix",
            False,
            "index.html.md",
            "example/index.html.md",
        ),
        ("dirhtml", "url-suffix", True, "../nested.md", "example.md"),
        ("dirhtml", "replace", False, "index.md", "example/index.md"),
    ],
)
def test_nested_indexes_use_existing_docs_fixture_and_canonical_targets(
    builder: str,
    suffix_mode: str,
    parallel: bool,
    index_target: str,
    example_target: str,
) -> None:
    """Nested scopes reuse canonical Markdown targets from the shared fixture."""
    build = _build_sphinx(
        builder,
        {
            "llms_txt_build_parallel": parallel,
            "llms_txt_exclude": ["nested/orphan"],
            "llms_txt_suffix_mode": suffix_mode,
        },
    )
    app, build_dir, _ = next(build)

    nested_entries = _sitemap_entries(build_dir / "nested" / "llms.txt")
    deeper_entries = _sitemap_entries(build_dir / "nested" / "deeper" / "llms.txt")
    assert _sitemap_section_entries(build_dir / "nested" / "llms.txt", "Optional") == [
        ("Top-level llms.txt", "../llms.txt")
    ]
    assert _sitemap_section_entries(
        build_dir / "nested" / "deeper" / "llms.txt", "Optional"
    ) == [("Top-level llms.txt", "../../llms.txt")]
    assert list(nested_entries) == ["Nested examples", "Example", "Deeper Example"]
    assert nested_entries["Nested examples"] == index_target
    assert deeper_entries == {"Deeper Example": example_target}
    assert nested_entries["Example"] == example_target
    assert (build_dir / "nested" / example_target).is_file()
    orphan_target = example_target.replace("example", "orphan", 1)
    assert (build_dir / "nested" / orphan_target).is_file()
    assert "Nested Orphan" not in nested_entries
    assert get_llms_txt_index_path(app, "nested/index") == PurePosixPath(
        "nested/llms.txt"
    )
    expected_deeper_index = (
        PurePosixPath("nested/deeper/llms.txt")
        if builder == "html"
        else PurePosixPath("nested/deeper/example/llms.txt")
    )
    assert (
        get_llms_txt_index_path(app, "nested/deeper/example") == expected_deeper_index
    )

    expected_indexes = {
        "llms.txt",
        "nested/llms.txt",
        "nested/deeper/llms.txt",
    }
    if builder == "dirhtml":
        expected_indexes.update(
            {
                "apples/llms.txt",
                "meta_example/llms.txt",
                "nested/deeper/example/llms.txt",
                "nested/example/llms.txt",
                "test/llms.txt",
            }
        )
    assert {
        path.relative_to(build_dir).as_posix() for path in build_dir.rglob("llms.txt")
    } == expected_indexes
    for nested_index in expected_indexes - {"llms.txt"}:
        assert "[llms-full.txt](" not in (build_dir / nested_index).read_text(
            encoding="utf-8"
        )


@pytest.mark.parametrize("builder", ["html", "dirhtml"])
def test_nested_indexes_identify_subsection_and_link_top_level(builder: str) -> None:
    """Every scoped index identifies its scope and links back to the root index."""
    build = _build_sphinx(builder, {"llms_txt_build_parallel": False})
    _, build_dir, _ = next(build)

    root_content = (build_dir / "llms.txt").read_text(encoding="utf-8")
    assert "## Pages\n\n" in root_content
    assert "## Pages in this subsection" not in root_content
    assert "[Top-level llms.txt](" not in root_content

    for nested_index in build_dir.rglob("llms.txt"):
        if nested_index == build_dir / "llms.txt":
            continue
        content = nested_index.read_text(encoding="utf-8")
        relative_root = posixpath.relpath(
            "llms.txt",
            start=nested_index.parent.relative_to(build_dir).as_posix(),
        )
        assert "## Pages in this subsection\n\n" in content
        assert content.count("## Pages in this subsection") == 1
        assert content.count("## Optional") == 1
        assert content.count("[Top-level llms.txt](") == 1
        assert _sitemap_section_entries(nested_index, "Optional") == [
            ("Top-level llms.txt", relative_root)
        ]
        resolved_root = (nested_index.parent / relative_root).resolve()
        assert resolved_root == (build_dir / "llms.txt").resolve()
        assert_file_exists_with_content(resolved_root)
        assert "[llms-full.txt](" not in content


def test_nested_sitemap_generation_sorts_pages_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Root and nested indexes share one global toctree ordering pass."""
    sort_calls = 0
    original = MarkdownGenerator._sorted_sitemap_files

    def counted_sort(generator: MarkdownGenerator, files: Iterable[Path]) -> list[Path]:
        nonlocal sort_calls
        sort_calls += 1
        return original(generator, files)

    monkeypatch.setattr(MarkdownGenerator, "_sorted_sitemap_files", counted_sort)
    build = _build_sphinx("dirhtml", {"llms_txt_build_parallel": False})
    next(build)

    assert sort_calls == 1


@pytest.mark.parametrize(
    ("builder", "expected_target"),
    [
        ("html", "nested/example.html.md"),
        ("dirhtml", "nested/example/index.html.md"),
    ],
)
def test_nested_index_entries_honor_markdown_http_base(
    builder: str, expected_target: str
) -> None:
    """Absolute Markdown targets are identical at every sitemap depth."""
    build = _build_sphinx(
        builder,
        {
            "llms_txt_build_parallel": False,
            "markdown_http_base": "https://example.test/docs/",
        },
    )
    _, build_dir, _ = next(build)

    nested_entries = _sitemap_entries(build_dir / "nested" / "llms.txt")
    assert nested_entries["Example"] == (f"https://example.test/docs/{expected_target}")
    for nested_index in build_dir.rglob("llms.txt"):
        if nested_index == build_dir / "llms.txt":
            continue
        nested_content = nested_index.read_text(encoding="utf-8")
        assert _sitemap_section_entries(nested_index, "Optional") == [
            ("Top-level llms.txt", "https://example.test/docs/llms.txt")
        ]
        assert "https://example.test/docs//llms.txt" not in nested_content


@pytest.mark.parametrize(
    ("builder", "parallel", "root_href"),
    [
        ("html", False, "../llms.txt"),
        ("dirhtml", True, "../../llms.txt"),
    ],
)
def test_nested_indexes_can_be_disabled(
    builder: str, parallel: bool, root_href: str
) -> None:
    """The nested switch retains root outputs and selects root discovery."""
    build = _build_sphinx(
        builder,
        {
            "llms_txt_build_parallel": parallel,
            "llms_txt_nested_enabled": False,
        },
    )
    app, build_dir, _ = next(build)
    html_path = (
        build_dir / "nested" / "example.html"
        if builder == "html"
        else build_dir / "nested" / "example" / "index.html"
    )

    assert {
        path.relative_to(build_dir).as_posix() for path in build_dir.rglob("llms.txt")
    } == {"llms.txt"}
    describedby = [
        link for link in _discovery_links(html_path) if link.get("rel") == "describedby"
    ]
    assert describedby == [{"rel": "describedby", "href": root_href}]
    assert get_llms_txt_index_path(app, "nested/example") == PurePosixPath("llms.txt")


@pytest.mark.parametrize("builder", ["html", "dirhtml"])
def test_disabled_nested_discovery_ignores_stale_indexes(builder: str) -> None:
    """A reused output tree never makes stale nested files authoritative."""
    docs_source_dir = Path(__file__).parents[3] / "docs" / "source"
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        build_dir = temp_path / "build"
        doctree_dir = temp_path / "doctrees"

        def build(nested_enabled: bool, *, freshenv: bool) -> Sphinx:
            app = Sphinx(
                srcdir=str(docs_source_dir),
                confdir=str(docs_source_dir),
                outdir=str(build_dir),
                doctreedir=str(doctree_dir),
                buildername=builder,
                warningiserror=False,
                freshenv=freshenv,
                confoverrides={
                    "llms_txt_build_parallel": False,
                    "llms_txt_nested_enabled": nested_enabled,
                },
            )
            app.build()
            return app

        build(True, freshenv=True)
        stale_index = build_dir / "nested" / "llms.txt"
        assert stale_index.is_file()
        app = build(False, freshenv=False)

        assert stale_index.is_file()
        assert get_llms_txt_index_path(app, "nested/example") == PurePosixPath(
            "llms.txt"
        )
        html_path = (
            build_dir / "nested" / "example.html"
            if builder == "html"
            else build_dir / "nested" / "example" / "index.html"
        )
        expected_href = "../llms.txt" if builder == "html" else "../../llms.txt"
        describedby = [
            link
            for link in _discovery_links(html_path)
            if link.get("rel") == "describedby"
        ]
        assert describedby == [{"rel": "describedby", "href": expected_href}]


@pytest.mark.parametrize(
    ("builder", "nested_enabled", "full_setting", "parallel"),
    [
        (builder, nested_enabled, full_setting, parallel)
        for builder in ("html", "dirhtml")
        for nested_enabled in (False, True)
        for full_setting, parallel in ((None, False), (False, True), (True, False))
    ],
)
def test_nested_and_full_build_controls_are_independent(
    builder: str,
    nested_enabled: bool,
    full_setting: bool | None,
    parallel: bool,
) -> None:
    """Nested generation preserves default, disabled, and enabled full output."""
    overrides = {
        "llms_txt_build_parallel": parallel,
        "llms_txt_nested_enabled": nested_enabled,
    }
    if full_setting is not None:
        overrides["llms_txt_full_build"] = full_setting
    build = _build_sphinx(builder, overrides)
    _, build_dir, _ = next(build)

    full_build = full_setting is True
    assert (build_dir / "llms.txt").is_file()
    assert (build_dir / "llms-full.txt").is_file() is full_build
    assert (build_dir / "nested" / "llms.txt").is_file() is nested_enabled
    root_content = (build_dir / "llms.txt").read_text(encoding="utf-8")
    full_entry = (
        "- [llms-full.txt](llms-full.txt): Complete documentation in a single file."
    )
    assert root_content.count("## Optional") == int(full_build)
    assert root_content.count(full_entry) == int(full_build)
    assert "For more comprehensive documentation" not in root_content
    if nested_enabled:
        nested_index = build_dir / "nested" / "llms.txt"
        nested_content = nested_index.read_text(encoding="utf-8")
        assert "llms-full.txt" not in nested_content
        assert _sitemap_section_entries(nested_index, "Optional") == [
            ("Top-level llms.txt", "../llms.txt")
        ]

    html_path = (
        build_dir / "nested" / "example.html"
        if builder == "html"
        else build_dir / "nested" / "example" / "index.html"
    )
    expected_href = (
        "llms.txt"
        if nested_enabled
        else ("../llms.txt" if builder == "html" else "../../llms.txt")
    )
    describedby = [
        link for link in _discovery_links(html_path) if link.get("rel") == "describedby"
    ]
    assert describedby == [{"rel": "describedby", "href": expected_href}]


@pytest.mark.parametrize(
    ("builder", "nested_enabled", "full_build"),
    [
        (builder, nested_enabled, full_build)
        for builder in ("html", "dirhtml")
        for nested_enabled in (False, True)
        for full_build in (False, True)
    ],
)
def test_custom_root_override_is_independent_of_nested_and_full_controls(
    builder: str, nested_enabled: bool, full_build: bool
) -> None:
    """An authored root remains exact while nested and full outputs stay separate."""
    build = _build_sphinx(
        builder,
        {
            "llms_txt_build_parallel": False,
            "llms_txt_full_build": full_build,
            "llms_txt_nested_enabled": nested_enabled,
            "llms_txt_override_source": "index",
        },
    )
    _, build_dir, _ = next(build)

    root_content = (build_dir / "llms.txt").read_text(encoding="utf-8")
    assert "Welcome to sphinx-llm" in root_content
    assert "## Pages" not in root_content
    assert "llms-full.txt" not in root_content
    assert (build_dir / "llms-full.txt").is_file() is full_build
    assert (build_dir / "nested" / "llms.txt").is_file() is nested_enabled
    if nested_enabled:
        nested_index = build_dir / "nested" / "llms.txt"
        nested_content = nested_index.read_text(encoding="utf-8")
        assert "[llms-full.txt](" not in nested_content
        assert _sitemap_section_entries(nested_index, "Optional") == [
            ("Top-level llms.txt", "../llms.txt")
        ]

    html_path = (
        build_dir / "nested" / "example.html"
        if builder == "html"
        else build_dir / "nested" / "example" / "index.html"
    )
    expected_href = (
        "llms.txt"
        if nested_enabled
        else ("../llms.txt" if builder == "html" else "../../llms.txt")
    )
    describedby = [
        link for link in _discovery_links(html_path) if link.get("rel") == "describedby"
    ]
    assert describedby == [{"rel": "describedby", "href": expected_href}]


@pytest.mark.parametrize("builder", ["html", "dirhtml"])
def test_custom_root_override_nested_link_honors_markdown_http_base(
    builder: str,
) -> None:
    """A nested index links to an unmodified custom root with an absolute base."""
    root_contents = []
    for full_build in (False, True):
        build = _build_sphinx(
            builder,
            {
                "llms_txt_build_parallel": False,
                "llms_txt_full_build": full_build,
                "llms_txt_nested_enabled": True,
                "llms_txt_override_source": "index",
                "markdown_http_base": "https://example.test/docs/",
            },
        )
        _, build_dir, _ = next(build)

        root_contents.append((build_dir / "llms.txt").read_text(encoding="utf-8"))
        for nested_index in build_dir.rglob("llms.txt"):
            if nested_index == build_dir / "llms.txt":
                continue
            nested_content = nested_index.read_text(encoding="utf-8")
            assert _sitemap_section_entries(nested_index, "Optional") == [
                ("Top-level llms.txt", "https://example.test/docs/llms.txt")
            ]
            assert "https://example.test/docs//llms.txt" not in nested_content
            assert "[llms-full.txt](" not in nested_content
        assert (build_dir / "llms-full.txt").is_file() is full_build

    assert root_contents[0] == root_contents[1]
    assert "## Optional" not in root_contents[0]


@pytest.mark.parametrize("builder", ["html", "dirhtml"])
def test_disabled_builds_do_not_have_discovery_metadata(builder: str):
    """Disabling llms.txt leaves HTML metadata unchanged."""
    build = _build_sphinx(builder, {"llms_txt_enabled": False})
    _, build_dir, _ = next(build)
    links = _discovery_links(build_dir / "index.html")

    assert not [
        link for link in links if link.get("rel") in {"alternate", "describedby"}
    ]


def test_discovery_metadata_covers_source_pages_not_auxiliary_pages(tmp_path: Path):
    """Discovery is complete for source docs without dangling auxiliary links."""
    source_dir = tmp_path / "source"
    guide_dir = source_dir / "guide"
    guide_dir.mkdir(parents=True)
    (source_dir / "conf.py").write_text(
        'extensions = ["sphinx_llm.txt"]\n'
        'project = "Discovery test"\n'
        'root_doc = "index"\n'
        "llms_txt_build_parallel = False\n"
        'llms_txt_suffix_mode = "replace"\n'
        'llms_txt_override_source = "index"\n'
        'llms_txt_exclude = ["excluded"]\n',
        encoding="utf-8",
    )
    (source_dir / "index.rst").write_text(
        "Index\n=====\n\n.. toctree::\n\n   guide/index\n   guide/page\n   excluded\n",
        encoding="utf-8",
    )
    (guide_dir / "index.rst").write_text(
        "Guide\n=====\n\n.. meta::\n   :description: Existing metadata must remain.\n",
        encoding="utf-8",
    )
    (guide_dir / "page.rst").write_text("Page\n====\n", encoding="utf-8")
    (source_dir / "excluded.rst").write_text("Excluded\n========\n", encoding="utf-8")
    (source_dir / "orphan.rst").write_text(
        ":orphan:\n\nOrphan\n======\n", encoding="utf-8"
    )
    output_dir = tmp_path / "output"
    app = Sphinx(
        srcdir=str(source_dir),
        confdir=str(source_dir),
        outdir=str(output_dir),
        doctreedir=str(tmp_path / "doctrees"),
        buildername="dirhtml",
        warningiserror=False,
        freshenv=True,
    )
    app.build()

    pages = {
        "index": (output_dir / "index.html", "index.md", "llms.txt"),
        "guide/index": (
            output_dir / "guide/index.html",
            "index.md",
            "llms.txt",
        ),
        "guide/page": (
            output_dir / "guide/page/index.html",
            "index.md",
            "llms.txt",
        ),
        "excluded": (
            output_dir / "excluded/index.html",
            "index.md",
            "../llms.txt",
        ),
        "orphan": (
            output_dir / "orphan/index.html",
            "index.md",
            "llms.txt",
        ),
    }
    for docname, (html_path, markdown_href, llms_txt_href) in pages.items():
        links = _discovery_links(html_path)
        alternate = [
            link
            for link in links
            if link.get("rel") == "alternate" and link.get("type") == "text/markdown"
        ]
        describedby = [link for link in links if link.get("rel") == "describedby"]
        assert alternate == [
            {
                "rel": "alternate",
                "type": "text/markdown",
                "href": markdown_href,
            }
        ], docname
        assert describedby == [{"rel": "describedby", "href": llms_txt_href}], docname
        assert_file_exists_with_content(html_path.parent / alternate[0]["href"])
        assert_file_exists_with_content(html_path.parent / describedby[0]["href"])

    guide_html = pages["guide/index"][0].read_text(encoding="utf-8")
    assert 'content="Existing metadata must remain."' in guide_html
    assert 'name="description"' in guide_html
    for auxiliary_name in ("genindex", "search"):
        auxiliary_path = output_dir / auxiliary_name / "index.html"
        assert auxiliary_path.exists()
        assert not [
            link
            for link in _discovery_links(auxiliary_path)
            if link.get("rel") in {"alternate", "describedby"}
        ]


@pytest.mark.parametrize("builder", ["text", "llms-markdown"])
def test_unsupported_and_internal_builders_do_not_register_discovery(builder: str):
    """Non-HTML and internal Markdown builders remain unchanged."""
    app = MagicMock()
    app.builder.name = builder
    app.builder.outdir = "/tmp/unused"
    app.config.llms_txt_enabled = True
    app.config.llms_txt_build_parallel = True
    app.config.llms_txt_suffix_mode = "auto"
    generator = MarkdownGenerator(app)

    generator.build_llms_txt(app)

    assert call("html-page-context", generator.add_discovery_metadata) not in (
        app.connect.call_args_list
    )


def test_llms_full_txt_not_created_by_default(sphinx_build):
    """Test that llms-full.txt is not created or referenced by default."""
    _, build_dir, _ = sphinx_build

    llms_full_txt_path = build_dir / "llms-full.txt"
    assert not llms_full_txt_path.exists()
    assert "llms-full.txt" not in (build_dir / "llms.txt").read_text(encoding="utf-8")


def test_llms_full_setting_matrix(sphinx_build_llms_full_matrix):
    """Cover default, disabled, and enabled full output in every build mode."""
    app, build_dir, _, full_setting = sphinx_build_llms_full_matrix
    llms_txt = (build_dir / "llms.txt").read_text(encoding="utf-8")
    llms_full = build_dir / "llms-full.txt"

    if full_setting is not True:
        assert not llms_full.exists()
        assert "llms-full.txt" not in llms_txt
        assert_file_exists_with_content(build_dir / "llms.txt")
        assert_file_exists_with_content(build_dir / "index.html.md")
        return

    assert_file_exists_with_content(llms_full)
    http_base = (getattr(app.config, "markdown_http_base", "") or "").rstrip("/")
    expected_url = f"{http_base}/llms-full.txt" if http_base else "llms-full.txt"
    expected_entry = (
        f"- [llms-full.txt]({expected_url}): Complete documentation in a single file."
    )
    assert "## Optional\n\n" in llms_txt
    assert llms_txt.count(expected_entry) == 1
    assert "For more comprehensive documentation" not in llms_txt
    if not http_base:
        assert (build_dir / expected_url).is_file()


@pytest.fixture
def sphinx_build_no_llms_full(
    request,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Build Sphinx docs with llms_txt_full_build set to False."""
    builder = request.param
    yield from _build_sphinx(builder, {"llms_txt_full_build": False})


@pytest.mark.parametrize(
    "sphinx_build_no_llms_full",
    ["html", "dirhtml"],
    indirect=True,
)
def test_llms_full_txt_not_created_when_disabled(sphinx_build_no_llms_full):
    """Test that llms-full.txt is NOT created when llms_txt_full_build is False."""
    _, build_dir, _ = sphinx_build_no_llms_full

    llms_full_txt_path = build_dir / "llms-full.txt"
    assert not llms_full_txt_path.exists(), (
        "llms-full.txt should not be created when llms_txt_full_build is False"
    )


@pytest.mark.parametrize(
    "sphinx_build_no_llms_full",
    ["html", "dirhtml"],
    indirect=True,
)
def test_llms_txt_sitemap_still_created_when_full_disabled(sphinx_build_no_llms_full):
    """Test that llms.txt sitemap is still created when llms-full.txt is disabled."""
    _, build_dir, _ = sphinx_build_no_llms_full

    llms_txt_path = build_dir / "llms.txt"
    assert llms_txt_path.exists(), (
        "llms.txt should still be created when llms_txt_full_build is False"
    )
    assert llms_txt_path.stat().st_size > 0, "llms.txt should not be empty"


@pytest.mark.parametrize(
    "sphinx_build_no_llms_full",
    ["html", "dirhtml"],
    indirect=True,
)
def test_markdown_files_still_created_when_full_disabled(sphinx_build_no_llms_full):
    """Test that per-page markdown files are still created when llms-full.txt is disabled."""
    app, build_dir, source_dir = sphinx_build_no_llms_full

    rst_files = list(source_dir.rglob("*.rst"))
    assert len(rst_files) > 0, "No RST files found in source directory"

    for rst_file in rst_files:
        rel_path = rst_file.relative_to(source_dir)

        if app.builder.name == "html":
            md_path = build_dir / rel_path.with_suffix(".html.md")
        elif rel_path.stem == "index":
            if rel_path.parent == Path("."):
                md_path = build_dir / "index.html.md"
            else:
                md_path = build_dir / rel_path.parent / "index.html.md"
        else:
            md_path = build_dir / rel_path.with_suffix("") / "index.html.md"

        assert md_path.exists(), (
            f"Markdown file should still be created when llms-full.txt is disabled: {md_path}"
        )


@pytest.mark.parametrize(
    "sphinx_build_no_llms_full",
    ["html", "dirhtml"],
    indirect=True,
)
def test_llms_txt_does_not_link_to_llms_full_when_disabled(sphinx_build_no_llms_full):
    """Test that llms.txt has no llms-full reference when explicitly disabled."""
    _, build_dir, _ = sphinx_build_no_llms_full

    content = (build_dir / "llms.txt").read_text(encoding="utf-8")
    assert "llms-full.txt" not in content


@pytest.mark.parametrize("nested_enabled", [False, True])
def test_llms_txt_does_not_reference_stale_full_artifact(
    tmp_path: Path, nested_enabled: bool
):
    """Only a full artifact generated by the current build may be listed."""
    docs_source_dir = Path(__file__).parent.parent.parent.parent / "docs" / "source"
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    stale_full = build_dir / "llms-full.txt"
    stale_full.write_text("stale output\n", encoding="utf-8")

    with patch.object(MarkdownGenerator, "build_llms_full_txt", return_value=None):
        app = Sphinx(
            srcdir=str(docs_source_dir),
            confdir=str(docs_source_dir),
            outdir=str(build_dir),
            doctreedir=str(tmp_path / "doctrees"),
            buildername="html",
            warningiserror=False,
            freshenv=True,
            confoverrides={
                "llms_txt_build_parallel": False,
                "llms_txt_full_build": True,
                "llms_txt_nested_enabled": nested_enabled,
            },
        )
        app.build()

    assert stale_full.read_text(encoding="utf-8") == "stale output\n"
    assert "llms-full.txt" not in (build_dir / "llms.txt").read_text(encoding="utf-8")
    nested_index = build_dir / "nested" / "llms.txt"
    assert nested_index.is_file() is nested_enabled
    if nested_enabled:
        assert "llms-full.txt" not in nested_index.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# html_meta description tests
# ---------------------------------------------------------------------------

_HTML_META_PAGE = "meta_example"


def _get_html_meta_description(app: Sphinx, docname: str) -> str:
    """Extract the html_meta description from a page's pickled doctree.

    This is the ground truth for what the extension should write into llms.txt.
    Reading it from the doctree (rather than hardcoding it) keeps the tests
    valid when the source document is edited.
    """
    doctree = app.env.get_doctree(docname)
    for node in doctree.traverse(lambda node: node.tagname == "meta"):
        if node.get("name") == "description" and node.get("content"):
            return node["content"]
    raise AssertionError(
        f"No html_meta description found in doctree for '{docname}'. "
        f"Does the source file define '.. meta:: :description:'?"
    )


def test_html_meta_description_used_in_llms_txt(sphinx_build):
    """Test that a page's html_meta description is used in llms.txt when defined."""
    app, build_dir, _ = sphinx_build

    expected = _get_html_meta_description(app, _HTML_META_PAGE)
    content = (build_dir / "llms.txt").read_text(encoding="utf-8")

    meta_lines = [line for line in content.splitlines() if _HTML_META_PAGE in line]
    assert meta_lines, f"No llms.txt entry found for page '{_HTML_META_PAGE}'"

    for line in meta_lines:
        assert expected in line, (
            f"html_meta description not found in llms.txt entry for '{_HTML_META_PAGE}'.\n"
            f"Entry:    {line!r}\n"
            f"Expected: {expected!r}"
        )


def test_html_meta_description_without_nodes_meta(sphinx_build, monkeypatch, tmp_path):
    app, _, _ = sphinx_build
    expected = _get_html_meta_description(app, _HTML_META_PAGE)
    doctree = app.env.get_doctree(_HTML_META_PAGE)
    monkeypatch.setattr(app.env, "get_doctree", lambda docname: doctree)
    monkeypatch.delattr(docutils.nodes, "meta", raising=False)
    md_file = tmp_path / "page.md"
    md_file.write_text("Content fallback.", encoding="utf-8")
    generator = MarkdownGenerator(app)
    generator._docname_by_output_file[md_file] = _HTML_META_PAGE

    assert generator.get_page_description(md_file) == expected


def test_content_fallback_used_when_no_html_meta(sphinx_build):
    """Test that pages without html_meta use content-based descriptions in llms.txt."""
    app, build_dir, _ = sphinx_build

    llms_txt_path = build_dir / "llms.txt"
    content = llms_txt_path.read_text(encoding="utf-8")

    # The 'apples' page has no html_meta; its llms.txt description should match
    # the content-based extraction.  We derive the local markdown file path from
    # the URL already recorded in llms.txt.  The URL may be relative or absolute
    # (when markdown_http_base is configured), so we normalise accordingly.
    apples_lines = [line for line in content.splitlines() if "apples" in line.lower()]
    assert apples_lines, "No llms.txt entry found for 'apples' page"

    for line in apples_lines:
        url_match = re.search(r"\]\(([^)]+)\)", line)
        desc_match = re.search(r"\):\s*(.+)$", line)
        assert url_match and desc_match and desc_match.group(1).strip(), (
            f"Could not parse llms.txt entry for 'apples': {line!r}"
        )
        url = url_match.group(1)
        if url.startswith(("http://", "https://")):
            http_base = (getattr(app.config, "markdown_http_base", "") or "").rstrip(
                "/"
            )
            rel_path = url[len(http_base) :].lstrip("/")
        else:
            rel_path = url
        apples_md = build_dir / rel_path
        expected = MarkdownGenerator.extract_description_from_markdown(apples_md)
        assert desc_match.group(1).strip() == expected, (
            f"Expected content-based description {expected!r}, "
            f"got {desc_match.group(1).strip()!r}"
        )


@pytest.mark.parametrize(
    "linked_source",
    [
        "[Readable label](python_api.html.md#callback-api) trailing prose",
        "[Readable label][api] trailing prose\n\n"
        "[api]: python_api.html.md#callback-api",
    ],
)
def test_content_fallback_sanitizes_before_truncating(
    tmp_path: Path, linked_source: str
) -> None:
    """Fallback excerpts never truncate a link into unsafe literal syntax."""
    markdown = tmp_path / "page.html.md"
    markdown.write_text("A" * 75 + " " + linked_source, encoding="utf-8")
    expected = ("A" * 75 + " Readable label trailing prose")[:100] + "..."

    description = MarkdownGenerator.extract_description_from_markdown(markdown)

    assert description == expected
    assert "python_api.html.md" not in description
    assert "[Readable label]" not in description


def test_content_fallback_plain_truncation_is_unchanged(tmp_path: Path) -> None:
    """Sanitization does not alter the existing plain-text truncation contract."""
    markdown = tmp_path / "page.html.md"
    markdown.write_text("A" * 101, encoding="utf-8")
    assert MarkdownGenerator.extract_description_from_markdown(markdown) == (
        "A" * 100 + "..."
    )


def test_get_docname_from_md_file(sphinx_build):
    """Test that _get_docname_from_md_file returns correct Sphinx docnames."""
    app, _, _ = sphinx_build
    generator = MarkdownGenerator(app)
    # Simulate a md_build_dir so the helper can be exercised directly

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        generator.md_build_dir = tmp_path

        cases = {
            tmp_path / "index.md": "index",
            tmp_path / "apples.md": "apples",
            tmp_path / "nested" / "example.md": "nested/example",
        }
        for md_file, expected_docname in cases.items():
            md_file.parent.mkdir(parents=True, exist_ok=True)
            md_file.touch()
            assert generator._get_docname_from_md_file(md_file) == expected_docname


def test_html_meta_description_used_in_incremental_build():
    """Test that html_meta descriptions are used even when doctrees are cached.

    This covers the case where Sphinx does NOT fire doctree-read for unchanged
    pages (incremental / non-fresh builds).  A naive implementation that collects
    descriptions only during doctree-read would silently fall back to the
    content-based description in this scenario.
    """
    docs_source_dir = Path(__file__).parent.parent.parent.parent / "docs" / "source"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Both builds share the same outdir, doctreedir, and confoverrides so
        # Sphinx's incremental environment cache is active for the second build.
        # (A different outdir, or any changed config value registered with
        # rebuild="env", triggers a full re-read and defeats the purpose of
        # this test.  llms_txt_build_parallel=True matches the extension default
        # to avoid the "config changed" detection.)
        build_dir = tmp_path / "build"
        doctree_dir = tmp_path / "doctrees"
        overrides = {"llms_txt_build_parallel": True}

        # ── First build (fresh) ── populates the doctree pickle cache
        app1 = Sphinx(
            srcdir=str(docs_source_dir),
            confdir=str(docs_source_dir),
            outdir=str(build_dir),
            doctreedir=str(doctree_dir),
            buildername="html",
            warningiserror=False,
            freshenv=True,
            confoverrides=overrides,
        )
        app1.build()

        # ── Second build (incremental) ── source unchanged; doctrees served from cache
        doctree_read_pages: list[str] = []
        app2 = Sphinx(
            srcdir=str(docs_source_dir),
            confdir=str(docs_source_dir),
            outdir=str(build_dir),
            doctreedir=str(doctree_dir),
            buildername="html",
            warningiserror=False,
            freshenv=False,
            confoverrides=overrides,
        )
        app2.connect(
            "doctree-read",
            lambda a, dt: doctree_read_pages.append(a.env.docname),
        )
        app2.build()

        # Confirm we are actually exercising the incremental-build path
        assert _HTML_META_PAGE not in doctree_read_pages, (
            f"Expected '{_HTML_META_PAGE}' to be served from doctree cache, "
            f"but doctree-read fired for it. Incremental build test is not valid."
        )

        # html_meta description must still appear in llms.txt.
        # Derive the expected description from the pickled doctree (same source
        # of truth as the extension) rather than hardcoding the string.
        expected = _get_html_meta_description(app2, _HTML_META_PAGE)
        llms_txt = (build_dir / "llms.txt").read_text(encoding="utf-8")
        meta_lines = [line for line in llms_txt.splitlines() if _HTML_META_PAGE in line]
        assert meta_lines, f"No llms.txt entry found for page '{_HTML_META_PAGE}'"
        for line in meta_lines:
            assert expected in line, (
                f"html_meta description missing from llms.txt in incremental build.\n"
                f"Entry:    {line!r}\n"
                f"Expected: {expected!r}"
            )


@pytest.fixture(
    params=[("html", True), ("html", False), ("dirhtml", True), ("dirhtml", False)]
)
def sphinx_build_with_exclude(
    request,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Build Sphinx docs with llms_txt_exclude set."""
    builder, parallel = request.param
    yield from _build_sphinx(
        builder,
        {
            "llms_txt_build_parallel": parallel,
            "llms_txt_exclude": ["apples", "nested/**"],
            "llms_txt_full_build": True,
        },
    )


# Body text unique to the excluded pages: unlike their titles (which other
# pages may reference, e.g. in toctrees), these strings only ever appear in
# the pages themselves.
_APPLES_BODY_TEXT = "wonderful experience for both you and the pig"
_NESTED_BODY_TEXT = "This is an example."


def test_excluded_documents_not_in_llms_txt(sphinx_build_with_exclude):
    """Documents matching llms_txt_exclude must not be listed in llms.txt."""
    _, build_dir, _ = sphinx_build_with_exclude
    llms_txt = build_dir / "llms.txt"
    assert_file_exists_with_content(llms_txt)
    content = llms_txt.read_text()

    assert _APPLES_BODY_TEXT not in content
    assert _NESTED_BODY_TEXT not in content
    # Non-excluded documents are still listed
    assert "test" in content


def test_excluded_documents_not_in_llms_full_txt(sphinx_build_with_exclude):
    """Documents matching llms_txt_exclude must not be part of llms-full.txt."""
    _, build_dir, _ = sphinx_build_with_exclude
    llms_full = build_dir / "llms-full.txt"
    assert_file_exists_with_content(llms_full)
    content = llms_full.read_text()

    assert _APPLES_BODY_TEXT not in content
    assert _NESTED_BODY_TEXT not in content


def test_excluded_documents_still_have_markdown_files(sphinx_build_with_exclude):
    """Documents matching llms_txt_exclude still get their individual
    markdown files."""
    app, build_dir, _ = sphinx_build_with_exclude

    if app.builder.name == "dirhtml":
        apples_md = build_dir / "apples" / "index.html.md"
        nested_md = build_dir / "nested" / "example" / "index.html.md"
    else:
        apples_md = build_dir / "apples.html.md"
        nested_md = build_dir / "nested" / "example.html.md"

    assert_file_exists_with_content(apples_md)
    assert_file_exists_with_content(nested_md)


def test_excluded_override_source_raises_error():
    """An override source must not bypass llms_txt_exclude."""
    with pytest.raises(ExtensionError, match="matches llms_txt_exclude"):
        list(
            _build_sphinx(
                "html",
                {
                    "llms_txt_build_parallel": False,
                    "llms_txt_exclude": ["apples"],
                    "llms_txt_override_source": "apples",
                },
            )
        )


def test_confdir_outside_srcdir():
    """The markdown sub-build must honor a configuration directory that does
    not live in the source directory (sphinx-build -c option)."""
    docs_source_dir = Path(__file__).parent.parent.parent.parent / "docs" / "source"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        srcdir = temp_path / "source"
        confdir = temp_path / "config"
        build_dir = temp_path / "build"
        doctree_dir = temp_path / "doctrees"

        shutil.copytree(docs_source_dir, srcdir)
        confdir.mkdir()
        (srcdir / "conf.py").rename(confdir / "conf.py")

        app = Sphinx(
            srcdir=str(srcdir),
            confdir=str(confdir),
            outdir=str(build_dir),
            doctreedir=str(doctree_dir),
            buildername="html",
            warningiserror=False,
            freshenv=True,
            confoverrides={
                "llms_txt_build_parallel": True,
                "llms_txt_full_build": True,
            },
        )
        app.build()

        assert_file_exists_with_content(build_dir / "llms.txt")
        assert_file_exists_with_content(build_dir / "llms-full.txt")
        assert_file_exists_with_content(build_dir / "index.html.md")


def test_tags_forwarded_to_markdown_build():
    """Tags of the primary build (sphinx-build -t option) must be forwarded
    to the markdown sub-build so that conditional content (".. only::")
    renders the same in both outputs."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        srcdir = temp_path / "source"
        build_dir = temp_path / "build"
        doctree_dir = temp_path / "doctrees"

        srcdir.mkdir()
        (srcdir / "conf.py").write_text('extensions = ["sphinx_llm.txt"]\n')
        (srcdir / "index.rst").write_text(
            "Test\n"
            "====\n"
            "\n"
            "Always visible.\n"
            "\n"
            ".. only:: custom_tag\n"
            "\n"
            "   Tagged content marker.\n"
        )

        app = Sphinx(
            srcdir=str(srcdir),
            confdir=str(srcdir),
            outdir=str(build_dir),
            doctreedir=str(doctree_dir),
            buildername="html",
            warningiserror=False,
            freshenv=True,
            tags=["custom_tag"],
            confoverrides={"llms_txt_build_parallel": True},
        )
        app.build()

        index_md = build_dir / "index.html.md"
        assert_file_exists_with_content(index_md)
        content = index_md.read_text()
        assert "Always visible." in content
        assert "Tagged content marker." in content, (
            "Content behind a tag of the primary build is missing from the "
            "markdown output; tags were not forwarded to the sub-build"
        )


def test_config_overrides_forwarded_to_markdown_build():
    """Configuration overrides must be forwarded to the markdown sub-build."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        srcdir = temp_path / "source"
        build_dir = temp_path / "build"

        srcdir.mkdir()
        (srcdir / "conf.py").write_text('extensions = ["sphinx_llm.txt"]\n')
        (srcdir / "index.rst").write_text("Test\n====\n\n|today|\n")

        app = Sphinx(
            srcdir=str(srcdir),
            confdir=str(srcdir),
            outdir=str(build_dir),
            doctreedir=str(temp_path / "doctrees"),
            buildername="html",
            warningiserror=False,
            freshenv=True,
            confoverrides={"today": "FORWARDED_OVERRIDE"},
        )
        app.build()

        assert "FORWARDED_OVERRIDE" in (build_dir / "index.html.md").read_text()
