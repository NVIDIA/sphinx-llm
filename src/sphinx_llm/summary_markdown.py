# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Sanitize Markdown for use in short generated summaries."""

from __future__ import annotations

from typing import Any

from markdown_it import MarkdownIt
from markdown_it.common.utils import normalizeReference
from markdown_it.rules_inline import (
    autolink as markdown_autolink_rule,
)
from markdown_it.rules_inline import (
    image as markdown_image_rule,
)
from markdown_it.rules_inline import (
    link as markdown_link_rule,
)
from markdown_it.rules_inline.state_inline import StateInline
from markdown_it.token import Token

_SUMMARY_SOURCE_KEY = "sphinx_llm_summary_source"
_SUMMARY_RANGES_KEY = "sphinx_llm_summary_ranges"
_SUMMARY_REFERENCES_KEY = "sphinx_llm_summary_references"
_ADMONITION_TITLES = frozenset(
    {
        "ATTENTION",
        "HINT",
        "IMPORTANT",
        "NOTE",
        "SEE ALSO",
        "WARNING",
    }
)


def _record_reference_label(
    state: StateInline, label_start: int, label_end: int, end: int
) -> None:
    """Record a reference label when the parser consumed reference syntax."""
    suffix_start = label_end + 1
    label = None
    if end == suffix_start:
        label = state.src[label_start:label_end]
    elif suffix_start < len(state.src) and state.src[suffix_start] == "[":
        reference_end = state.md.helpers.parseLinkLabel(state, suffix_start)
        if reference_end >= 0 and end == reference_end + 1:
            label = state.src[suffix_start + 1 : reference_end]
            if not label:
                label = state.src[label_start:label_end]
    if label is not None:
        state.env[_SUMMARY_REFERENCES_KEY].add(normalizeReference(label))


def _record_link(
    state: StateInline, start: int, label_start: int, label_end: int
) -> None:
    """Record source ranges removed from one parser-recognized link or image."""
    if state.src is not state.env.get(_SUMMARY_SOURCE_KEY):
        return
    state.env[_SUMMARY_RANGES_KEY].extend(
        ((start, label_start), (label_end, state.pos))
    )
    _record_reference_label(state, label_start, label_end, state.pos)


def _tracked_markdown_link(state: StateInline, silent: bool) -> bool:
    """Run MarkdownIt's link rule while capturing its exact source range."""
    start = state.pos
    label_end = state.md.helpers.parseLinkLabel(state, start, True)
    result = markdown_link_rule(state, silent)
    if result and not silent and label_end >= 0:
        _record_link(state, start, start + 1, label_end)
    return result


def _tracked_markdown_image(state: StateInline, silent: bool) -> bool:
    """Run MarkdownIt's image rule while capturing its exact source range."""
    start = state.pos
    label_end = state.md.helpers.parseLinkLabel(state, start + 1, False)
    result = markdown_image_rule(state, silent)
    if result and not silent and label_end >= 0:
        _record_link(state, start, start + 2, label_end)
    return result


def _tracked_markdown_autolink(state: StateInline, silent: bool) -> bool:
    """Run MarkdownIt's autolink rule while capturing its angle brackets."""
    start = state.pos
    result = markdown_autolink_rule(state, silent)
    if result and not silent and state.src is state.env.get(_SUMMARY_SOURCE_KEY):
        state.env[_SUMMARY_RANGES_KEY].extend(
            ((start, start + 1), (state.pos - 1, state.pos))
        )
    return result


_MARKDOWN_PARSER = MarkdownIt("commonmark")
_MARKDOWN_PARSER.inline.ruler.at("link", _tracked_markdown_link)
_MARKDOWN_PARSER.inline.ruler.at("image", _tracked_markdown_image)
_MARKDOWN_PARSER.inline.ruler.at("autolink", _tracked_markdown_autolink)


def _markdown_context(
    value: str,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, list[tuple[int, int]]],
    list[Token],
    list[int],
]:
    """Return parser references, definitions, tokens, and line offsets."""
    environment: dict[str, Any] = {}
    tokens = _MARKDOWN_PARSER.parse(value, environment)
    references = environment.get("references", {})
    offsets = [0]
    for line in value.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))

    definitions = {
        label: [(offsets[record["map"][0]], offsets[record["map"][1]])]
        for label, record in references.items()
    }
    for duplicate in environment.get("duplicate_refs", []):
        definitions.setdefault(duplicate["label"], []).append(
            (offsets[duplicate["map"][0]], offsets[duplicate["map"][1]])
        )
    return references, definitions, tokens, offsets


def _inline_link_ranges(
    value: str, references: dict[str, dict[str, Any]]
) -> tuple[list[tuple[int, int]], set[str]]:
    """Return link markup ranges reported by MarkdownIt's inline rules."""
    ranges: list[tuple[int, int]] = []
    used_references: set[str] = set()
    environment = {
        "references": references,
        _SUMMARY_SOURCE_KEY: value,
        _SUMMARY_RANGES_KEY: ranges,
        _SUMMARY_REFERENCES_KEY: used_references,
    }
    _MARKDOWN_PARSER.inline.parse(value, _MARKDOWN_PARSER, environment, [])
    return ranges, used_references


def _inline_source_positions(
    value: str, token: Token, offsets: list[int]
) -> list[int] | None:
    """Map normalized inline content characters back to original source offsets."""
    if token.map is None:
        return None
    source_lines = value.splitlines(keepends=True)
    source_line = token.map[0]
    positions = []
    for content_line in token.content.splitlines(keepends=True):
        has_newline = content_line.endswith("\n")
        content = content_line[:-1] if has_newline else content_line
        matched = False
        while source_line < token.map[1]:
            source = source_lines[source_line]
            source_content = source.rstrip("\r\n")
            column = source_content.rfind(content)
            if column >= 0:
                positions.extend(
                    offsets[source_line] + column + i for i in range(len(content))
                )
                if has_newline:
                    positions.append(offsets[source_line] + len(source) - 1)
                source_line += 1
                matched = True
                break
            source_line += 1
        if not matched:
            return None
    return positions


def _admonition_ranges(
    value: str, tokens: list[Token], offsets: list[int]
) -> list[tuple[int, int]]:
    """Return ranges for admonition headings emitted by the Markdown builder."""
    ranges = []
    for index, token in enumerate(tokens[:-1]):
        if (
            token.type != "heading_open"
            or token.tag != "h4"
            or token.map is None
            or tokens[index + 1].type != "inline"
            or tokens[index + 1].content not in _ADMONITION_TITLES
        ):
            continue
        end = offsets[token.map[1]]
        while end < len(value) and value[end] in "\r\n":
            end += 1
        ranges.append((offsets[token.map[0]], end))
    return ranges


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping source deletion ranges."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def strip_summary_markup(markdown: str) -> str:
    """Remove summary-inappropriate Markdown while preserving readable prose.

    Link and image destinations are removed using CommonMark parser ranges,
    while link labels and image alt text remain. Admonition headings emitted by
    ``sphinx-markdown-builder`` are removed without discarding their content.
    Unrecognized and unrelated Markdown is left byte-for-byte unchanged.
    """
    references, definitions, tokens, offsets = _markdown_context(markdown)
    deletions = _admonition_ranges(markdown, tokens, offsets)
    used_reference_labels: set[str] = set()
    for token in tokens:
        if token.type != "inline":
            continue
        inline_ranges, inline_references = _inline_link_ranges(
            token.content, references
        )
        positions = _inline_source_positions(markdown, token, offsets)
        if positions is None:
            continue
        for start, end in inline_ranges:
            deletions.append((positions[start], positions[end - 1] + 1))
        used_reference_labels.update(inline_references)

    for label in used_reference_labels:
        deletions.extend(definitions.get(label, []))
    if not deletions:
        return markdown

    pieces = []
    start = 0
    for deletion_start, deletion_end in _merge_ranges(deletions):
        pieces.append(markdown[start:deletion_start])
        start = deletion_end
    pieces.append(markdown[start:])
    result = "".join(pieces)
    if used_reference_labels:
        result = result.rstrip("\r\n")
    return result
