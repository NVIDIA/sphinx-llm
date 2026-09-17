# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Focused regressions for generated llms.txt file-list serialization."""

from __future__ import annotations

import html
import posixpath
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote, unquote, urlsplit

import pytest

from sphinx_llm.txt import (
    MarkdownGenerator,
    _serialize_sitemap_entry,
    _strip_summary_links,
)


def _generator(tmp_path: Path, http_base: str = "") -> MarkdownGenerator:
    config = SimpleNamespace(
        _raw_config={"markdown_http_base": http_base},
        copyright="",
        llms_txt_exclude=[],
        markdown_http_base=http_base,
        project="Serialization test",
    )
    app = SimpleNamespace(config=config, builder=SimpleNamespace(name="html"))
    generator = MarkdownGenerator(app)
    generator.outdir = tmp_path
    generator.suffix_mode = "auto"
    return generator


@pytest.mark.parametrize("builder", ["html", "dirhtml"])
@pytest.mark.parametrize("nested", [False, True], ids=["root", "nested"])
@pytest.mark.parametrize("absolute", [False, True], ids=["relative", "absolute"])
def test_generated_entries_round_trip_markdown_edges(
    tmp_path: Path, builder: str, nested: bool, absolute: bool
) -> None:
    """Generated fields stay parseable, readable, and artifact-resolving."""
    http_base = "https://example.test/docs%20base/(archive)" if absolute else ""
    generator = _generator(tmp_path, http_base)
    generator.app.builder.name = builder

    scope = Path("nested area") if nested else Path()
    page_name = "API [β](v2): 100% \\ draft? #1"
    artifact = scope / page_name
    artifact = (
        artifact.with_suffix(".html.md")
        if builder == "html"
        else artifact / "index.html.md"
    )
    artifact = tmp_path / artifact
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("# generated artifact\n", encoding="utf-8")

    title = "API [β]\n(v2): `path` &copy; <tag> *star* _under_ \\"
    normalized_title = "API [β] (v2): `path` &copy; <tag> *star* _under_ \\"
    description = (
        "Read [the guide](other.md): café\\\r\n"
        "then `code` &copy; <tag> *stars* _under_."
    )
    normalized_description = (
        "Read the guide: café\\ then `code` &copy; <tag> *stars* _under_."
    )
    generator._docname_by_output_file[artifact] = "edge"
    generator.extract_title_from_markdown = lambda _: title
    generator.get_page_description = lambda _: description

    index = tmp_path / scope / "llms.txt"
    generator._write_sitemap(index, [artifact], subsection=nested)

    content = index.read_text(encoding="utf-8")
    page_lines = [line for line in content.splitlines() if line.startswith("- [API")]
    assert len(page_lines) == 1
    assert "_under_" not in page_lines[0]
    assert page_lines[0].count("&#95;under&#95;") == 2
    parse_llms_file = pytest.importorskip("llms_txt").parse_llms_file
    parsed = parse_llms_file(content)
    pages_heading = "Pages in this subsection" if nested else "Pages"
    assert len(parsed.sections[pages_heading]) == 1
    entry = parsed.sections[pages_heading][0]

    assert html.unescape(entry.title) == normalized_title
    assert html.unescape(entry.desc) == normalized_description
    assert "other.md" not in entry.desc
    assert "\n" not in entry.title
    assert "\n" not in entry.desc

    if absolute:
        expected_url = "https://example.test/docs%20base/%28archive%29/" + quote(
            artifact.relative_to(tmp_path).as_posix(), safe="/"
        )
        parsed_path = urlsplit(entry.url).path
        base_path = quote(urlsplit(http_base).path, safe="/%").rstrip("/") + "/"
        assert parsed_path.startswith(base_path)
        resolved = tmp_path / unquote(parsed_path.removeprefix(base_path))
    else:
        relative_target = posixpath.relpath(
            artifact.relative_to(tmp_path).as_posix(),
            start=index.parent.relative_to(tmp_path).as_posix() or ".",
        )
        expected_url = quote(relative_target, safe="/")
        resolved = (index.parent / unquote(entry.url)).resolve()

    assert entry.url == expected_url
    assert "%2520base" not in entry.url
    assert resolved == artifact.resolve()
    assert resolved.is_file()


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        (
            "Read [Callback API](python_api.html.md#callback-api) for details.",
            "Read Callback API for details.",
        ),
        (
            "Read [the **Callback API**](python_api.html.md#callback-api) "
            "and ![callback flow](images/callback.png).",
            "Read the **Callback API** and callback flow.",
        ),
        (
            "Compare [callbacks][callback-ref], [events][], and [the guide].\n\n"
            "[callback-ref]: callbacks.md\n"
            "[events]: events.md\n"
            "[the guide]: guide.md",
            "Compare callbacks, events, and the guide.",
        ),
        (
            "Visit <https://example.test/docs> or <docs@example.test>.",
            "Visit https://example.test/docs or docs@example.test.",
        ),
        (
            'Use [callbacks](<python_(v2).html.md> "API") and '
            "[events](events\\(old\\).md).",
            "Use callbacks and events.",
        ),
        (
            'Use [callbacks]( <callbacks.md> ) and [events](events.md "Event\nAPI").',
            "Use callbacks and events.",
        ),
        (
            "Read [Callback API][api].\n\n[api]:\n  python_api.html.md#callback-api",
            "Read Callback API.",
        ),
        ("A useful summary without links.", "A useful summary without links."),
    ],
)
def test_generated_summary_strips_links_but_keeps_readable_text(
    tmp_path: Path, description: str, expected: str
) -> None:
    """Relocated summaries keep their prose without Markdown destinations."""
    generator = _generator(tmp_path)
    artifact = tmp_path / "python" / "callbacks.html.md"
    artifact.parent.mkdir()
    artifact.write_text("# Callbacks\n", encoding="utf-8")
    generator._docname_by_output_file[artifact] = "python/callbacks"
    generator.extract_title_from_markdown = lambda _: "Callbacks"
    generator.get_page_description = lambda _: description

    index = tmp_path / "llms.txt"
    generator._write_sitemap(index, [artifact])

    parse_llms_file = pytest.importorskip("llms_txt").parse_llms_file
    entry = parse_llms_file(index.read_text(encoding="utf-8")).sections["Pages"][0]
    assert html.unescape(entry.desc) == expected
    assert "python_api.html.md#callback-api" not in entry.desc
    assert "images/callback.png" not in entry.desc


@pytest.mark.parametrize(
    "summary",
    [
        "A useful summary without links.",
        "A [bracketed] note with an unresolved [reference][missing].",
        r"Escaped \[label](destination.md) and `[code](destination.md)`.",
        "Not links: [label](two words) or [label](<two<words>).",
        "Plain text: [literal](not-a-link\\ space).",
        "```\n[api]: callbacks.md\n```\nUnresolved [Callback API][api].",
        "Unsafe URI <javascript:alert(1)> and invalid <a@b_c.example>.",
        "Unused definition.\n\n[api]: callbacks.md",
    ],
)
def test_strip_summary_links_leaves_non_links_unchanged(summary: str) -> None:
    """Ordinary brackets, escapes, code, and plain prose are not corrupted."""
    assert _strip_summary_links(summary) == summary


def test_strip_summary_links_handles_nested_labels_and_multiple_links() -> None:
    """Nested formatting and image alt text remain useful without destinations."""
    summary = (
        "See [the **API** and ![diagram](diagram.png)](guide_(v2).md) or "
        '[examples](examples.md "Examples ) here").'
    )
    assert _strip_summary_links(summary) == ("See the **API** and diagram or examples.")


def test_strip_summary_links_keeps_reference_context_in_nested_image() -> None:
    """A linked reference image becomes its useful alt text."""
    summary = "See [![diagram][img]](callbacks.md).\n\n[img]: callback.png"
    assert _strip_summary_links(summary) == "See diagram."


@pytest.mark.parametrize(
    ("destination", "expected"),
    [
        ("guide/page.md", "guide/page.md"),
        ("../llms.txt", "../llms.txt"),
        (
            "first:segment\\file (draft)[1].md",
            "first%3Asegment%5Cfile%20%28draft%29%5B1%5D.md",
        ),
        (
            "https://example.test/docs%20base/(archive)/page.md?q=(x)#part(y)",
            "https://example.test/docs%20base/%28archive%29/page.md?"
            "q=%28x%29#part%28y%29",
        ),
        (
            "https://user(name):pass%20word@[2001:db8::1]/docs/page.md",
            "https://user%28name%29:pass%20word@[2001:db8::1]/docs/page.md",
        ),
    ],
)
def test_generated_destination_serialization(destination: str, expected: str) -> None:
    """Generated destinations are safe while ordinary URI syntax is retained."""
    assert (
        _serialize_sitemap_entry("Title", destination, "Description")
        == f"- [Title]({expected}): Description"
    )


def test_generated_ordinary_entry_keeps_existing_output(tmp_path: Path) -> None:
    """Plain generated content does not change byte source representation."""
    generator = _generator(tmp_path)
    artifact = tmp_path / "guide" / "page.html.md"
    artifact.parent.mkdir()
    artifact.write_text("# Plain Title\n", encoding="utf-8")
    generator._docname_by_output_file[artifact] = "guide/page"
    generator.extract_title_from_markdown = lambda _: "Plain Title"
    generator.get_page_description = lambda _: "Plain description."

    index = tmp_path / "llms.txt"
    generator._write_sitemap(index, [artifact])

    assert (
        "- [Plain Title](guide/page.html.md): Plain description.\n"
        in index.read_text(encoding="utf-8")
    )


def test_custom_override_content_is_not_serialized(tmp_path: Path) -> None:
    """Arbitrary authored Markdown remains byte-for-byte user-owned."""
    generator = _generator(tmp_path)
    generator.app.config.llms_txt_override_source = "index"
    source = tmp_path / "custom.md"
    authored = (
        "# User [owned] &copy;\n\n"
        "- [Raw \\] label](a b(1).md): line with *markup*\\\n"
        "  continuation\n"
    )
    source.write_text(authored, encoding="utf-8")
    generator._markdown_file_by_docname = {"index": source}

    generator.build_custom_llms_txt()

    assert (tmp_path / "llms.txt").read_text(encoding="utf-8") == authored
