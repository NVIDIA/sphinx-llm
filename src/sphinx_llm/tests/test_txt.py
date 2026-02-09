# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the sphinx_llm.txt module.
"""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from sphinx.application import Sphinx

from sphinx_llm.txt import MarkdownGenerator


@pytest.fixture(
    params=[
        # builder, parallel
        ("html", True),
        ("dirhtml", True),
        ("html", False),
        ("dirhtml", False),
    ]
)
def sphinx_build(request) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """
    Build Sphinx documentation into a temporary directory.

    Yields:
        Tuple of (Sphinx app, temporary build directory path, source directory path)
    """
    builder, parallel = request.param
    # Get the docs source directory
    docs_source_dir = Path(__file__).parent.parent.parent.parent / "docs" / "source"

    # Create a temporary directory for the build
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        build_dir = temp_path / "build"
        doctree_dir = temp_path / "doctrees"

        # Create the Sphinx application
        app = Sphinx(
            srcdir=str(docs_source_dir),
            confdir=str(docs_source_dir),
            outdir=str(build_dir),
            doctreedir=str(doctree_dir),
            buildername=builder,
            warningiserror=False,
            freshenv=True,
            confoverrides={"llms_txt_build_parallel": parallel},
        )

        # Build the documentation
        app.build()

        yield app, build_dir, docs_source_dir


def test_sphinx_build_fixture(sphinx_build):
    """Test that the sphinx_build fixture works correctly."""
    app, build_dir, source_dir = sphinx_build

    # Verify the app is a Sphinx application
    assert isinstance(app, Sphinx)

    # Verify the build directory exists and contains files
    assert build_dir.exists()
    assert build_dir.is_dir()

    # Verify the source directory exists
    assert source_dir.exists()
    assert source_dir.is_dir()

    # Check that index.html exists in the build directory
    index_html = build_dir / "index.html"
    assert index_html.exists(), f"{index_html} does not exist"


def test_markdown_generator_init(sphinx_build):
    """Test MarkdownGenerator initialization."""
    app, _, _ = sphinx_build
    generator = MarkdownGenerator(app)

    assert generator.app == app
    # No builder attribute to check anymore


def test_markdown_generator_setup(sphinx_build):
    """Test that setup connects to the correct events."""
    app, _, _ = sphinx_build
    generator = MarkdownGenerator(app)

    # Patch app.connect to record calls
    connect_calls = []
    original_connect = app.connect

    def record_connect(event, callback):
        connect_calls.append((event, callback))
        return original_connect(event, callback)

    app.connect = record_connect

    generator.setup()

    # Check that the correct event is connected
    events = [call[0] for call in connect_calls]
    assert "builder-inited" in events


def test_build_llms_txt_with_exception(sphinx_build):
    """Test that build_llms_txt returns early on exception."""
    app, _, _ = sphinx_build
    generator = MarkdownGenerator(app)

    # Should not raise
    generator.combine_builds(app, Exception("fail"))


def test_rst_files_have_corresponding_output_files(sphinx_build):
    """Test that all RST files have corresponding HTML and HTML.MD files in output."""
    app, build_dir, source_dir = sphinx_build

    # Find all RST files in the source directory
    rst_files = list(source_dir.rglob("*.rst"))
    assert len(rst_files) > 0, "No RST files found in source directory"

    # For each RST file, check that corresponding HTML and HTML.MD files exist
    for rst_file in rst_files:
        # Calculate relative path from source directory
        rel_path = rst_file.relative_to(source_dir)

        # For html builder remove .rst extension and add .html
        # For dirhtml builder remove .rst extension and add directory containing index.html
        html_or_index = rel_path.stem == "index" or app.builder.name == "html"
        html_name = (
            rel_path.with_suffix(".html")
            if html_or_index
            else rel_path.with_suffix("") / "index.html"
        )
        html_md_name = html_name.with_suffix(".html.md")

        # Check HTML file exists
        html_path = build_dir / html_name
        assert html_path.exists(), f"HTML file not found: {html_path}"

        # Check HTML.MD file exists
        html_md_path = build_dir / html_md_name
        assert html_md_path.exists(), f"HTML.MD file not found: {html_md_path}"

        # Verify both files have content
        assert html_path.stat().st_size > 0, f"HTML file is empty: {html_path}"
        assert html_md_path.stat().st_size > 0, f"HTML.MD file is empty: {html_md_path}"


def test_llms_txt_sitemap_links_exist(sphinx_build):
    """Test that all markdown pages listed in the llms.txt sitemap actually exist."""
    app, build_dir, source_dir = sphinx_build

    # Check that llms.txt exists
    llms_txt_path = build_dir / "llms.txt"
    assert llms_txt_path.exists(), f"llms.txt not found: {llms_txt_path}"

    # Read the sitemap and extract URLs
    with open(llms_txt_path, encoding="utf-8") as f:
        content = f.read()

    # Find all markdown URLs in the sitemap
    # URLs are in the format: [title](url)
    import re

    url_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    matches = re.findall(url_pattern, content)

    assert len(matches) > 0, "No URLs found in llms.txt sitemap"

    # Check that each URL points to an existing markdown file
    for title, url in matches:
        # Convert URL to file path relative to build directory
        md_file_path = build_dir / url

        assert md_file_path.exists(), (
            f"Markdown file not found for URL '{url}' (title: '{title}'): {md_file_path}"
        )
        assert md_file_path.stat().st_size > 0, (
            f"Markdown file is empty for URL '{url}' (title: '{title}'): {md_file_path}"
        )


def test_dirhtml_url_style_markdown_files(sphinx_build):
    """Test that dirhtml builder creates URL-style .md files (e.g., foo.md) by default."""
    app, build_dir, source_dir = sphinx_build

    # This test only applies to dirhtml builder
    if app.builder.name != "dirhtml":
        pytest.skip("Only applicable to dirhtml builder")

    # Find all RST files in the source directory (except index.rst)
    rst_files = [f for f in source_dir.rglob("*.rst") if f.stem != "index"]
    assert len(rst_files) > 0, "No non-index RST files found in source directory"

    # For each RST file, check that URL-style markdown file exists
    for rst_file in rst_files:
        # Calculate relative path from source directory
        rel_path = rst_file.relative_to(source_dir)

        # For dirhtml, foo.rst should create both:
        # - foo/index.html.md (current default)
        # - foo.md (new URL-style)
        url_style_md = build_dir / rel_path.with_suffix(".md")

        assert url_style_md.exists(), (
            f"URL-style markdown file not found: {url_style_md}"
        )
        assert url_style_md.stat().st_size > 0, (
            f"URL-style markdown file is empty: {url_style_md}"
        )


def test_dirhtml_both_markdown_formats_by_default(sphinx_build):
    """Test that dirhtml builder creates both index.html.md and .md files by default."""
    app, build_dir, source_dir = sphinx_build

    # This test only applies to dirhtml builder
    if app.builder.name != "dirhtml":
        pytest.skip("Only applicable to dirhtml builder")

    # Find all RST files in the source directory (except index.rst)
    rst_files = [f for f in source_dir.rglob("*.rst") if f.stem != "index"]
    assert len(rst_files) > 0, "No non-index RST files found in source directory"

    # For each RST file, check that both formats exist
    for rst_file in rst_files:
        # Calculate relative path from source directory
        rel_path = rst_file.relative_to(source_dir)

        # For dirhtml, foo.rst should create both:
        # - foo/index.html.md (spec-compliant)
        # - foo.md (URL-style)
        spec_compliant_md = build_dir / rel_path.with_suffix("") / "index.html.md"
        url_style_md = build_dir / rel_path.with_suffix(".md")

        assert spec_compliant_md.exists(), (
            f"Spec-compliant markdown file not found: {spec_compliant_md}"
        )
        assert url_style_md.exists(), (
            f"URL-style markdown file not found: {url_style_md}"
        )

        # Verify content is the same (they should be copies of each other)
        with open(spec_compliant_md, encoding="utf-8") as f1:
            content1 = f1.read()
        with open(url_style_md, encoding="utf-8") as f2:
            content2 = f2.read()

        assert content1 == content2, (
            f"Content mismatch between {spec_compliant_md} and {url_style_md}"
        )


@pytest.fixture
def sphinx_build_with_suffix_mode_config(
    request,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """
    Build Sphinx documentation with specific llms_txt_suffix_mode configuration.

    Yields:
        Tuple of (Sphinx app, temporary build directory path, source directory path)
    """
    builder, suffix_mode_config = request.param
    # Get the docs source directory
    docs_source_dir = Path(__file__).parent.parent.parent.parent / "docs" / "source"

    # Create a temporary directory for the build
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        build_dir = temp_path / "build"
        doctree_dir = temp_path / "doctrees"

        # Create the Sphinx application
        app = Sphinx(
            srcdir=str(docs_source_dir),
            confdir=str(docs_source_dir),
            outdir=str(build_dir),
            doctreedir=str(doctree_dir),
            buildername=builder,
            warningiserror=False,
            freshenv=True,
            confoverrides={
                "llms_txt_build_parallel": True,
                "llms_txt_suffix_mode": suffix_mode_config,
            },
        )

        # Build the documentation
        app.build()

        yield app, build_dir, docs_source_dir


@pytest.mark.parametrize(
    "sphinx_build_with_suffix_mode_config",
    [("dirhtml", "file-suffix"), ("dirhtml", "url-suffix"), ("dirhtml", "both")],
    indirect=True,
)
def test_dirhtml_suffix_mode_configuration(sphinx_build_with_suffix_mode_config):
    """Test that llms_txt_suffix_mode configuration controls which markdown files are generated."""
    app, build_dir, source_dir = sphinx_build_with_suffix_mode_config
    suffix_mode_config = app.config.llms_txt_suffix_mode

    # Find all RST files in the source directory (except index.rst)
    rst_files = [f for f in source_dir.rglob("*.rst") if f.stem != "index"]
    assert len(rst_files) > 0, "No non-index RST files found in source directory"

    # For each RST file, check that the correct format exists
    for rst_file in rst_files:
        # Calculate relative path from source directory
        rel_path = rst_file.relative_to(source_dir)

        # Define both possible paths
        file_suffix_md = build_dir / rel_path.with_suffix("") / "index.html.md"
        url_suffix_md = build_dir / rel_path.with_suffix(".md")

        if suffix_mode_config == "file-suffix":
            # Only file-suffix should exist
            assert file_suffix_md.exists(), (
                f"File-suffix markdown file not found: {file_suffix_md}"
            )
            assert not url_suffix_md.exists(), (
                f"URL-suffix markdown file should not exist with suffix_mode='file-suffix': {url_suffix_md}"
            )
        elif suffix_mode_config == "url-suffix":
            # Only URL-suffix should exist
            assert url_suffix_md.exists(), (
                f"URL-suffix markdown file not found: {url_suffix_md}"
            )
            assert not file_suffix_md.exists(), (
                f"File-suffix markdown file should not exist with suffix_mode='url-suffix': {file_suffix_md}"
            )
        elif suffix_mode_config == "both":
            # Both should exist
            assert file_suffix_md.exists(), (
                f"File-suffix markdown file not found: {file_suffix_md}"
            )
            assert url_suffix_md.exists(), (
                f"URL-suffix markdown file not found: {url_suffix_md}"
            )
