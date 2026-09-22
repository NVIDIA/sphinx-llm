# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Observable probes for the shared-doctree proof of concept."""

from __future__ import annotations

import fcntl
import json
import os
import time
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.errors import ExtensionError


def _probe_dir() -> Path:
    return Path(os.environ["SPHINX_LLM_POC_PROBE_DIR"])


def _append_event(event: dict[str, object]) -> None:
    path = _probe_dir() / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(json.dumps(event, sort_keys=True) + "\n")
        stream.flush()
        fcntl.flock(stream, fcntl.LOCK_UN)


class EvaluateOnceDirective(Directive):
    """Perform a durable, externally observable read-time evaluation."""

    has_content = False

    def run(self):
        env = self.state.document.settings.env
        if os.environ.get("SPHINX_LLM_POC_FAIL_READ_DOC") == env.docname:
            raise ExtensionError(f"intentional read failure in {env.docname}")
        counter = _probe_dir() / "evaluations.txt"
        counter.parent.mkdir(parents=True, exist_ok=True)
        with counter.open("a+", encoding="utf-8") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.seek(0)
            ordinal = len(stream.readlines()) + 1
            value = f"evaluation:{env.docname}:{ordinal}"
            stream.write(value + "\n")
            stream.flush()
            fcntl.flock(stream, fcntl.LOCK_UN)
        return [nodes.paragraph(text=value)]


def _source_read(app, docname, source) -> None:
    _append_event({"event": "source-read", "docname": docname, "pid": os.getpid()})


def _environment_updated(app, env) -> None:
    _append_event({"event": "env-updated", "pid": os.getpid()})
    corrupt_docname = os.environ.get("SPHINX_LLM_POC_CORRUPT_DOCTREE")
    if corrupt_docname:
        pickled_cache = getattr(env, "_pickled_doctree_cache", None)
        if pickled_cache is not None:
            pickled_cache.pop(corrupt_docname, None)
        (Path(env.doctreedir) / f"{corrupt_docname}.doctree").write_bytes(b"broken")


def _snapshot_ready(app, docnames) -> None:
    _append_event(
        {
            "event": "snapshot-ready",
            "docnames": sorted(docnames),
            "pid": os.getpid(),
        }
    )


def _writer_finished(app, role) -> None:
    _append_event({"event": "writer-finished", "role": role, "pid": os.getpid()})


def _writer_failed(app, role, error_type) -> None:
    _append_event(
        {
            "error_type": error_type,
            "event": "writer-failed",
            "pid": os.getpid(),
            "role": role,
        }
    )


def _writer_exited(app, returncode) -> None:
    _append_event(
        {
            "event": "writer-exited",
            "pid": os.getpid(),
            "returncode": returncode,
        }
    )


def _wait_for(path: Path, description: str) -> None:
    deadline = time.monotonic() + 10
    while not path.exists():
        if time.monotonic() >= deadline:
            raise ExtensionError(f"timed out waiting for {description}")
        time.sleep(0.01)


def _writer_started(app, role) -> None:
    if not os.environ.get("SPHINX_LLM_POC_WRITER_BARRIER"):
        return
    other = "primary" if role == "markdown" else "markdown"
    probe_dir = _probe_dir()
    (probe_dir / f"{role}.started").touch()
    _append_event({"event": "writer-start", "role": role, "pid": os.getpid()})
    _wait_for(probe_dir / f"{other}.started", f"{other} writer")
    _append_event({"event": "writer-overlap", "role": role, "pid": os.getpid()})
    if role == "markdown" and os.environ.get("SPHINX_LLM_POC_HANG_MARKDOWN"):
        _wait_for(probe_dir / "release-markdown", "Markdown writer release")
    if os.environ.get("SPHINX_LLM_POC_FAIL_WRITER") == role:
        raise ExtensionError(f"intentional {role} writer failure")


def _doctree_resolved(app, doctree, docname) -> None:
    if not os.environ.get("SPHINX_LLM_POC_MUTATION_PROBE"):
        return
    probe_dir = _probe_dir()
    if app.builder.name == "llms-markdown":
        app.env.poc_markdown_mutation = docname
        doctree += nodes.paragraph(text="markdown-only-mutation")
        (probe_dir / "markdown.mutated").touch()
        return

    if os.environ.get("SPHINX_LLM_POC_FAIL_WRITER") == "markdown":
        return
    _wait_for(probe_dir / "markdown.mutated", "Markdown doctree mutation")
    if hasattr(app.env, "poc_markdown_mutation"):
        raise ExtensionError("Markdown environment mutation leaked into primary writer")
    doctree += nodes.paragraph(text="primary-only-mutation")


def setup(app):
    app.add_directive("evaluate-once", EvaluateOnceDirective)
    app.connect("source-read", _source_read)
    app.connect("env-updated", _environment_updated)
    app.connect("llms-shared-doctrees-ready", _snapshot_ready)
    app.connect("llms-shared-doctrees-writer-finished", _writer_finished)
    app.connect("llms-shared-doctrees-writer-failed", _writer_failed)
    app.connect("llms-shared-doctrees-writer-exited", _writer_exited)
    app.connect("llms-shared-doctrees-writer-started", _writer_started)
    app.connect("doctree-resolved", _doctree_resolved)
    return {
        "version": "1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
