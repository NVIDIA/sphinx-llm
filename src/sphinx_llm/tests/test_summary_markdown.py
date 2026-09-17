# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for Markdown sanitization in generated summaries."""

import pytest

from sphinx_llm.summary_markdown import strip_summary_markup


@pytest.mark.parametrize(
    ("markdown", "expected"),
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
        (
            "> [api]: python_api.html.md#callback-api\n> Read [Callback API][api].",
            "> Read Callback API.",
        ),
        (
            "Read [the `]` API](python_api.html.md#callback-api).",
            "Read the `]` API.",
        ),
        (
            '> [outer ![diagram](image.png "First\n  > second")](callbacks.md)',
            "> outer diagram",
        ),
        (
            '> > [Callback API](python_api.html.md "First\n> second")',
            "> > Callback API",
        ),
        (
            "[Callback API][api]\n\n[api]: first.md\n[api]: second.md",
            "Callback API",
        ),
        (
            "See [the **API** and ![diagram](diagram.png)](guide_(v2).md) or "
            '[examples](examples.md "Examples ) here").',
            "See the **API** and diagram or examples.",
        ),
        (
            "See [![diagram][img]](callbacks.md).\n\n[img]: callback.png",
            "See diagram.",
        ),
    ],
)
def test_strip_summary_markup_preserves_readable_link_text(
    markdown: str, expected: str
) -> None:
    """Parser-recognized links and images retain only readable source text."""
    assert strip_summary_markup(markdown) == expected


@pytest.mark.parametrize(
    "markdown",
    [
        "A useful summary without links.",
        "A [bracketed] note with an unresolved [reference][missing].",
        r"Escaped \[label](destination.md) and `[code](destination.md)`.",
        "Not links: [label](two words) or [label](<two<words>).",
        "Plain text: [literal](not-a-link\\ space).",
        "```\n[api]: callbacks.md\n```\nUnresolved [Callback API][api].",
        "Unsafe URI <javascript:alert(1)> and invalid <a@b_c.example>.",
        "Unused definition.\n\n[api]: callbacks.md",
        '[literal](not-a-link.md\n\n "title")',
        "    [literal](not-a-link.md)",
        '> [literal](not-a-link.md "first\n- > second")',
        '> [literal](not-a-link.md "first\n1. > second")',
        '> [literal](not-a-link.md "first\n+ > second")',
        "#### NOTES\n\nAn ordinary plural heading.",
        "### NOTE\n\nAn ordinary level-three heading.",
    ],
)
def test_strip_summary_markup_preserves_unrecognized_source(markdown: str) -> None:
    """Link-free and admonition-lookalike source remains byte-for-byte intact."""
    assert strip_summary_markup(markdown) == markdown


@pytest.mark.parametrize(
    ("markdown", "expected"),
    [
        ("#### NOTE\n\nUseful note prose.", "Useful note prose."),
        (
            "#### WARNING\r\n\r\nRead [the warning](warning.md).\r\n",
            "Read the warning.\r\n",
        ),
        (
            "Before.\n\n#### SEE ALSO\n\nRelated prose.\n\nAfter.",
            "Before.\n\nRelated prose.\n\nAfter.",
        ),
    ],
)
def test_strip_summary_markup_removes_generated_admonition_markers(
    markdown: str, expected: str
) -> None:
    """Sphinx Markdown builder admonition headings do not enter summaries."""
    result = strip_summary_markup(markdown)
    assert result == expected
    assert strip_summary_markup(result) == result


@pytest.mark.parametrize(
    "title", ["ATTENTION", "HINT", "IMPORTANT", "NOTE", "SEE ALSO", "WARNING"]
)
def test_strip_summary_markup_supports_builder_admonition_titles(title: str) -> None:
    """Every admonition heading emitted by the builder has an explicit contract."""
    assert strip_summary_markup(f"#### {title}\n\nUseful prose.") == "Useful prose."


def test_strip_summary_markup_is_idempotent_for_nested_markup() -> None:
    """Repeated sanitization produces the same readable summary."""
    markdown = "#### IMPORTANT\n\nSee [![diagram](image.png)](guide.md)."
    result = strip_summary_markup(markdown)
    assert result == "See diagram."
    assert strip_summary_markup(result) == result
