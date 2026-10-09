# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Markdown builder that preserves Sphinx document targets."""

import json
import re
import textwrap
from collections.abc import Sequence
from pathlib import Path
from typing import Optional, TypedDict
from uuid import uuid4

from docutils import nodes
from sphinx import addnodes
from sphinx.config import Config
from sphinx.errors import ConfigError
from sphinx_markdown_builder.builder import MarkdownBuilder
from sphinx_markdown_builder.translator import MarkdownTranslator

LINK_TOKEN_PREFIX = "sphinx-llm:"
LINK_TARGETS_FILENAME = ".sphinx-llm-link-targets.json"
SUPPRESS_UNKNOWN_NODE_WARNINGS_CONFIG = "llms_txt_suppress_unknown_node_warnings"
PRESERVE_UNKNOWN_NODES_CONFIG = "llms_txt_preserve_unknown_nodes"


class LinkTarget(TypedDict):
    """Sphinx document target stored for an opaque link token."""

    docname: str
    fragment: Optional[str]


def validate_suppress_unknown_node_warnings(_app, config: Config) -> None:
    """Validate and stabilize the unknown-node warning suppression setting."""
    value = getattr(config, SUPPRESS_UNKNOWN_NODE_WARNINGS_CONFIG)
    if isinstance(value, bool):
        return
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ConfigError(
            f"{SUPPRESS_UNKNOWN_NODE_WARNINGS_CONFIG} must be a bool or a "
            f"non-string sequence of node class names; got {value!r} "
            f"({type(value).__name__})"
        )

    for node_name in value:
        if not isinstance(node_name, str):
            raise ConfigError(
                f"{SUPPRESS_UNKNOWN_NODE_WARNINGS_CONFIG} entries must be "
                f"strings; got {node_name!r} ({type(node_name).__name__})"
            )
        if (
            not node_name
            or node_name != node_name.strip()
            or not node_name.isidentifier()
        ):
            raise ConfigError(
                f"{SUPPRESS_UNKNOWN_NODE_WARNINGS_CONFIG} entries must be "
                f"valid node class names without surrounding whitespace; "
                f"got {node_name!r}"
            )

    setattr(config, SUPPRESS_UNKNOWN_NODE_WARNINGS_CONFIG, tuple(value))


class SphinxLlmMarkdownTranslator(MarkdownTranslator):
    """Preserve document targets until sphinx-llm selects output paths."""

    def _adjust_url(self, url: str) -> str:
        if url.startswith(LINK_TOKEN_PREFIX):
            return url
        return super()._adjust_url(url)

    def _fetch_ref_uri(self, node: nodes.reference) -> str:
        if node.get("internal", self.status.default_ref_internal):
            ref_id = node.get("refid")
            if ref_id is not None:
                return self.builder.link_token(self.builder.current_doc_name, ref_id)
            if not node.get("refuri", ""):
                return self.builder.link_token(self.builder.current_doc_name)
        return super()._fetch_ref_uri(node)

    def unknown_visit(self, node: nodes.Node) -> None:
        """Handle unknown nodes without changing the default omission behavior."""
        suppressed = getattr(self.config, SUPPRESS_UNKNOWN_NODE_WARNINGS_CONFIG)
        node_name = node.__class__.__name__
        preserve = getattr(self.config, PRESERVE_UNKNOWN_NODES_CONFIG)
        warning_suppressed = suppressed is True or (
            suppressed is not False and node_name in suppressed
        )

        if preserve:
            if not warning_suppressed:
                try:
                    super().unknown_visit(node)
                except nodes.SkipNode:
                    pass
            self._add_unknown_node_source(node)
            raise nodes.SkipNode

        if warning_suppressed:
            raise nodes.SkipNode
        super().unknown_visit(node)

    def visit_desc_signature(self, node: nodes.Node) -> None:
        """Keep anonymous Breathe entities without emitting an empty heading."""
        if not node.astext().strip():
            if self.config.markdown_anchor_signatures:
                for anchor in node.get("ids", []):
                    self._add_anchor(anchor)
            for target in node.findall(nodes.target):
                self.visit_target(target)
            raise nodes.SkipNode
        super().visit_desc_signature(node)

    def depart_desc_signature(self, node: nodes.Node) -> None:
        self._pop_context(node)

    def _unknown_node_source(self, node: nodes.Node) -> str:
        """Return node source with any parsed-only descendants restored."""
        rawsource = getattr(node, "rawsource", "")
        source = rawsource or node.astext()

        if isinstance(node, addnodes.centered):
            return f".. centered:: {source}"

        if rawsource and not isinstance(node, nodes.Inline):
            missing_child_sources = []
            directive_match = re.match(
                r"^(?P<indent>[ \t]*)\.\. [^\n]+::[^\n]*(?:\n|$)", source
            )
            preserved_body = (
                textwrap.dedent(source[directive_match.end() :])
                if directive_match
                else source
            )
            for child in node.children:
                child_source = self._unknown_node_source(child).strip()
                if child_source and child_source in preserved_body:
                    preserved_body = preserved_body.replace(child_source, "", 1)
                elif child_source:
                    if directive_match:
                        content_indent = f"{directive_match.group('indent')}   "
                        child_source = textwrap.indent(child_source, content_indent)
                    missing_child_sources.append(child_source)
            if missing_child_sources:
                source = "\n\n".join([source.rstrip(), *missing_child_sources])
        return source

    def _add_unknown_node_source(self, node: nodes.Node) -> None:
        source = self._unknown_node_source(node)

        backtick_runs = re.findall(r"`+", source)
        fence = "`" * (max((len(run) for run in backtick_runs), default=0) + 1)

        if isinstance(node, nodes.Inline):
            padding = " " if source.startswith("`") or source.endswith("`") else ""
            self.add(f"{fence}{padding}{source}{padding}{fence}")
            return

        fence = "`" * max(3, len(fence))
        self.add(f"{fence}rst", prefix_eol=1, suffix_eol=1)
        self.add(source)
        self.add(fence, prefix_eol=1, suffix_eol=2)


class SphinxLlmMarkdownBuilder(MarkdownBuilder):
    """Write Markdown with links that retain Sphinx document names."""

    name = "llms-markdown"
    default_translator_class = SphinxLlmMarkdownTranslator

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._link_target_by_token: dict[str, LinkTarget] = {}
        self._link_token_by_target: dict[tuple[str, Optional[str]], str] = {}

    def link_token(self, docname: str, fragment: Optional[str] = None) -> str:
        """Return an opaque token for a Sphinx document target."""
        target = (docname, fragment)
        token = self._link_token_by_target.get(target)
        if token is None:
            token = f"{LINK_TOKEN_PREFIX}{uuid4().hex}"
            self._link_token_by_target[target] = token
            self._link_target_by_token[token] = {
                "docname": docname,
                "fragment": fragment,
            }
        return token

    def get_target_uri(self, docname: str, typ: Optional[str] = None) -> str:
        return self.link_token(docname)

    def get_relative_uri(self, from_: str, to: str, typ: Optional[str] = None) -> str:
        return self.link_token(to)

    def finish(self):
        super().finish()
        targets_path = Path(self.outdir) / LINK_TARGETS_FILENAME
        targets_path.write_text(
            json.dumps(self._link_target_by_token, sort_keys=True),
            encoding="utf-8",
        )
