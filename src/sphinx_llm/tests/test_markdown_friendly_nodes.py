# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the MarkdownFriendlyNodesTransform post-transform.
"""

from __future__ import annotations

import base64
from pathlib import Path

from sphinx.application import Sphinx

# A valid 1x1 transparent PNG, for exercising figure captions and legends.
PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def test_unsupported_nodes_are_converted_to_markdown(tmp_path: Path):
    """Nodes sphinx-markdown-builder would drop are kept in the markdown output."""
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    source_dir.mkdir()

    (source_dir / "conf.py").write_text(
        'extensions = ["sphinx_llm.txt"]\n'
        'project = "Markdown-friendly nodes test"\n'
        'root_doc = "index"\n'
        "llms_txt_build_parallel = False\n",
        encoding="utf-8",
    )
    (source_dir / "pixel.png").write_bytes(PIXEL_PNG)
    (source_dir / "index.rst").write_text(
        "Index\n"
        "=====\n\n"
        ".. tip::\n\n"
        "   Tip admonition body.\n\n"
        ".. caution::\n\n"
        "   Caution admonition body.\n\n"
        ".. admonition:: Custom Admonition Title\n\n"
        "   Generic admonition body.\n\n"
        ".. sidebar:: Sidebar Title\n\n"
        "   Sidebar body.\n\n"
        "A sentence with an :abbr:`LLM (Large Language Model)` "
        "in the middle.\n\n"
        ".. figure:: pixel.png\n\n"
        "   Figure caption text.\n\n"
        "   Figure legend paragraph.\n",
        encoding="utf-8",
    )

    app = Sphinx(
        srcdir=str(source_dir),
        confdir=str(source_dir),
        outdir=str(output_dir),
        doctreedir=str(tmp_path / "doctrees"),
        buildername="html",
        warningiserror=False,
    )
    app.build()

    markdown = (output_dir / "index.html.md").read_text(encoding="utf-8")

    # Tip and caution admonitions are mapped to supported flavors.
    assert "Tip admonition body." in markdown
    assert "Caution admonition body." in markdown

    # Generic admonitions and sidebars become a bold title and their content.
    assert "**Custom Admonition Title**" in markdown
    assert "Generic admonition body." in markdown
    assert "**Sidebar Title**" in markdown
    assert "Sidebar body." in markdown

    # Abbreviations keep their text instead of losing words mid-sentence.
    assert "A sentence with an LLM in the middle." in markdown

    # Figure captions and legends become regular (emphasized) content.
    assert "*Figure caption text.*" in markdown
    assert "Figure legend paragraph." in markdown
