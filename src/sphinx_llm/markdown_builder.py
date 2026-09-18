# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Markdown builder that preserves Sphinx document targets."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Optional, TypedDict
from uuid import uuid4

from docutils import nodes
from sphinx.config import Config
from sphinx.errors import ConfigError
from sphinx_markdown_builder.builder import MarkdownBuilder
from sphinx_markdown_builder.translator import MarkdownTranslator

LINK_TOKEN_PREFIX = "sphinx-llm:"
LINK_TARGETS_FILENAME = ".sphinx-llm-link-targets.json"
SUPPRESS_UNKNOWN_NODE_WARNINGS_CONFIG = "llms_txt_suppress_unknown_node_warnings"


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
        """Optionally suppress the warning while still dropping the subtree."""
        suppressed = getattr(self.config, SUPPRESS_UNKNOWN_NODE_WARNINGS_CONFIG)
        node_name = node.__class__.__name__
        if suppressed is True or (suppressed is not False and node_name in suppressed):
            raise nodes.SkipNode
        super().unknown_visit(node)


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
