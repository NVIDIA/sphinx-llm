# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Audience selection uses Sphinx's native only-expression evaluation."""

from __future__ import annotations

from pathlib import Path

import pytest

# Expected audiences: HTML, Sphinx LLM Markdown, standalone Markdown, other.
CONDITIONS = [
    ("human", "HumanAudienceMarker", {"html"}),
    ("agent", "AgentAudienceMarker", {"agent"}),
    ("html", "NativeHtmlMarker", {"html"}),
    ("markdown", "NativeMarkdownMarker", {"agent", "markdown"}),
    ("format_html", "HtmlFormatMarker", {"html"}),
    ("format_markdown", "MarkdownFormatMarker", {"agent", "markdown"}),
    ("not human", "NotHumanMarker", {"agent", "markdown", "other"}),
    ("not agent", "NotAgentMarker", {"html", "markdown", "other"}),
    ("human and html", "HumanHtmlMarker", {"html"}),
    ("agent and markdown", "AgentMarkdownMarker", {"agent"}),
    ("markdown and not agent", "StandaloneMarkdownMarker", {"markdown"}),
    ("human or agent", "EitherAudienceMarker", {"html", "agent"}),
    ("human and agent", "BothAudiencesMarker", set()),
    ("(human or agent) and custom_tag", "CustomAudienceMarker", {"html", "agent"}),
    ("agent and missing_tag", "MissingCustomMarker", set()),
]
SOURCE = "Audience selection\n==================\n\n" + "\n".join(
    f".. only:: {expression}\n\n   {marker}\n" for expression, marker, _ in CONDITIONS
)
SOURCE += """
.. only:: markdown

   .. only:: agent

      NestedAgentMarker

.. only:: human

   .. only:: html

      NestedHumanMarker

.. only:: builder_html

   HtmlBuilderMarker

.. only:: builder_dirhtml

   DirhtmlBuilderMarker
"""


def _assert_audience(content: str, audience: str, builder: str) -> None:
    for expression, marker, audiences in CONDITIONS:
        assert (marker in content) == (audience in audiences), expression
    assert ("NestedAgentMarker" in content) == (audience == "agent")
    assert ("NestedHumanMarker" in content) == (audience == "html")
    assert ("HtmlBuilderMarker" in content) == (builder == "html")
    assert ("DirhtmlBuilderMarker" in content) == (builder == "dirhtml")


@pytest.mark.parametrize("builder", ["html", "dirhtml"])
@pytest.mark.parametrize("parallel", [False, True])
def test_generated_outputs_select_their_own_audience(
    make_sphinx_project, make_sphinx_app, builder: str, parallel: bool
) -> None:
    """The child must not inherit human, even when it reuses HTML doctrees."""
    source = make_sphinx_project(
        config='extensions = ["sphinx_llm.txt"]\n'
        f"llms_txt_build_parallel = {parallel!r}\n"
        "llms_txt_full_build = True\n"
        'llms_txt_override_source = "index"\n',
        documents={"index.rst": SOURCE},
    )
    app = make_sphinx_app(srcdir=source, buildername=builder, tags=["custom_tag"])
    app.build()
    assert app.statuscode == 0, app._warning.getvalue()
    output = Path(app.outdir)
    _assert_audience((output / "index.html").read_text(), "html", builder)
    for name in ("index.html.md", "index.md", "llms-full.txt", "llms.txt"):
        _assert_audience((output / name).read_text(), "agent", "llms-markdown")


@pytest.mark.parametrize(
    ("builder", "tags", "audience"),
    [
        ("markdown", ["custom_tag"], "markdown"),
        # The internal registration tag alone must not imply an agent audience.
        ("markdown", ["custom_tag", "sphinx_llm_markdown"], "markdown"),
        ("llms-markdown", ["custom_tag", "sphinx_llm_markdown"], "agent"),
        ("text", ["custom_tag"], "other"),
    ],
)
def test_standalone_builds_select_only_their_own_audience(
    make_sphinx_project, make_sphinx_app, builder, tags, audience
) -> None:
    source = make_sphinx_project(
        config='extensions = ["sphinx_markdown_builder", "sphinx_llm.txt"]\n',
        documents={"index.rst": SOURCE},
    )
    app = make_sphinx_app(srcdir=source, buildername=builder, tags=tags)
    app.build()
    assert app.statuscode == 0, app._warning.getvalue()
    suffix = ".txt" if builder == "text" else ".md"
    _assert_audience(
        (Path(app.outdir) / f"index{suffix}").read_text(), audience, builder
    )


@pytest.mark.parametrize("builder", ["html", "dirhtml"])
def test_human_tag_does_not_depend_on_artifact_generation(
    make_sphinx_project, build_sphinx_app, builder
) -> None:
    source = make_sphinx_project(
        config='extensions = ["sphinx_llm.txt"]\nllms_txt_enabled = False\n',
        documents={"index.rst": SOURCE},
    )
    _, output, _ = build_sphinx_app(source, builder=builder)
    assert "HumanAudienceMarker" in (output / "index.html").read_text()
    assert "AgentAudienceMarker" not in (output / "index.html").read_text()
    assert not (output / "llms.txt").exists()
