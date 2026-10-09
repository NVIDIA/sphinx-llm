# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Custom unknown node extension used by integration tests."""

import sys

from docutils import nodes
from docutils.parsers.rst import Directive, directives, roles


class custom_unknown(nodes.Inline, nodes.TextElement):
    pass


class custom_admonition(nodes.Admonition, nodes.Element):
    pass


class CustomAdmonitionDirective(Directive):
    has_content = True

    def run(self):
        node = custom_admonition(".. custom-admonition::")
        self.state.nested_parse(self.content, self.content_offset, node)
        return [node]


class CompleteRawsourceAdmonitionDirective(Directive):
    has_content = True

    def run(self):
        node = custom_admonition(self.block_text)
        self.state.nested_parse(self.content, self.content_offset, node)
        return [node]


class HeaderMatchingAdmonitionDirective(Directive):
    has_content = True
    required_arguments = 1
    final_argument_whitespace = True

    def run(self):
        node = custom_admonition(f".. header-matching-admonition:: {self.arguments[0]}")
        self.state.nested_parse(self.content, self.content_offset, node)
        return [node]


def custom_unknown_role(
    name, rawtext, text, lineno, inliner, options=None, content=None
):
    return [custom_unknown(rawtext, text)], []


def passthrough(translator, node):
    pass


def setup(app):
    app.add_node(custom_unknown, html=(passthrough, passthrough))
    app.add_node(custom_admonition, html=(passthrough, passthrough))
    app.add_config_value("custom_fail_markdown", False, "env")
    app.add_config_value("custom_invalid_log_bytes", False, "env")
    roles.register_local_role("custom-unknown", custom_unknown_role)
    directives.register_directive("custom-admonition", CustomAdmonitionDirective)
    directives.register_directive(
        "complete-rawsource-admonition", CompleteRawsourceAdmonitionDirective
    )
    directives.register_directive(
        "header-matching-admonition", HeaderMatchingAdmonitionDirective
    )
    app.connect(
        "builder-inited",
        lambda app: (
            (sys.stdout.buffer.write(b"\xff\n"), sys.stdout.flush())
            if app.builder.name == "llms-markdown"
            and app.config.custom_invalid_log_bytes
            else None
        ),
    )
    app.connect(
        "build-finished",
        lambda app, exception: (
            (_ for _ in ()).throw(RuntimeError("child failed"))
            if app.builder.name == "llms-markdown" and app.config.custom_fail_markdown
            else None
        ),
    )
