# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Markdown builder that preserves Sphinx document targets."""

import json
from pathlib import Path
from typing import Any, Optional, TypedDict
from uuid import uuid4

from docutils import nodes
from sphinx.transforms.post_transforms import SphinxPostTransform
from sphinx_markdown_builder.builder import MarkdownBuilder
from sphinx_markdown_builder.translator import MarkdownTranslator

LINK_TOKEN_PREFIX = "sphinx-llm:"
LINK_TARGETS_FILENAME = ".sphinx-llm-link-targets.json"


class LinkTarget(TypedDict):
    """Sphinx document target stored for an opaque link token."""

    docname: str
    fragment: Optional[str]


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


class MarkdownFriendlyNodesTransform(SphinxPostTransform):
    """Make documents more markdown-friendly before they get written.

    ``sphinx-markdown-builder`` drops the nodes it does not support (they only
    produce an "unknown node type" warning), which would result in content
    missing from the markdown output. Convert the affected node types into
    supported equivalents.
    """

    default_priority = 400
    formats = ("markdown",)

    def run(self, **kwargs: Any) -> None:
        # Generic admonitions and sidebars become a bold title followed by
        # their content.
        for node in [
            *self.document.findall(nodes.admonition),
            *self.document.findall(nodes.sidebar),
        ]:
            children = []
            for child in node.children:
                if isinstance(child, nodes.title):
                    para = nodes.paragraph()
                    para += nodes.strong(text=child.astext())
                    children.append(para)
                elif isinstance(child, nodes.raw):
                    continue
                else:
                    children.append(child)
            node.replace_self(children)

        # Map unsupported admonition flavors to supported ones with a similar
        # meaning.
        for node in list(self.document.findall(nodes.tip)):
            node.replace_self(nodes.hint("", *node.children))

        for node in list(self.document.findall(nodes.caution)):
            node.replace_self(nodes.attention("", *node.children))

        # Figure captions and legends are dropped by the markdown builder;
        # turn them into regular content.
        for node in list(self.document.findall(nodes.caption)):
            para = nodes.paragraph()
            para += nodes.emphasis(text=node.astext())
            node.replace_self(para)

        for node in list(self.document.findall(nodes.legend)):
            node.replace_self(node.children)

        # Abbreviations are inline elements: dropping them would remove words
        # from the middle of sentences. Keep their text.
        for node in list(self.document.findall(nodes.abbreviation)):
            node.replace_self(node.children)
