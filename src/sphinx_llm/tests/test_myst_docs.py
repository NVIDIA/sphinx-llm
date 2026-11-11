# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Exercise the repository's MyST sources through both documentation builds."""

import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PAGES = {
    "myst": ("MyST Markdown example", "Markdown sources share the Sphinx build"),
    "myst-links": ("Links from Markdown", "Cross-format links connect Markdown"),
}
LINKS = [
    ("myst", "myst-links"),
    ("myst", "apples"),
    ("myst-links", "myst"),
    ("myst-links", "apples"),
]


@pytest.fixture(
    scope="module",
    params=[
        ("html", False),
        ("dirhtml", False),
        ("html", True),
        ("dirhtml", True),
    ],
    ids=lambda param: f"{param[0]}-{'parallel' if param[1] else 'sequential'}",
)
def readonly_myst_build(request, docs_source_dir, tmp_path_factory):
    """Read-only CLI output with warnings as errors; never modify artifacts."""
    builder, parallel = request.param
    output = tmp_path_factory.mktemp("myst-build") / "build"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-W",
            "-b",
            builder,
            "-D",
            f"llms_txt_build_parallel={int(parallel)}",
            "-D",
            "llms_txt_full_build=1",
            str(docs_source_dir),
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    sitemap = (output / "llms.txt").read_text(encoding="utf-8")
    return SimpleNamespace(
        builder=builder,
        output=output,
        sitemap=sitemap,
        full=(output / "llms-full.txt").read_text(encoding="utf-8"),
        entries=re.findall(r"^- \[([^]]+)\]\(([^)]+)\): (.+)$", sitemap, re.MULTILINE),
    )


def html_path(build, docname: str) -> Path:
    return build.output / (
        f"{docname}.html" if build.builder == "html" else f"{docname}/index.html"
    )


def read_page(build, docname: str) -> tuple[str, str]:
    path = html_path(build, docname)
    return (
        path.read_text(encoding="utf-8"),
        path.with_suffix(".html.md").read_text(encoding="utf-8"),
    )


@pytest.mark.parametrize("docname", PAGES)
def test_title_and_body_in_html_and_markdown(readonly_myst_build, docname):
    title, body = PAGES[docname]
    html, markdown = read_page(readonly_myst_build, docname)
    assert title in html and title in markdown
    assert body in html and body in markdown and body in readonly_myst_build.full


@pytest.mark.parametrize("docname", PAGES)
def test_body_appears_once_in_llms_full(readonly_myst_build, docname):
    _, body = PAGES[docname]
    assert readonly_myst_build.full.count(body) == 1


@pytest.mark.parametrize("docname", PAGES)
def test_sitemap_entry_links_to_page_markdown(readonly_myst_build, docname):
    title, body = PAGES[docname]
    output = readonly_myst_build.output
    page_entries = [
        (url, description)
        for name, url, description in readonly_myst_build.entries
        if name == title
    ]
    assert len(page_entries) == 1
    url, description = page_entries[0]
    assert output.joinpath(url).is_file()
    assert body in output.joinpath(url).read_text(encoding="utf-8")
    assert description.strip()


def test_sitemap_uses_authored_myst_description(readonly_myst_build):
    title, _ = PAGES["myst"]
    descriptions = [
        description
        for name, _, description in readonly_myst_build.entries
        if name == title
    ]
    assert descriptions == ["A Markdown page with authored MyST metadata."]
    assert "A Markdown page with authored MyST metadata." in readonly_myst_build.sitemap


@pytest.mark.parametrize("docname", PAGES)
def test_dirhtml_url_suffix_markdown_contains_body(readonly_myst_build, docname):
    if readonly_myst_build.builder != "dirhtml":
        pytest.skip("URL-suffix Markdown files are only generated for dirhtml")
    _, body = PAGES[docname]
    markdown_path = readonly_myst_build.output / f"{docname}.md"
    assert body in markdown_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(("docname", "destination"), LINKS)
def test_html_cross_format_links_resolve(readonly_myst_build, docname, destination):
    page = html_path(readonly_myst_build, docname)
    html = page.read_text(encoding="utf-8")
    html_url = (
        f"{destination}.html"
        if readonly_myst_build.builder == "html"
        else f"../{destination}/"
    )
    assert f'href="{html_url}"' in html
    assert (page.parent / html_url).exists()


@pytest.mark.parametrize(("docname", "destination"), LINKS)
def test_markdown_cross_format_links_resolve(readonly_myst_build, docname, destination):
    page = html_path(readonly_myst_build, docname)
    markdown = page.with_suffix(".html.md").read_text(encoding="utf-8")
    markdown_url = (
        f"{destination}.html.md"
        if readonly_myst_build.builder == "html"
        else f"../{destination}/index.html.md"
    )
    assert f"]({markdown_url})" in markdown
    assert (page.parent / markdown_url).is_file()


def test_myst_code_block_is_converted(readonly_myst_build):
    html, markdown = read_page(readonly_myst_build, "myst")
    assert 'class="highlight-python' in html
    assert '```python\nprint("MyST code survives conversion")\n```' in markdown
    assert 'print("MyST code survives conversion")' in readonly_myst_build.full


def test_myst_list_is_converted(readonly_myst_build):
    html, markdown = read_page(readonly_myst_build, "myst")
    assert "<ul" in html and "Build HTML documentation." in html
    assert "- Build HTML documentation." in markdown


def test_markdown_only_content_is_excluded_from_html(readonly_myst_build):
    html, markdown = read_page(readonly_myst_build, "myst")
    assert "This MyST paragraph appears only in Markdown output." in markdown
    assert "This MyST paragraph appears only in Markdown output." not in html


def test_myst_metadata_is_not_rendered_in_markdown(readonly_myst_build):
    _, markdown = read_page(readonly_myst_build, "myst")
    assert "html_meta:" not in markdown


def test_linked_rst_page_has_markdown(readonly_myst_build):
    output = readonly_myst_build.output
    assert (
        output / "apples.html.md"
        if readonly_myst_build.builder == "html"
        else output / "apples/index.html.md"
    ).is_file()
