# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the sphinx_llm.txt module.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Generator
from pathlib import Path

import docutils.nodes
import pytest
from sphinx.application import Sphinx
from sphinx.errors import ExtensionError

from sphinx_llm.txt import MarkdownGenerator


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


@pytest.fixture
def sphinx_build_with_suffix_mode_config(
    request,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Build Sphinx docs with specific llms_txt_suffix_mode configuration."""
    builder, suffix_mode = request.param
    yield from _build_sphinx(builder, {"llms_txt_suffix_mode": suffix_mode})


def test_markdown_generator_init(sphinx_build):
    """Test MarkdownGenerator initialization."""
    app, _, _ = sphinx_build
    generator = MarkdownGenerator(app)
    assert generator.app == app


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
        ("html", "https://example.com/docs/"),
        ("dirhtml", "https://example.com/docs/"),
        ("dirhtml", "https://example.com/docs"),  # trailing slash is optional
    ]
)
def sphinx_build_with_http_base(
    request,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Build Sphinx docs with markdown_http_base set."""
    builder, http_base = request.param
    yield from _build_sphinx(builder, {"markdown_http_base": http_base})


def test_llms_txt_sitemap_uses_markdown_http_base(sphinx_build_with_http_base):
    """Test that llms.txt links are absolute when markdown_http_base is configured."""
    app, build_dir, _ = sphinx_build_with_http_base

    http_base = app.config._raw_config.get("markdown_http_base", "").rstrip("/")

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
            # Verify content is the same (they should be copies)
            assert file_suffix_md.read_text(
                encoding="utf-8"
            ) == url_suffix_md.read_text(encoding="utf-8"), (
                f"Content mismatch between {file_suffix_md} and {url_suffix_md}"
            )

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


def test_invalid_suffix_mode_raises_error():
    """Test that invalid llms_txt_suffix_mode values raise an error."""
    with pytest.raises(ExtensionError, match="Invalid llms_txt_suffix_mode"):
        list(_build_sphinx("dirhtml", {"llms_txt_suffix_mode": "invalid-mode"}))


def test_llms_full_txt_created_by_default(sphinx_build):
    """Test that llms-full.txt is created by default."""
    _, build_dir, _ = sphinx_build

    llms_full_txt_path = build_dir / "llms-full.txt"
    assert llms_full_txt_path.exists(), "llms-full.txt should be created by default"
    assert llms_full_txt_path.stat().st_size > 0, "llms-full.txt should not be empty"


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
    for node in doctree.traverse(docutils.nodes.meta):
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
