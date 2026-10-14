# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Exercise the repository's MyST sources through both documentation builds."""

import re
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("builder", ["html", "dirhtml"])
@pytest.mark.parametrize("parallel", [False, True])
def test_myst_documentation_outputs(tmp_path: Path, builder: str, parallel: bool):
    source = Path(__file__).resolve().parents[3] / "docs" / "source"
    output = tmp_path / "build"
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
            str(source),
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    sitemap = (output / "llms.txt").read_text(encoding="utf-8")
    full = (output / "llms-full.txt").read_text(encoding="utf-8")
    entries = re.findall(r"^- \[([^]]+)\]\(([^)]+)\): (.+)$", sitemap, re.MULTILINE)

    pages = {
        "myst": ("MyST Markdown example", "Markdown sources share the Sphinx build"),
        "myst-links": ("Links from Markdown", "Cross-format links connect Markdown"),
    }
    for docname, (title, body) in pages.items():
        html_path = output / (
            f"{docname}.html" if builder == "html" else f"{docname}/index.html"
        )
        html = html_path.read_text(encoding="utf-8")
        markdown = html_path.with_suffix(".html.md").read_text(encoding="utf-8")
        assert title in html and title in markdown
        assert body in html and body in markdown and body in full
        assert full.count(body) == 1
        page_entries = [
            (url, description) for name, url, description in entries if name == title
        ]
        assert len(page_entries) == 1
        url, description = page_entries[0]
        assert output.joinpath(url).is_file()
        assert body in output.joinpath(url).read_text(encoding="utf-8")
        assert description.strip()
        if docname == "myst":
            assert description == "A Markdown page with authored MyST metadata."
        if builder == "dirhtml":
            assert body in (output / f"{docname}.md").read_text(encoding="utf-8")

        target = "myst-links" if docname == "myst" else "myst"
        for destination in (target, "apples"):
            html_url = (
                f"{destination}.html" if builder == "html" else f"../{destination}/"
            )
            assert f'href="{html_url}"' in html
            assert (html_path.parent / html_url).exists()
            markdown_url = (
                f"{destination}.html.md"
                if builder == "html"
                else f"../{destination}/index.html.md"
            )
            assert f"]({markdown_url})" in markdown
            assert (html_path.parent / markdown_url).is_file()

    myst_html = output / ("myst.html" if builder == "html" else "myst/index.html")
    html = myst_html.read_text(encoding="utf-8")
    assert 'class="highlight-python' in html
    assert "<ul" in html and "Build HTML documentation." in html
    myst_markdown = myst_html.with_suffix(".html.md").read_text(encoding="utf-8")
    assert "- Build HTML documentation." in myst_markdown
    assert '```python\nprint("MyST code survives conversion")\n```' in myst_markdown
    assert 'print("MyST code survives conversion")' in full
    assert "This MyST paragraph appears only in Markdown output." in myst_markdown
    assert (
        "This MyST paragraph appears only in Markdown output."
        not in myst_html.read_text(encoding="utf-8")
    )
    assert "A Markdown page with authored MyST metadata." in sitemap
    assert "html_meta:" not in myst_markdown
    assert (
        output / "apples.html.md"
        if builder == "html"
        else output / "apples/index.html.md"
    ).is_file()
