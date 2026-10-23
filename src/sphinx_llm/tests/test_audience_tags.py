# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Audience selection uses Sphinx's native only-expression evaluation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Expected audiences: HTML, Sphinx LLM Markdown, standalone Markdown, other.
CONDITIONS = [
    ("human", "HumanAudienceMarker", {"html", "markdown", "other"}),
    ("agent", "AgentAudienceMarker", {"agent"}),
    ("html", "NativeHtmlMarker", {"html"}),
    ("markdown", "NativeMarkdownMarker", {"agent", "markdown"}),
    ("format_html", "HtmlFormatMarker", {"html"}),
    ("format_markdown", "MarkdownFormatMarker", {"agent", "markdown"}),
    ("not human", "NotHumanMarker", {"agent"}),
    ("not agent", "NotAgentMarker", {"html", "markdown", "other"}),
    ("human and html", "HumanHtmlMarker", {"html"}),
    ("agent and markdown", "AgentMarkdownMarker", {"agent"}),
    ("markdown and not agent", "StandaloneMarkdownMarker", {"markdown"}),
    ("human or agent", "EitherAudienceMarker", {"html", "agent", "markdown", "other"}),
    ("human and agent", "BothAudiencesMarker", set()),
    (
        "(human or agent) and custom_tag",
        "CustomAudienceMarker",
        {"html", "agent", "markdown", "other"},
    ),
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
    """Check native tags, audience expressions, and nesting in rendered output."""
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
        ("man", ["custom_tag"], "other"),
    ],
)
@pytest.mark.parametrize(
    "explicit_tags", [(), ("human",), ("agent",), ("human", "agent")]
)
@pytest.mark.parametrize("tag_source", ["cli", "conf"])
@pytest.mark.parametrize("evaluate_in_conf", [False, True])
def test_standalone_builds_select_only_their_own_audience(
    make_sphinx_project,
    make_sphinx_app,
    builder,
    tags,
    audience,
    explicit_tags,
    tag_source,
    evaluate_in_conf,
) -> None:
    """Only the dedicated LLM builder automatically selects agent content."""
    config = 'extensions = ["sphinx_markdown_builder", "sphinx_llm.txt"]\n'
    if tag_source == "conf":
        config += "".join(
            f"tags.add({tag!r})\n" for tag in (*explicit_tags, "custom_tag")
        )
    if evaluate_in_conf:
        # Cache complete expressions before builder initialization; clearing only
        # the bare audience names would leave compound expressions stale.
        conditions = [condition for condition, _, _ in CONDITIONS]
        config += (
            f"for condition in {conditions!r}:\n    tags.eval_condition(condition)\n"
        )
    source = make_sphinx_project(
        config=config,
        documents={"index.rst": SOURCE},
    )
    app = make_sphinx_app(
        srcdir=source,
        buildername=builder,
        tags=[*tags, *explicit_tags] if tag_source == "cli" else tags,
    )
    app.build()
    assert app.statuscode == 0, app._warning.getvalue()
    if builder == "man":
        content = next(Path(app.outdir).glob("*.1")).read_text()
    else:
        suffix = ".txt" if builder == "text" else ".md"
        content = (Path(app.outdir) / f"index{suffix}").read_text()
    _assert_audience(content, audience, builder)


@pytest.mark.parametrize("builder", ["html", "dirhtml"])
def test_human_tag_does_not_depend_on_artifact_generation(
    make_sphinx_project, build_sphinx_app, builder
) -> None:
    """Disabling generated artifacts leaves HTML audience selection available."""
    source = make_sphinx_project(
        config='extensions = ["sphinx_llm.txt"]\nllms_txt_enabled = False\n',
        documents={"index.rst": SOURCE},
    )
    _, output, _ = build_sphinx_app(source, builder=builder)
    assert "HumanAudienceMarker" in (output / "index.html").read_text()
    assert "AgentAudienceMarker" not in (output / "index.html").read_text()
    assert not (output / "llms.txt").exists()


@pytest.mark.parametrize("builder", ["html", "dirhtml"])
@pytest.mark.parametrize("parallel", [False, True])
@pytest.mark.parametrize("tag_source", ["cli", "conf"])
@pytest.mark.parametrize("explicit_tags", [("human",), ("agent",), ("human", "agent")])
@pytest.mark.parametrize("evaluate_in_conf", [False, True])
def test_explicit_audience_tags_are_normalized(
    make_sphinx_project,
    builder: str,
    parallel: bool,
    tag_source: str,
    explicit_tags,
    evaluate_in_conf,
) -> None:
    """Explicit audience tags cannot contradict the actual output audience."""
    config = (
        'extensions = ["sphinx_llm.txt"]\n'
        f"llms_txt_build_parallel = {parallel!r}\n"
        "llms_txt_full_build = True\n"
        'llms_txt_override_source = "index"\n'
    )
    if tag_source == "conf":
        config += "".join(
            f"tags.add({tag!r})\n" for tag in (*explicit_tags, "custom_tag")
        )
    if evaluate_in_conf:
        config += (
            'for condition in ("human", "agent", "human and agent", "custom_tag"):\n'
            "    tags.eval_condition(condition)\n"
        )
    source = make_sphinx_project(
        config=config,
        documents={
            "index.rst": "Explicit audience\n=================\n\n"
            ".. only:: human\n\n   ExplicitHumanMarker\n\n"
            ".. only:: agent\n\n   ExplicitAgentMarker\n\n"
            ".. only:: human and agent\n\n   CombinedAudienceMarker\n\n"
            ".. only:: custom_tag\n\n   PreservedCustomMarker\n"
        },
    )
    output = source.parent / "build"
    command = [sys.executable, "-m", "sphinx", "-W", "-b", builder]
    if tag_source == "cli":
        for tag in (*explicit_tags, "custom_tag"):
            command += ["-t", tag]
    result = subprocess.run(
        [*command, str(source), str(output)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    html = (output / "index.html").read_text()
    assert "ExplicitHumanMarker" in html
    assert "ExplicitAgentMarker" not in html
    assert "CombinedAudienceMarker" not in html
    assert "PreservedCustomMarker" in html
    for name in ("index.html.md", "index.md", "llms-full.txt", "llms.txt"):
        markdown = (output / name).read_text()
        assert "ExplicitHumanMarker" not in markdown, (tag_source, name)
        assert "ExplicitAgentMarker" in markdown
        assert "CombinedAudienceMarker" not in markdown
        assert "PreservedCustomMarker" in markdown
