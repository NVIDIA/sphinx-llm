# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Markdown builder that preserves Sphinx document targets."""

from typing import Optional
from urllib.parse import quote

from docutils import nodes
from sphinx_markdown_builder.builder import MarkdownBuilder
from sphinx_markdown_builder.translator import MarkdownTranslator

LINK_TOKEN_PREFIX = "sphinx-llm:"


def link_token(docname: str, fragment: Optional[str] = None) -> str:
    """Return a link token for a Sphinx document target."""
    token = f"{LINK_TOKEN_PREFIX}{quote(docname, safe='/')}"
    if fragment:
        token = f"{token}#{quote(fragment, safe='')}"
    return token


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
                return link_token(self.builder.current_doc_name, ref_id)
            if not node.get("refuri", ""):
                return link_token(self.builder.current_doc_name)
        return super()._fetch_ref_uri(node)


class SphinxLlmMarkdownBuilder(MarkdownBuilder):
    """Write Markdown with links that retain Sphinx document names."""

    name = "llms-markdown"
    default_translator_class = SphinxLlmMarkdownTranslator

    def get_target_uri(self, docname: str, typ: Optional[str] = None) -> str:
        return link_token(docname)

    def get_relative_uri(self, from_: str, to: str, typ: Optional[str] = None) -> str:
        return link_token(to)
