# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for format-specific raw content in Markdown output."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SOURCE = """Raw content
===========

Before :inline-raw:`icon` after.

.. raw:: html

   <b id="raw-html-block">HTML only</b>

.. raw:: markdown

   **markdown-only**

.. raw:: md

   _md-only_

.. raw:: html markdown

   `mixed-format`
"""


def _write_project(source_dir: Path, *, full_build: bool = False) -> None:
    source_dir.mkdir()
    (source_dir / "conf.py").write_text(
        'extensions = ["sphinx_llm.txt"]\n'
        'project = "raw-node-test"\n'
        'root_doc = "index"\n'
        f"llms_txt_full_build = {full_build!r}\n"
        "from docutils import nodes\n"
        "from docutils.parsers.rst import roles\n"
        "def inline_raw_role(name, rawtext, text, lineno, inliner, options=None, "
        "content=None):\n"
        "    node = nodes.raw(rawtext, '<svg id=\"raw-html-inline\"></svg>', "
        "format='html')\n"
        "    return [node], []\n"
        "roles.register_local_role('inline-raw', inline_raw_role)\n",
        encoding="utf-8",
    )
    (source_dir / "index.rst").write_text(SOURCE, encoding="utf-8")


def _run_sphinx(source_dir: Path, output_dir: Path, builder: str) -> None:
    if builder == "llms-markdown":
        command = [
            sys.executable,
            "-c",
            "from pathlib import Path; from sphinx.application import Sphinx; "
            "import sys; source, output = map(Path, sys.argv[1:]); "
            "app = Sphinx(srcdir=source, confdir=source, outdir=output, "
            "doctreedir=output / '.doctrees', buildername='llms-markdown', "
            "freshenv=True, warningiserror=True, tags=('sphinx_llm_markdown',)); "
            "app.build(force_all=True); raise SystemExit(app.statuscode)",
            str(source_dir),
            str(output_dir),
        ]
    else:
        command = [
            sys.executable,
            "-m",
            "sphinx",
            "-W",
            "-E",
            "-a",
            "-b",
            builder,
            str(source_dir),
            str(output_dir),
        ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _assert_markdown_raw_filtering(markdown: str) -> None:
    assert "raw-html-inline" not in markdown
    assert "raw-html-block" not in markdown
    assert "Before  after." in markdown
    assert markdown.count("**markdown-only**") == 1
    assert markdown.count("_md-only_") == 1
    assert markdown.count("`mixed-format`") == 1


def test_llms_markdown_filters_raw_nodes_by_format(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "markdown"
    _write_project(source_dir)

    _run_sphinx(source_dir, output_dir, "llms-markdown")

    _assert_markdown_raw_filtering(
        (output_dir / "index.md").read_text(encoding="utf-8")
    )


def test_generated_outputs_filter_html_raw_nodes(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "html"
    _write_project(source_dir, full_build=True)

    _run_sphinx(source_dir, output_dir, "html")

    html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "raw-html-inline" in html
    assert "raw-html-block" in html
    _assert_markdown_raw_filtering(
        (output_dir / "index.html.md").read_text(encoding="utf-8")
    )
    _assert_markdown_raw_filtering(
        (output_dir / "llms-full.txt").read_text(encoding="utf-8")
    )
