# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for reporting and suppressing unknown Markdown node warnings."""

from __future__ import annotations

import os
import subprocess
import sys
from collections import UserList
from pathlib import Path
from types import SimpleNamespace

import pytest
from sphinx.errors import ConfigError

from sphinx_llm.markdown_builder import validate_suppress_unknown_node_warnings

CONFIG_NAME = "llms_txt_suppress_unknown_node_warnings"
SOURCE = """Unknown nodes
=============

First :abbr:`API (application programming interface)`.

Second :abbr:`CPU (central processing unit)`.

.. centered:: Centered child text.

Custom :custom-unknown:`Extension child text`.

Retained paragraph.
"""

CUSTOM_NODE_EXTENSION = """
import sys

from docutils import nodes
from docutils.parsers.rst import roles

class custom_unknown(nodes.Inline, nodes.TextElement):
    pass

def custom_unknown_role(name, rawtext, text, lineno, inliner, options=None, content=None):
    return [custom_unknown(rawtext, text)], []

def passthrough(translator, node):
    pass

def setup(app):
    app.add_node(custom_unknown, html=(passthrough, passthrough))
    app.add_config_value("custom_fail_markdown", False, "env")
    app.add_config_value("custom_invalid_log_bytes", False, "env")
    roles.register_local_role("custom-unknown", custom_unknown_role)
    app.connect(
        "builder-inited",
        lambda app: (sys.stdout.buffer.write(b"\\xff\\n"), sys.stdout.flush())
        if app.builder.name == "llms-markdown" and app.config.custom_invalid_log_bytes
        else None,
    )
    app.connect(
        "build-finished",
        lambda app, exception: (_ for _ in ()).throw(RuntimeError("child failed"))
        if app.builder.name == "llms-markdown" and app.config.custom_fail_markdown
        else None,
    )
"""


def _build(
    tmp_path: Path,
    *,
    value=Ellipsis,
    builder: str = "html",
    parallel: bool = False,
    warning_is_error: bool = False,
    keep_going: bool = True,
    source: str = SOURCE,
    extra_sources: dict[str, str] | None = None,
    fail_child: bool = False,
    invalid_child_log: bool = False,
) -> tuple[subprocess.CompletedProcess[str], str]:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    source_dir.mkdir(parents=True)
    config = [
        "import os, sys",
        'sys.path.insert(0, os.path.abspath("."))',
        'extensions = ["sphinx_llm.txt", "custom_unknown"]',
        'project = "unknown-node-test"',
        'root_doc = "index"',
        f"llms_txt_build_parallel = {parallel!r}",
        f"custom_fail_markdown = {fail_child!r}",
        f"custom_invalid_log_bytes = {invalid_child_log!r}",
    ]
    if value is not Ellipsis:
        config.append(f"{CONFIG_NAME} = {value!r}")
    (source_dir / "conf.py").write_text("\n".join(config), encoding="utf-8")
    (source_dir / "custom_unknown.py").write_text(
        CUSTOM_NODE_EXTENSION, encoding="utf-8"
    )
    (source_dir / "index.rst").write_text(source, encoding="utf-8")
    for name, content in (extra_sources or {}).items():
        (source_dir / name).write_text(content, encoding="utf-8")

    command = [
        sys.executable,
        "-m",
        "sphinx",
        "-E",
        "-a",
        "-b",
        builder,
    ]
    if keep_going:
        command.append("--keep-going")
    if builder == "llms-markdown":
        command.extend(["-t", "sphinx_llm_markdown"])
    if warning_is_error:
        command.append("-W")
    command.extend([str(source_dir), str(output_dir)])
    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
        encoding="utf-8",
        env=os.environ.copy(),
    )
    markdown_name = "index.html.md" if builder == "html" else "index.md"
    markdown_path = output_dir / markdown_name
    markdown = (
        markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
    )
    return result, markdown


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def _assert_all_unknown_warnings(output: str) -> None:
    assert output.count("WARNING:") == 3
    assert output.count("unknown node type: <abbreviation:") == 1
    assert output.count("unknown node type: <centered:") == 1
    assert output.count("unknown node type: <custom_unknown:") == 1
    assert "index.rst:4: WARNING: unknown node type: <abbreviation:" in output


def _assert_unknown_content_omitted(markdown: str) -> None:
    assert "API" not in markdown
    assert "CPU" not in markdown
    assert "Centered child text" not in markdown
    assert "Extension child text" not in markdown
    assert "Retained paragraph." in markdown


@pytest.mark.parametrize("parallel", [False, True], ids=["sequential", "parallel"])
def test_primary_build_surfaces_unknown_node_warnings_by_default(tmp_path, parallel):
    result, markdown = _build(tmp_path, parallel=parallel)

    assert result.returncode == 0
    _assert_all_unknown_warnings(_output(result))
    _assert_unknown_content_omitted(markdown)


@pytest.mark.parametrize("parallel", [False, True], ids=["sequential", "parallel"])
def test_primary_unknown_node_warnings_respect_warning_is_error(tmp_path, parallel):
    result, markdown = _build(tmp_path, parallel=parallel, warning_is_error=True)

    assert result.returncode == 1
    _assert_all_unknown_warnings(_output(result))
    _assert_unknown_content_omitted(markdown)


@pytest.mark.parametrize("parallel", [False, True], ids=["sequential", "parallel"])
def test_primary_warning_is_error_without_keep_going(tmp_path, parallel):
    result, markdown = _build(
        tmp_path,
        parallel=parallel,
        warning_is_error=True,
        keep_going=False,
    )

    assert result.returncode == 1
    _assert_all_unknown_warnings(_output(result))
    _assert_unknown_content_omitted(markdown)
    assert not (tmp_path / "output" / "_markdown_build").exists()


def test_primary_relay_preserves_distinct_document_locations(tmp_path):
    source = SOURCE + "\n.. toctree::\n   :hidden:\n\n   second\n"
    result, _ = _build(
        tmp_path,
        source=source,
        extra_sources={
            "second.rst": "Second page\n===========\n\nAn :abbr:`SDK (kit)`.\n"
        },
    )

    output = _output(result)
    assert result.returncode == 0
    assert output.count("unknown node type: <abbreviation:") == 2
    assert "index.rst:4: WARNING: unknown node type: <abbreviation:" in output
    assert "second.rst:4: WARNING: unknown node type: <abbreviation:" in output


@pytest.mark.parametrize("parallel", [False, True], ids=["sequential", "parallel"])
def test_true_suppresses_all_primary_unknown_node_warnings(tmp_path, parallel):
    result, markdown = _build(
        tmp_path, value=True, parallel=parallel, warning_is_error=True
    )

    assert result.returncode == 0
    assert "unknown node type" not in _output(result)
    _assert_unknown_content_omitted(markdown)


@pytest.mark.parametrize("parallel", [False, True], ids=["sequential", "parallel"])
def test_selective_suppression_leaves_unmatched_primary_warnings(tmp_path, parallel):
    result, markdown = _build(
        tmp_path,
        value=["abbreviation"],
        parallel=parallel,
        warning_is_error=True,
    )

    output = _output(result)
    assert result.returncode == 1
    assert "unknown node type: <abbreviation:" not in output
    assert output.count("unknown node type: <centered:") == 1
    assert output.count("unknown node type: <custom_unknown:") == 1
    _assert_unknown_content_omitted(markdown)


@pytest.mark.parametrize(
    "value",
    [False, [], ["Abbreviation"], ["abbreviation", "abbreviation"]],
    ids=["false", "empty", "case-mismatch", "duplicates"],
)
def test_false_empty_mismatched_and_duplicate_names_use_exact_matching(tmp_path, value):
    result, _ = _build(tmp_path, value=value)

    output = _output(result)
    assert result.returncode == 0
    if isinstance(value, list) and "abbreviation" in value:
        assert "unknown node type: <abbreviation:" not in output
        assert output.count("unknown node type: <centered:") == 1
        assert output.count("unknown node type: <custom_unknown:") == 1
    else:
        _assert_all_unknown_warnings(output)


def test_tuple_can_suppress_all_exact_node_names(tmp_path):
    result, markdown = _build(
        tmp_path,
        value=("abbreviation", "centered", "custom_unknown"),
        warning_is_error=True,
    )

    assert result.returncode == 0
    assert "unknown node type" not in _output(result)
    _assert_unknown_content_omitted(markdown)


def test_suppression_changes_only_diagnostics_not_markdown(tmp_path):
    default, default_markdown = _build(tmp_path / "default")
    suppressed, suppressed_markdown = _build(tmp_path / "suppressed", value=True)

    assert default.returncode == 0
    assert suppressed.returncode == 0
    assert default_markdown == suppressed_markdown
    _assert_unknown_content_omitted(suppressed_markdown)


@pytest.mark.parametrize(
    ("value", "expected_warning_count"),
    [
        (Ellipsis, 3),
        (False, 3),
        (True, 0),
        (["abbreviation"], 2),
        (("abbreviation",), 2),
        ([], 3),
        (["Abbreviation"], 3),
        (["abbreviation", "abbreviation"], 2),
    ],
    ids=[
        "default",
        "false",
        "true",
        "selective-list",
        "tuple",
        "empty",
        "exact-name-mismatch",
        "duplicates",
    ],
)
def test_direct_llms_markdown_suppression_contract(
    tmp_path, value, expected_warning_count
):
    result, markdown = _build(tmp_path, value=value, builder="llms-markdown")

    assert result.returncode == 0
    assert _output(result).count("unknown node type:") == expected_warning_count
    _assert_unknown_content_omitted(markdown)


@pytest.mark.parametrize(
    "value",
    [
        "abbreviation",
        b"abbreviation",
        bytearray(b"abbreviation"),
        None,
        1,
        {"abbreviation"},
        {"node": "abbreviation"},
    ],
)
def test_invalid_top_level_values_raise_config_error(value):
    config = SimpleNamespace(**{CONFIG_NAME: value})

    with pytest.raises(ConfigError, match=CONFIG_NAME):
        validate_suppress_unknown_node_warnings(None, config)


def test_valid_sequence_is_normalized_to_a_stable_tuple():
    config = SimpleNamespace(
        **{CONFIG_NAME: UserList(["abbreviation", "abbreviation"])}
    )

    validate_suppress_unknown_node_warnings(None, config)

    assert getattr(config, CONFIG_NAME) == ("abbreviation", "abbreviation")


@pytest.mark.parametrize(
    "value", [[1], [""], [" centered"], ["centered "], ["nodes.centered"]]
)
def test_invalid_sequence_entries_raise_config_error(value):
    config = SimpleNamespace(**{CONFIG_NAME: value})

    with pytest.raises(ConfigError, match=CONFIG_NAME):
        validate_suppress_unknown_node_warnings(None, config)


def test_invalid_config_fails_during_sphinx_initialization(tmp_path):
    result, _ = _build(tmp_path, value="abbreviation")

    assert result.returncode == 2
    assert CONFIG_NAME in _output(result)
    assert "must be a bool or a non-string sequence" in _output(result)


def test_suppression_does_not_hide_unrelated_primary_warnings(tmp_path):
    result, _ = _build(
        tmp_path,
        value=True,
        source=SOURCE + "\nMissing :doc:`document`.\n",
    )

    output = _output(result)
    assert result.returncode == 0
    assert "unknown node type" not in output
    assert "unknown document: 'document'" in output


def test_direct_suppression_does_not_hide_unrelated_warnings(tmp_path):
    result, _ = _build(
        tmp_path,
        value=True,
        builder="llms-markdown",
        warning_is_error=True,
        source=SOURCE + "\nMissing :doc:`document`.\n",
    )

    output = _output(result)
    assert result.returncode == 1
    assert "unknown node type" not in output
    assert "unknown document: 'document'" in output


def test_failed_child_unknown_warnings_are_relayed_only_once(tmp_path):
    result, _ = _build(tmp_path, fail_child=True)

    output = _output(result)
    assert output.count("unknown node type: <abbreviation:") == 1
    assert output.count("unknown node type: <centered:") == 1
    assert output.count("unknown node type: <custom_unknown:") == 1
    assert "Markdown build subprocess failed with return code" in output
    assert "child failed" in output


def test_invalid_child_log_bytes_do_not_prevent_relay_or_cleanup(tmp_path):
    result, markdown = _build(tmp_path, invalid_child_log=True)

    assert result.returncode == 0
    _assert_all_unknown_warnings(_output(result))
    _assert_unknown_content_omitted(markdown)
    assert not (tmp_path / "output" / "_markdown_build").exists()


def test_native_markdown_builder_is_not_affected(tmp_path):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    source_dir.mkdir()
    (source_dir / "conf.py").write_text(
        "\n".join(
            [
                "import os, sys",
                'sys.path.insert(0, os.path.abspath("."))',
                'extensions = ["sphinx_markdown_builder", "custom_unknown"]',
                'project = "native-markdown-test"',
                'root_doc = "index"',
            ]
        ),
        encoding="utf-8",
    )
    (source_dir / "custom_unknown.py").write_text(
        CUSTOM_NODE_EXTENSION, encoding="utf-8"
    )
    (source_dir / "index.rst").write_text(SOURCE, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-E",
            "-a",
            "--keep-going",
            "-b",
            "markdown",
            "-W",
            str(source_dir),
            str(output_dir),
        ],
        capture_output=True,
        check=False,
        encoding="utf-8",
        env=os.environ.copy(),
    )
    markdown = (output_dir / "index.md").read_text(encoding="utf-8")

    assert result.returncode == 1
    _assert_all_unknown_warnings(_output(result))
    _assert_unknown_content_omitted(markdown)
