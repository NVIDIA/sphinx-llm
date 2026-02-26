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
        assert_file_exists_with_content(build_dir / url)


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
