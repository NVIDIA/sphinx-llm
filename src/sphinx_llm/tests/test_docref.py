# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the docref summary cache."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from sphinx_llm.docref import Docref


def _make_docref() -> tuple[Docref, dict[str, str]]:
    """Create a lightweight docref directive and its shared options."""
    shared_options = {
        "model": "model-a",
        "base_url": "https://example.com/v1",
        "api_key_env": "TEST_API_KEY",
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
