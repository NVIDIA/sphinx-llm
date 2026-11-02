# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Plain inspection helpers shared by test modules."""

from sphinx.application import Sphinx

HTML_META_PAGE = "meta_example"


def get_html_meta_description(app: Sphinx, docname: str) -> str:
    """Extract the html_meta description from a page's pickled doctree.

    This is the ground truth for what the extension should write into llms.txt.
    Reading it from the doctree (rather than hardcoding it) keeps the tests
    valid when the source document is edited.
    """
    doctree = app.env.get_doctree(docname)
    for node in doctree.traverse(lambda node: node.tagname == "meta"):
        if node.get("name") == "description" and node.get("content"):
            return node["content"]
    raise AssertionError(
        f"No html_meta description found in doctree for '{docname}'. "
        f"Does the source file define '.. meta:: :description:'?"
    )
