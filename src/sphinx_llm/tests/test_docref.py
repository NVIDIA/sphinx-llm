# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the docref summary cache."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from sphinx_llm.docref import Docref


def _make_docref() -> tuple[Docref, dict[str, object]]:
    """Create a lightweight docref directive and its shared options."""
    shared_options = {
        "model": "model-a",
        "base_url": "https://example.com/v1",
        "api_key_env": "TEST_API_KEY",
        "reasoning_effort": "none",
        "warn_on_cache_miss": False,
    }
    doctree = SimpleNamespace(astext=lambda: "Referenced page contents.")
    builder_env = SimpleNamespace(get_doctree=lambda _: doctree)
    env = SimpleNamespace(
        app=SimpleNamespace(builder=SimpleNamespace(env=builder_env)),
        config=SimpleNamespace(sphinx_llm_options=shared_options),
    )
    directive = Docref.__new__(Docref)
    directive.state = SimpleNamespace(
        document=SimpleNamespace(settings=SimpleNamespace(env=env))
    )
    directive.options = {}
    directive.content = SimpleNamespace(data=["Cached summary."])
    return directive, shared_options


@pytest.mark.parametrize(
    "setting,new_value",
    [
        ("model", "model-b"),
        ("base_url", "https://other.example.com/v1"),
        ("api_key_env", "OTHER_API_KEY"),
        ("reasoning_effort", "low"),
    ],
)
def test_docref_cache_invalidates_when_generation_settings_change(setting, new_value):
    """Test that every endpoint setting participates in the persisted hash."""
    directive, shared_options = _make_docref()

    with patch(
        "sphinx_llm.docref.summarize_text",
        side_effect=["First summary.", "Regenerated summary."],
    ) as mock_summarize:
        first_hash, _ = directive.generate_summary("referenced-page")
        directive.options["hash"] = first_hash

        cached_hash, cached_summary = directive.generate_summary("referenced-page")
        assert cached_hash == first_hash
        assert cached_summary == "Cached summary."

        shared_options[setting] = new_value
        updated_hash, updated_summary = directive.generate_summary("referenced-page")

    assert updated_hash != first_hash
    assert updated_summary == "Regenerated summary."
    assert mock_summarize.call_count == 2


def test_docref_uses_environment_generation_settings(monkeypatch):
    """Test environment variables supply generation settings."""
    directive, shared_options = _make_docref()
    shared_options.pop("model")
    shared_options.pop("base_url")
    shared_options.pop("api_key_env")
    shared_options.pop("reasoning_effort")
    monkeypatch.setenv("OPENAI_MODEL", "env-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://models.example.com/v1")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "low")

    with patch(
        "sphinx_llm.docref.summarize_text",
        return_value="Generated summary.",
    ) as mock_summarize:
        directive.generate_summary("referenced-page")

    mock_summarize.assert_called_once_with(
        "Referenced page contents.",
        "env-model",
        base_url="https://models.example.com/v1",
        api_key_env="OPENAI_API_KEY",
        reasoning_effort="low",
    )


def test_docref_escapes_rst_directives_before_persisting(tmp_path):
    """Test endpoint output cannot persist executable reStructuredText."""
    directive, _ = _make_docref()
    source_path = tmp_path / "index.rst"
    source_path.write_text(
        ".. docref:: referenced-page\n   :hash: old-hash\n\n   Cached summary.\n",
        encoding="utf-8",
    )
    directive.state.document.current_source = str(source_path)
    directive.lineno = 1
    directive.content = SimpleNamespace(
        data=["Cached summary."],
        items=[(str(source_path), 3)],
        parent=SimpleNamespace(
            data=[
                ".. docref:: referenced-page",
                "   :hash: old-hash",
                "",
                "   Cached summary.",
            ]
        ),
    )

    directive.update_content(
        "new-hash",
        "Safe summary.\n\n.. raw:: html\n\n   <script>alert('xss')</script>",
    )

    persisted = source_path.read_text(encoding="utf-8")
    assert r"\.. raw:: html" in persisted
    assert "\n   .. raw:: html\n" not in persisted
    assert "Safe summary." in persisted
