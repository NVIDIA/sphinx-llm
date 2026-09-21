# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Integration evidence for the issue #159 shared-doctree proof of concept."""

from __future__ import annotations

import json
import os
import pickle
import shutil
import sys
from pathlib import Path

import pytest
from sphinx.application import Sphinx

FIXTURE = Path(__file__).parent / "fixtures" / "shared_doctree"


def _build(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    builder: str = "html",
    parallel: int = 1,
    experimental: bool,
) -> tuple[Sphinx, Path, Path]:
    source = root / "source"
    output = root / "output"
    probe = root / "probe"
    shutil.copytree(FIXTURE, source)
    if not experimental:
        conf = source / "conf.py"
        conf.write_text(
            conf.read_text(encoding="utf-8").replace(
                "llms_txt_experimental_shared_doctrees = True",
                "llms_txt_experimental_shared_doctrees = False",
            ),
            encoding="utf-8",
        )
    app = _run_build(
        source,
        output,
        probe,
        monkeypatch,
        builder=builder,
        parallel=parallel,
        freshenv=True,
        experimental=experimental,
    )
    return app, output, probe


def _run_build(
    source: Path,
    output: Path,
    probe: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    builder: str = "html",
    parallel: int = 1,
    freshenv: bool,
    experimental: bool = True,
) -> Sphinx:
    monkeypatch.setenv("SPHINX_LLM_POC_PROBE_DIR", str(probe))
    monkeypatch.setenv("SPHINX_LLM_POC_WRITER_BARRIER", "1" if experimental else "")
    monkeypatch.setenv("SPHINX_LLM_POC_MUTATION_PROBE", "1" if experimental else "")
    for marker in ("primary.started", "markdown.started", "markdown.mutated"):
        (probe / marker).unlink(missing_ok=True)
    sys.path.insert(0, str(source))
    try:
        app = Sphinx(
            srcdir=source,
            confdir=source,
            outdir=output,
            doctreedir=output.parent / "doctrees",
            buildername=builder,
            freshenv=freshenv,
            parallel=parallel,
            tags=["html"],
        )
        app.build()
    finally:
        sys.path.remove(str(source))
    return app


def _events(probe: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (probe / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def test_control_build_evaluates_sources_twice(tmp_path, monkeypatch):
    _, _, probe = _build(tmp_path, monkeypatch, experimental=False)

    evaluations = (probe / "evaluations.txt").read_text(encoding="utf-8").splitlines()
    source_reads = [
        event for event in _events(probe) if event["event"] == "source-read"
    ]
    assert len(evaluations) == 4
    assert len(source_reads) == 4


@pytest.mark.parametrize("builder", ["html", "dirhtml"])
@pytest.mark.parametrize("parallel", [1, 2], ids=["serial-read", "parallel-read"])
def test_shared_doctree_build_evaluates_once_and_overlaps_writers(
    tmp_path, monkeypatch, builder, parallel
):
    app, output, probe = _build(
        tmp_path,
        monkeypatch,
        builder=builder,
        parallel=parallel,
        experimental=True,
    )

    evaluations = (probe / "evaluations.txt").read_text(encoding="utf-8").splitlines()
    assert len(evaluations) == 2
    assert {value.split(":")[1] for value in evaluations} == {"index", "guide"}

    events = _events(probe)
    source_reads = [event for event in events if event["event"] == "source-read"]
    assert len(source_reads) == 2
    assert {event["docname"] for event in source_reads} == {"index", "guide"}
    assert len({event["pid"] for event in source_reads}) == parallel
    assert {
        event["role"] for event in events if event["event"] == "writer-overlap"
    } == {
        "primary",
        "markdown",
    }
    assert [event["event"] for event in events].index("env-updated") < [
        event["event"] for event in events
    ].index("snapshot-ready")
    assert next(event for event in events if event["event"] == "snapshot-ready")[
        "docnames"
    ] == ["guide", "index"]
    for role in ("primary", "markdown"):
        start = next(
            index
            for index, event in enumerate(events)
            if event["event"] == "writer-start" and event["role"] == role
        )
        overlap = next(
            index
            for index, event in enumerate(events)
            if event["event"] == "writer-overlap" and event["role"] == role
        )
        finish = next(
            index
            for index, event in enumerate(events)
            if event["event"] == "writer-finished" and event["role"] == role
        )
        assert start < overlap < finish

    if builder == "html":
        html_paths = {"index": output / "index.html", "guide": output / "guide.html"}
        markdown_paths = {
            "index": output / "index.html.md",
            "guide": output / "guide.html.md",
        }
    else:
        html_paths = {
            "index": output / "index.html",
            "guide": output / "guide" / "index.html",
        }
        markdown_paths = {
            "index": output / "index.html.md",
            "guide": output / "guide" / "index.html.md",
        }

    for docname in ("index", "guide"):
        value = next(value for value in evaluations if f":{docname}:" in value)
        html = html_paths[docname].read_text(encoding="utf-8")
        markdown = markdown_paths[docname].read_text(encoding="utf-8")
        assert value in html
        assert value in markdown
        assert "primary-only-mutation" in html
        assert "markdown-only-mutation" not in html
        assert "markdown-only-mutation" in markdown
        assert "primary-only-mutation" not in markdown

    index_markdown = markdown_paths["index"].read_text(encoding="utf-8")
    assert "HTML-tag-conditioned content." in index_markdown
    assert "[The guide]" in index_markdown
    assert "Root page from the shared doctree fixture." in (
        output / "llms.txt"
    ).read_text(encoding="utf-8")
    assert "Guide body from the shared doctree fixture." in (
        output / "llms-full.txt"
    ).read_text(encoding="utf-8")
    assert app.statuscode == 0


def test_shared_doctree_clean_build_is_repeatable(tmp_path, monkeypatch):
    outputs = []
    for run in ("first", "second"):
        _, output, _ = _build(tmp_path / run, monkeypatch, experimental=True)
        outputs.append(
            {
                path.relative_to(output): path.read_text(encoding="utf-8")
                for path in output.rglob("*.md")
            }
            | {
                Path(name): (output / name).read_text(encoding="utf-8")
                for name in ("llms.txt", "llms-full.txt")
            }
        )
    assert outputs[0] == outputs[1]


def test_shared_doctree_incremental_builds(tmp_path, monkeypatch):
    source = tmp_path / "source"
    output = tmp_path / "output"
    probe = tmp_path / "probe"
    shutil.copytree(FIXTURE, source)

    _run_build(source, output, probe, monkeypatch, freshenv=True)
    assert len((probe / "evaluations.txt").read_text().splitlines()) == 2

    _run_build(source, output, probe, monkeypatch, freshenv=False)
    assert len((probe / "evaluations.txt").read_text().splitlines()) == 2

    with (source / "guide.rst").open("a", encoding="utf-8") as stream:
        stream.write("\nChanged content marker.\n")
    _run_build(source, output, probe, monkeypatch, freshenv=False)

    evaluations = (probe / "evaluations.txt").read_text().splitlines()
    assert len(evaluations) == 3
    assert evaluations[-1].startswith("evaluation:guide:")
    assert "Changed content marker." in (output / "guide.html").read_text()
    assert "Changed content marker." in (output / "guide.html.md").read_text()
    assert "evaluation:index:" in (output / "index.html.md").read_text()
    assert (
        len([event for event in _events(probe) if event["event"] == "source-read"]) == 3
    )


def test_read_failure_never_starts_secondary_writer(tmp_path, monkeypatch):
    monkeypatch.setenv("SPHINX_LLM_POC_FAIL_READ_DOC", "guide")
    with pytest.raises(Exception, match="intentional read failure"):
        _build(tmp_path, monkeypatch, experimental=True)
    assert not (tmp_path / "probe" / "markdown.started").exists()


def test_corrupt_doctree_fails_without_reread_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("SPHINX_LLM_POC_CORRUPT_DOCTREE", "guide")
    with pytest.raises(pickle.UnpicklingError):
        _build(tmp_path, monkeypatch, experimental=True)
    probe = tmp_path / "probe"
    assert not (probe / "markdown.started").exists()
    assert (
        len([event for event in _events(probe) if event["event"] == "source-read"]) == 2
    )


def test_secondary_failure_sets_nonzero_status_and_removes_staging(
    tmp_path, monkeypatch
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    probe = tmp_path / "probe"
    shutil.copytree(FIXTURE, source)
    _run_build(source, output, probe, monkeypatch, freshenv=True)
    assert (output / "index.html.md").exists()

    monkeypatch.setenv("SPHINX_LLM_POC_FAIL_WRITER", "markdown")
    app = _run_build(source, output, probe, monkeypatch, freshenv=False)
    assert app.statuscode != 0
    assert not (output / "_markdown_build").exists()
    assert not (output / "index.html.md").exists()
    assert not (output / "llms.txt").exists()


def test_primary_failure_terminates_secondary_writer(tmp_path, monkeypatch):
    monkeypatch.setenv("SPHINX_LLM_POC_FAIL_WRITER", "primary")
    monkeypatch.setenv("SPHINX_LLM_POC_HANG_MARKDOWN", "1")
    with pytest.raises(Exception, match="intentional primary writer failure"):
        _build(tmp_path, monkeypatch, experimental=True)

    probe = tmp_path / "probe"
    markdown_start = next(
        event
        for event in _events(probe)
        if event["event"] == "writer-start" and event["role"] == "markdown"
    )
    with pytest.raises(ProcessLookupError):
        os.kill(markdown_start["pid"], 0)
    assert not (tmp_path / "output" / "_markdown_build").exists()
