# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Integration tests for documentation context in generated Markdown."""

import subprocess
import sys

import pytest
import yaml

AUTHOR = 'Docs: "Team" #1 & <contributors> — 日本語\nSecond line'


def _build(
    tmp_path,
    *,
    builder="html",
    parallel=False,
    settings=None,
    overrides=(),
    local_docinfo=":author: Local author\n",
):
    source = tmp_path / "source"
    source.mkdir(parents=True)
    config = {
        "extensions": ["sphinx_markdown_builder", "sphinx_llm.txt"],
        "project": "Example software",
        "author": AUTHOR,
        "copyright": "2026, Example team",
        "version": "0.6",
        "release": "0.6.01rc1.dev2",
        "llms_txt_build_parallel": parallel,
        "llms_txt_full_build": True,
        "llms_txt_suppress_unknown_node_warnings": ["meta"],
    }
    config.update(settings or {})
    (source / "conf.py").write_text(
        "\n".join(f"{key} = {value!r}" for key, value in config.items()),
        encoding="utf-8",
    )
    (source / "index.rst").write_text(
        "Home\n====\n\nThe actual introduction paragraph.\n\n"
        ".. toctree::\n\n   nested/page\n   authored\n",
        encoding="utf-8",
    )
    (source / "nested").mkdir()
    (source / "nested/page.rst").write_text(
        local_docinfo + "\nNested page\n===========\n\n"
        "The nested body paragraph.\n\n.. _details:\n\nDetails\n-------\n\n"
        "Return to :doc:`/index` or :ref:`details`.\n",
        encoding="utf-8",
    )
    (source / "authored.rst").write_text(
        ".. meta::\n   :description: Authored page description.\n\n"
        "Authored page\n=============\n\nThe authored body paragraph.\n",
        encoding="utf-8",
    )
    output = tmp_path / "output"
    command = [sys.executable, "-m", "sphinx", "-E", "-a", "-b", builder]
    for override in overrides:
        command.extend(["-D", override])
    command.extend([str(source), str(output)])
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Markdown build subprocess failed" not in result.stdout + result.stderr
    return output


def _frontmatter(path):
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---\n"), content
    frontmatter, body = content[4:].split("\n---\n", 1)
    assert "\n---\n" not in body
    assert "<meta " not in content
    metadata = yaml.safe_load(frontmatter)
    assert len(yaml.compose(frontmatter).value) == len(metadata)
    return metadata, body


@pytest.mark.parametrize(
    ("builder", "parallel", "suffix"),
    [
        ("html", True, "auto"),
        ("html", False, "both"),
        ("dirhtml", True, "auto"),
        ("dirhtml", False, "both"),
        ("html", False, "replace"),
        ("dirhtml", False, "url-suffix"),
        ("dirhtml", True, "file-suffix"),
    ],
)
def test_docinfo_default(tmp_path, builder, parallel, suffix):
    output = _build(
        tmp_path,
        builder=builder,
        parallel=parallel,
        settings={"llms_txt_suffix_mode": suffix, "markdown_docinfo": False},
    )
    expected = {
        "project": "Example software",
        "author": AUTHOR,
        "copyright": "2026, Example team",
        "version": "0.6",
        "release": "0.6.01rc1.dev2",
    }
    pages = list(output.rglob("*.md"))
    assert len(pages) >= 3
    for page in pages:
        metadata, body = _frontmatter(page)
        if "nested" in page.relative_to(output).parts:
            assert metadata == {**expected, "author": "Local author"}
            assert "The nested body paragraph." in body
            assert '<a id="details"></a>' in body
            assert "sphinx-llm:" not in body
            assert "[Home](" in body
        else:
            assert metadata == expected
            assert "# Home" in body or "# Authored page" in body
    sitemap = (output / "llms.txt").read_text()
    assert "The actual introduction paragraph." in sitemap
    assert "The nested body paragraph." in sitemap
    assert "Authored page description." in sitemap
    assert '"author":' not in sitemap
    assert "Second line" not in sitemap
    nested_sitemap = (output / "nested/llms.txt").read_text()
    assert "The nested body paragraph." in nested_sitemap
    full = (output / "llms-full.txt").read_text()
    assert full.count("\n---\n") == 6  # three complete per-page blocks
    assert full.count('"version": "0.6"') == 3
    assert "The actual introduction paragraph." in full
    assert 'rel="alternate"' in (output / "index.html").read_text()


@pytest.mark.parametrize("parallel", [True, False])
@pytest.mark.parametrize("upstream", [True, False])
def test_docinfo_opt_out(tmp_path, parallel, upstream):
    output = _build(
        tmp_path,
        parallel=parallel,
        settings={
            "llms_txt_docinfo": False,
            "markdown_docinfo": upstream,
        },
    )
    for page in output.rglob("*.md"):
        assert not page.read_text().startswith("---\n")
        assert "<meta " not in page.read_text()
    assert "<meta" in (output / "authored.html").read_text()


@pytest.mark.parametrize("parallel", [True, False])
def test_docinfo_cli_overrides(tmp_path, parallel):
    enabled = _build(
        tmp_path / "enabled",
        parallel=parallel,
        settings={"llms_txt_docinfo": False},
        overrides=[
            "llms_txt_docinfo=1",
            "markdown_docinfo=0",
            "version=01.0",
            "release=1.0",
        ],
    )
    metadata, _ = _frontmatter(enabled / "index.html.md")
    assert metadata["version"] == "01.0"
    assert metadata["release"] == "1.0"
    disabled = _build(
        tmp_path / "disabled",
        parallel=parallel,
        overrides=["llms_txt_docinfo=0", "markdown_docinfo=1"],
    )
    assert not (disabled / "index.html.md").read_text().startswith("---\n")


def test_docinfo_empty_versions(tmp_path):
    output = _build(tmp_path, settings={"version": "", "release": ""})
    metadata, _ = _frontmatter(output / "index.html.md")
    assert "version" not in metadata
    assert "release" not in metadata


def test_local_empty_values_and_page_isolation(tmp_path):
    output = _build(
        tmp_path, local_docinfo=":author: Local author\n:version: 001.0\n:release:\n"
    )
    local, _ = _frontmatter(output / "nested/page.html.md")
    assert local["author"] == "Local author"
    assert local["version"] == "001.0"
    assert "release" not in local
    root, _ = _frontmatter(output / "index.html.md")
    assert root["author"] == AUTHOR
    assert root["version"] == "0.6"
    assert root["release"] == "0.6.01rc1.dev2"


def test_strip_docinfo_preserves_body_and_authored_delimiters():
    from sphinx_llm.markdown_builder import strip_docinfo

    body = '# Body\n\n---\n\n<meta name="version" content="authored"/>\n'
    generated = '---\n"version": "0.6"\n---\n\n'
    assert strip_docinfo(generated + body) == body
    authored = "---\ncustom: authored value\n---\n\n" + body
    assert strip_docinfo(authored) == authored


@pytest.mark.parametrize("enabled", [True, False])
def test_native_markdown_docinfo_unchanged(tmp_path, enabled):
    output = _build(
        tmp_path, builder="markdown", settings={"markdown_docinfo": enabled}
    )
    content = (output / "index.md").read_text()
    assert ('<meta name="version" content="0.6"/>' in content) is enabled
    assert not content.startswith("---\n")


def test_custom_index_and_exclusions(tmp_path):
    output = _build(
        tmp_path,
        settings={
            "llms_txt_override_source": "index",
            "llms_txt_exclude": ["nested/**"],
        },
    )
    index = (output / "llms.txt").read_text()
    assert index.startswith("# Home")
    assert '"version":' not in index
    assert '"version":' in (output / "nested/page.html.md").read_text()
    assert "The nested body paragraph." not in (output / "llms-full.txt").read_text()


def test_disabled_extension(tmp_path):
    output = _build(tmp_path, settings={"llms_txt_enabled": False})
    assert not list(output.rglob("*.md"))
    assert not (output / "llms.txt").exists()
