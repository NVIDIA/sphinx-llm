# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the Sphinx-native ``docref`` summary lifecycle."""

from __future__ import annotations

import hashlib
import json
import os
import time
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from sphinx.application import Sphinx
from sphinx.errors import ExtensionError, NoUri

from sphinx_llm import docref
from sphinx_llm import summary as summary_client


@pytest.fixture(autouse=True)
def _clear_summary_environment(monkeypatch):
    """Keep configuration tests independent of the caller's environment."""
    for name in list(os.environ):
        if name.startswith(("SPHINX_LLM_SUMMARY_", "OPENAI_")):
            monkeypatch.delenv(name)


def _write_project(
    tmp_path: Path,
    *,
    index: str,
    target: str = "Target\n======\n\nThe first target paragraph.\n",
    extra_documents: dict[str, str] | None = None,
) -> Path:
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)
    (source_dir / "conf.py").write_text(
        "\n".join(
            [
                'project = "docref tests"',
                'extensions = ["sphinx_llm.docref"]',
                'master_doc = "index"',
                "nitpicky = True",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (source_dir / "index.rst").write_text(index, encoding="utf-8")
    (source_dir / "target.rst").write_text(target, encoding="utf-8")
    for name, contents in (extra_documents or {}).items():
        path = source_dir / f"{name}.rst"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    return source_dir


def _build(
    source_dir: Path,
    *,
    freshenv: bool = True,
    confoverrides: dict | None = None,
    parallel: int = 0,
) -> tuple[Sphinx, Path, StringIO]:
    root = source_dir.parent
    output_dir = root / "build"
    warning = StringIO()
    app = Sphinx(
        srcdir=str(source_dir),
        confdir=str(source_dir),
        outdir=str(output_dir),
        doctreedir=str(root / "doctrees"),
        buildername="html",
        confoverrides=confoverrides or {},
        status=StringIO(),
        warning=warning,
        warningiserror=False,
        freshenv=freshenv,
        parallel=parallel,
    )
    app.build()
    assert app.statuscode == 0, warning.getvalue()
    return app, output_dir, warning


def _automatic_index(*, references: int = 1) -> str:
    directives = "\n".join(".. docref:: target\n" for _ in range(references))
    return f"Index\n=====\n\n.. toctree::\n   :hidden:\n\n   target\n\n{directives}"


def _report(output_dir: Path) -> dict:
    return json.loads(
        (output_dir / "sphinx-llm-summaries.json").read_text(encoding="utf-8")
    )


def _fake_generator(calls: list, prefix: str = "Generated summary"):
    def generate(settings, contents: str) -> str:
        calls.append((settings, contents))
        return f"{prefix} {len(calls)}."

    return generate


def test_automatic_summaries_are_deduplicated_and_sources_are_unchanged(
    tmp_path, monkeypatch
):
    source_dir = _write_project(tmp_path, index=_automatic_index(references=2))
    original_sources = {
        path: path.read_text(encoding="utf-8") for path in source_dir.glob("*.rst")
    }
    calls: list = []
    monkeypatch.setattr(docref, "generate_summary", _fake_generator(calls))

    app, output_dir, _ = _build(
        source_dir,
        confoverrides={
            "llms_txt_summary_enabled": True,
            "llms_txt_summary_cache_path": "cache/summaries.json",
        },
    )

    assert len(calls) == 1
    assert calls[0][1] == "Target\n\nThe first target paragraph."
    assert (output_dir / "index.html").read_text(encoding="utf-8").count(
        "Generated summary 1."
    ) == 2
    assert {
        path: path.read_text(encoding="utf-8") for path in source_dir.glob("*.rst")
    } == original_sources

    report = _report(output_dir)
    assert report["version"] == 1
    assert len(report["summaries"]) == 1
    summary = report["summaries"][0]
    assert summary["summary"] == "Generated summary 1."
    assert summary["origin"] == "generated"
    assert summary["target"] == "target"
    assert summary["provider"] == "openai-compatible"
    assert summary["model"] == ""
    assert len(summary["fingerprint"]) == 64
    assert len(summary["consumers"]) == 2
    assert summary["consumers"][0]["source"] == "index.rst"
    [cache_record] = getattr(app.env, docref.CACHE_ATTRIBUTE).values()
    cache_payload = json.loads(
        (source_dir / "cache" / "summaries.json").read_text(encoding="utf-8")
    )
    [shared_record] = [
        record
        for key, record in cache_payload["summaries"].items()
        if key.startswith("docref:")
    ]
    assert shared_record == cache_record
    assert cache_record["generation_settings"] == {
        "reasoning_effort": "none",
        "temperature": 0,
    }


@pytest.mark.parametrize(
    ("directive", "target", "enabled", "expected", "origin"),
    [
        (
            ".. docref:: target\n\n   A permanent reviewed summary.\n",
            "Target\n======\n\n.. meta::\n   :description: Target metadata.\n\nTarget body.\n",
            True,
            "A permanent reviewed summary.",
            "directive",
        ),
        (
            ".. docref:: target\n",
            "Target\n======\n\n.. meta::\n   :description: Target metadata.\n\nTarget body.\n",
            True,
            "Target metadata.",
            "html_meta",
        ),
        (
            ".. docref:: target\n",
            "Target\n======\n\nTarget body used as a local fallback.\n",
            False,
            "Target body used as a local fallback.",
            "fallback",
        ),
    ],
)
def test_override_precedence_and_disabled_fallback(
    tmp_path, monkeypatch, directive, target, enabled, expected, origin
):
    index = f"Index\n=====\n\n.. toctree::\n   :hidden:\n\n   target\n\n{directive}"
    source_dir = _write_project(tmp_path, index=index, target=target)
    calls: list = []
    monkeypatch.setattr(docref, "generate_summary", _fake_generator(calls))

    _, output_dir, _ = _build(
        source_dir, confoverrides={"llms_txt_summary_enabled": enabled}
    )

    assert calls == []
    assert expected in (output_dir / "index.html").read_text(encoding="utf-8")
    [summary] = _report(output_dir)["summaries"]
    assert summary["summary"] == expected
    assert summary["origin"] == origin
    assert "provider" not in summary
    assert "model" not in summary


def test_incremental_cache_hit_and_target_content_invalidation(tmp_path, monkeypatch):
    source_dir = _write_project(tmp_path, index=_automatic_index())
    first_calls: list = []
    monkeypatch.setattr(docref, "generate_summary", _fake_generator(first_calls))
    overrides = {"llms_txt_summary_enabled": True}

    _build(source_dir, confoverrides=overrides)
    assert len(first_calls) == 1

    cached_calls: list = []
    monkeypatch.setattr(docref, "generate_summary", _fake_generator(cached_calls))
    _, output_dir, _ = _build(source_dir, freshenv=False, confoverrides=overrides)
    assert cached_calls == []
    assert _report(output_dir)["summaries"][0]["summary"] == "Generated summary 1."

    target = source_dir / "target.rst"
    target.write_text(
        "Target\n======\n\nThe target content has now changed.\n", encoding="utf-8"
    )
    newer = time.time() + 60
    os.utime(target, (newer, newer))
    invalidated_calls: list = []
    monkeypatch.setattr(
        docref, "generate_summary", _fake_generator(invalidated_calls, "Regenerated")
    )
    _, output_dir, _ = _build(source_dir, freshenv=False, confoverrides=overrides)

    assert len(invalidated_calls) == 1
    assert "The target content has now changed." in invalidated_calls[0][1]
    assert _report(output_dir)["summaries"][0]["summary"] == "Regenerated 1."
    assert "Regenerated 1." in (output_dir / "index.html").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "changed_setting",
    [
        "model",
        "base_url",
        "api_key_env",
        "allow_insecure_auth",
        "max_input_chars",
        "timeout",
        "prompt_version",
    ],
)
def test_generation_setting_changes_invalidate_cache(
    tmp_path, monkeypatch, changed_setting
):
    source_dir = _write_project(tmp_path, index=_automatic_index())
    first_overrides = {
        "llms_txt_summary_enabled": True,
        "llms_txt_summary_api_key_env": "FIRST_API_KEY",
        "llms_txt_summary_allow_insecure_auth": False,
        "llms_txt_summary_max_input_chars": 12_000,
        "llms_txt_summary_timeout": 60,
        "llms_txt_summary_model": "model-a",
        "llms_txt_summary_base_url": "https://one.invalid",
    }
    first_calls: list = []
    monkeypatch.setattr(docref, "generate_summary", _fake_generator(first_calls))
    _build(source_dir, confoverrides=first_overrides)
    assert len(first_calls) == 1

    second_overrides = dict(first_overrides)
    if changed_setting == "model":
        second_overrides["llms_txt_summary_model"] = "model-b"
    elif changed_setting == "base_url":
        second_overrides["llms_txt_summary_base_url"] = "https://two.invalid"
    elif changed_setting == "api_key_env":
        second_overrides["llms_txt_summary_api_key_env"] = "SECOND_API_KEY"
    elif changed_setting == "allow_insecure_auth":
        second_overrides["llms_txt_summary_allow_insecure_auth"] = True
    elif changed_setting == "max_input_chars":
        second_overrides["llms_txt_summary_max_input_chars"] = 100
    elif changed_setting == "timeout":
        second_overrides["llms_txt_summary_timeout"] = 15
    else:
        monkeypatch.setattr(
            summary_client,
            "SUMMARY_PROMPT_VERSION",
            summary_client.SUMMARY_PROMPT_VERSION + 1,
        )

    second_calls: list = []
    monkeypatch.setattr(
        docref, "generate_summary", _fake_generator(second_calls, "Changed")
    )
    _, output_dir, _ = _build(
        source_dir, freshenv=False, confoverrides=second_overrides
    )

    assert len(second_calls) == 1
    assert _report(output_dir)["summaries"][0]["summary"] == "Changed 1."


def test_parallel_reading_merges_requests_and_generates_once(tmp_path, monkeypatch):
    source_dir = _write_project(
        tmp_path,
        index=(
            "Index\n=====\n\n"
            ".. toctree::\n"
            "   :hidden:\n\n"
            "   target\n"
            "   first\n"
            "   second\n"
        ),
        extra_documents={
            "first": "First\n=====\n\n.. docref:: target\n",
            "second": "Second\n======\n\n.. docref:: target\n",
        },
    )
    calls: list = []
    monkeypatch.setattr(docref, "generate_summary", _fake_generator(calls))

    _, output_dir, _ = _build(
        source_dir,
        confoverrides={"llms_txt_summary_enabled": True},
        parallel=2,
    )

    assert len(calls) == 1
    [summary] = _report(output_dir)["summaries"]
    assert summary["origin"] == "generated"
    assert [consumer["docname"] for consumer in summary["consumers"]] == [
        "first",
        "second",
    ]


@pytest.mark.parametrize("hash_kind", ["md5", "pr115"])
def test_legacy_hash_seeds_cache_without_modifying_source(
    tmp_path, monkeypatch, hash_kind
):
    target_text = "Target\n\nThe first target paragraph."
    if hash_kind == "md5":
        legacy_hash = hashlib.md5(target_text.encode()).hexdigest()
    else:
        legacy_hash = summary_client.summary_fingerprint(
            target_text,
            "legacy-model",
        )
    index = (
        "Index\n=====\n\n"
        ".. toctree::\n"
        "   :hidden:\n\n"
        "   target\n\n"
        ".. docref:: target\n"
        f"   :hash: {legacy_hash}\n"
        "   :model: legacy-model\n\n"
        "   A legacy generated summary.\n"
    )
    source_dir = _write_project(tmp_path, index=index)
    source = source_dir / "index.rst"
    original = source.read_text(encoding="utf-8")
    calls: list = []
    monkeypatch.setattr(docref, "generate_summary", _fake_generator(calls))

    _, output_dir, warning = _build(
        source_dir, confoverrides={"llms_txt_summary_enabled": True}
    )

    assert calls == []
    assert source.read_text(encoding="utf-8") == original
    assert ":hash: is deprecated" in warning.getvalue()
    assert "A legacy generated summary." in (output_dir / "index.html").read_text(
        encoding="utf-8"
    )
    [summary] = _report(output_dir)["summaries"]
    assert summary["origin"] == "generated"
    assert summary["model"] == "legacy-model"


def test_environment_configuration_and_report_do_not_expose_secrets(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("SPHINX_LLM_SUMMARY_ENABLED", "true")
    monkeypatch.setenv("SPHINX_LLM_SUMMARY_PROVIDER", "openai-compatible")
    monkeypatch.setenv("SPHINX_LLM_SUMMARY_MODEL", "environment-model")
    monkeypatch.setenv(
        "SPHINX_LLM_SUMMARY_BASE_URL", "https://user:password@example.invalid"
    )
    monkeypatch.setenv("SPHINX_LLM_SUMMARY_API_KEY_ENV", "SUMMARY_SECRET")
    monkeypatch.setenv("SUMMARY_SECRET", "super-secret-value")
    source_dir = _write_project(tmp_path, index=_automatic_index())
    calls: list = []
    monkeypatch.setattr(docref, "generate_summary", _fake_generator(calls))

    _, output_dir, _ = _build(source_dir)

    settings = calls[0][0]
    assert settings.enabled is True
    assert settings.provider == "openai-compatible"
    assert settings.model == "environment-model"
    assert settings.base_url == "https://user:password@example.invalid"
    report_text = (output_dir / "sphinx-llm-summaries.json").read_text(encoding="utf-8")
    assert "password" not in report_text
    assert "super-secret-value" not in report_text
    assert "SUMMARY_SECRET" not in report_text


def test_authored_overrides_take_precedence_over_an_existing_cache(
    tmp_path, monkeypatch
):
    source_dir = _write_project(tmp_path, index=_automatic_index())
    calls: list = []
    monkeypatch.setattr(docref, "generate_summary", _fake_generator(calls))
    overrides = {"llms_txt_summary_enabled": True}
    _build(source_dir, confoverrides=overrides)
    assert len(calls) == 1

    target = source_dir / "target.rst"
    target.write_text(
        "Target\n======\n\n.. meta::\n"
        "   :description: Reviewed page description.\n\nTarget body.\n",
        encoding="utf-8",
    )
    newer = time.time() + 60
    os.utime(target, (newer, newer))
    calls.clear()
    _, output_dir, _ = _build(source_dir, freshenv=False, confoverrides=overrides)
    assert calls == []
    assert _report(output_dir)["summaries"][0]["origin"] == "html_meta"

    index = source_dir / "index.rst"
    index.write_text(
        "Index\n=====\n\n.. toctree::\n   :hidden:\n\n   target\n\n"
        ".. docref:: target\n\n   A reference-specific review.\n",
        encoding="utf-8",
    )
    newer = time.time() + 60
    os.utime(index, (newer, newer))
    _, output_dir, _ = _build(source_dir, freshenv=False, confoverrides=overrides)
    assert calls == []
    [summary] = _report(output_dir)["summaries"]
    assert summary["origin"] == "directive"
    assert summary["summary"] == "A reference-specific review."


def test_purge_removes_requests_for_a_changed_consumer(tmp_path, monkeypatch):
    source_dir = _write_project(tmp_path, index=_automatic_index())
    monkeypatch.setattr(docref, "generate_summary", _fake_generator([]))
    overrides = {"llms_txt_summary_enabled": True}
    _build(source_dir, confoverrides=overrides)

    index = source_dir / "index.rst"
    index.write_text(
        "Index\n=====\n\n.. toctree::\n   :hidden:\n\n   target\n",
        encoding="utf-8",
    )
    newer = time.time() + 60
    os.utime(index, (newer, newer))
    app, output_dir, _ = _build(source_dir, freshenv=False, confoverrides=overrides)

    assert getattr(app.env, docref.REQUESTS_ATTRIBUTE) == {}
    assert _report(output_dir)["summaries"] == []


def test_manual_body_preserves_markup_and_generated_text_is_not_parsed(
    tmp_path, monkeypatch
):
    index = (
        "Index\n=====\n\n.. toctree::\n   :hidden:\n\n   target\n\n"
        ".. docref:: target\n\n"
        "   A **reviewed** summary with an `external link <https://example.com>`_.\n"
    )
    source_dir = _write_project(tmp_path, index=index)
    monkeypatch.setattr(docref, "generate_summary", _fake_generator([]))
    _, output_dir, _ = _build(source_dir)
    html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "<strong>reviewed</strong>" in html
    assert 'href="https://example.com"' in html

    automatic_source = _write_project(tmp_path / "automatic", index=_automatic_index())
    monkeypatch.setattr(
        docref,
        "generate_summary",
        lambda settings, contents: (
            "Safe text.\n\n.. raw:: html\n\n   <script>x</script>"
        ),
    )
    _, output_dir, _ = _build(
        automatic_source, confoverrides={"llms_txt_summary_enabled": True}
    )
    html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html


def test_scalar_override_wins_over_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SPHINX_LLM_SUMMARY_MODEL", "environment-model")
    source_dir = _write_project(tmp_path, index=_automatic_index())
    calls: list = []
    monkeypatch.setattr(docref, "generate_summary", _fake_generator(calls))

    app, _, _ = _build(
        source_dir,
        confoverrides={
            "llms_txt_summary_enabled": True,
            "llms_txt_summary_model": "override-model",
        },
    )

    assert calls[0][0].model == "override-model"
    assert (
        app.extensions["sphinx_llm.docref"].metadata["env_version"]
        == docref.ENV_VERSION
    )


def test_enabled_generation_requires_explicit_model(tmp_path, monkeypatch):
    monkeypatch.delenv("SPHINX_LLM_SUMMARY_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    source_dir = _write_project(tmp_path, index=_automatic_index())

    with pytest.raises(ExtensionError, match="llms_txt_summary_model"):
        _build(source_dir, confoverrides={"llms_txt_summary_enabled": True})


def test_missing_target_warns_and_uses_fallback(tmp_path):
    source_dir = _write_project(
        tmp_path,
        index="Index\n=====\n\n.. docref:: missing\n",
    )

    _, output_dir, warning = _build(source_dir)

    assert "Unable to load document referenced by docref" in warning.getvalue()
    assert "See missing." in (output_dir / "index.html").read_text(encoding="utf-8")
    [summary] = _report(output_dir)["summaries"]
    assert summary["origin"] == "fallback"


def test_no_uri_omits_read_more_link():
    app = SimpleNamespace(
        builder=SimpleNamespace(
            get_relative_uri=lambda *args: (_ for _ in ()).throw(NoUri)
        )
    )

    assert docref._link_node(app, "index", "target") is None


def test_merge_docref_data_merges_worker_requests():
    env = SimpleNamespace()
    other = SimpleNamespace(
        sphinx_llm_summary_requests={
            "worker:0": {
                "request_id": "worker:0",
                "source_docname": "worker",
            }
        }
    )

    docref.merge_docref_data(None, env, ["worker"], other)

    assert docref._requests(env) == other.sphinx_llm_summary_requests


def test_generate_summary_forwards_shared_limits_and_security(monkeypatch):
    settings = docref.SummaryOptions(
        enabled=True,
        provider="openai-compatible",
        model="test-model",
        base_url="https://example.invalid/v1",
        api_key_env="",
        allow_insecure_auth=True,
        max_input_chars=5,
        timeout=12,
        cache_path="",
    )
    calls = []

    def summarize(text, model, **kwargs):
        calls.append((text, model, kwargs))
        return "Summary."

    monkeypatch.setattr(summary_client, "summarize_text", summarize)

    assert docref.generate_summary(settings, "complete contents") == "Summary."
    assert calls == [
        (
            "compl",
            "test-model",
            {
                "base_url": "https://example.invalid/v1",
                "api_key_env": "",
                "reasoning_effort": "none",
                "timeout": 12,
                "use_environment_defaults": False,
                "allow_insecure_auth": True,
            },
        )
    ]


def test_generate_summary_redacts_provider_failure(monkeypatch):
    settings = docref.SummaryOptions(
        enabled=True,
        provider="openai-compatible",
        model="test-model",
        base_url="https://example.invalid/v1",
        api_key_env="",
        allow_insecure_auth=False,
        max_input_chars=100,
        timeout=60,
        cache_path="",
    )
    monkeypatch.setattr(
        summary_client,
        "summarize_text",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("provider leaked top-secret")
        ),
    )

    with pytest.raises(ExtensionError, match="provider configuration") as error:
        docref.generate_summary(settings, "contents")

    assert "top-secret" not in str(error.value)
