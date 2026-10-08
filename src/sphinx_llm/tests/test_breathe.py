# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Verify rendered API content from real Doxygen XML through Breathe."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("builder", ["html", "dirhtml"])
@pytest.mark.parametrize("parallel", [False, True])
def test_breathe_api_output(tmp_path: Path, builder: str, parallel: bool):
    source = tmp_path / "source"
    source.mkdir()
    shutil.copytree(
        Path(__file__).parent / "fixtures" / "breathe" / "xml", source / "xml"
    )
    (source / "conf.py").write_text(
        'extensions = ["breathe", "sphinx_llm.txt"]\n'
        'project = "Breathe regression"\n'
        'breathe_projects = {"api": "xml"}\n'
        'breathe_default_project = "api"\n'
        "markdown_anchor_signatures = True\n"
        "llms_txt_full_build = True\n"
        f"llms_txt_build_parallel = {parallel!r}\n"
    )
    (source / "index.rst").write_text(
        "API reference\n=============\n\n.. toctree::\n\n   function\n   types\n"
    )
    (source / "function.rst").write_text(
        "Functions\n=========\n\n.. doxygenfunction:: add\n"
    )
    (source / "types.rst").write_text(
        "Types\n=====\n\n.. doxygenstruct:: Widget\n   :members:\n\n"
        ".. doxygenenum:: Mode\n"
    )
    output = tmp_path / "output"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-E",
            "-W",
            "-b",
            builder,
            str(source),
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    def page(name):
        return output / (
            f"{name}.html.md" if builder == "html" else f"{name}/index.html.md"
        )

    function = page("function").read_text()
    types = page("types").read_text()
    for content in (
        "int add(int left, int right)",
        "Add two item counts.",
        "The detailed description survives the Markdown build.",
        "**left**",
        "First item count.",
        "**right**",
        "Second item count.",
        "**Returns:**",
        "Combined item count.",
        "```",
        "add(2, 3);",
    ):
        assert content in function
    for content in (
        "struct Widget",
        "A widget with a documented member.",
        "int count",
        "Number of items in the widget.",
        "enum Mode",
        "Available processing modes.",
        "All",
        "Process every item.",
        "First",
        "Process only the first item.",
    ):
        assert content in types
    assert not re.search(r"^#+\s*$", function + types, re.MULTILINE)

    # Doxygen's see-also reference must point to a published page and anchor.
    target = re.search(r"\[Widget\]\(([^)]+)\)", function)
    assert target is not None, function
    path, fragment = target.group(1).split("#")
    linked_page = (page("function").parent / path).resolve()
    assert linked_page == page("types").resolve()
    assert f'<a id="{fragment}"></a>' in linked_page.read_text()

    sitemap = (output / "llms.txt").read_text()
    for name in ("function", "types"):
        assert page(name).relative_to(output).as_posix() in sitemap
    full = (output / "llms-full.txt").read_text()
    assert "Add two item counts." in full
    assert "A widget with a documented member." in full
