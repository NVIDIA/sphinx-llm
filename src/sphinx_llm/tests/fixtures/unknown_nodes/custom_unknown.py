# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Custom unknown node extension used by integration tests."""

import sys

from docutils import nodes
from docutils.parsers.rst import roles


class custom_unknown(nodes.Inline, nodes.TextElement):
    pass


def custom_unknown_role(
    name, rawtext, text, lineno, inliner, options=None, content=None
):
    return [custom_unknown(rawtext, text)], []


def passthrough(translator, node):
    pass


def setup(app):
    app.add_node(custom_unknown, html=(passthrough, passthrough))
    app.add_config_value("custom_fail_markdown", False, "env")
    app.add_config_value("custom_invalid_log_bytes", False, "env")
    roles.register_local_role("custom-unknown", custom_unknown_role)
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
