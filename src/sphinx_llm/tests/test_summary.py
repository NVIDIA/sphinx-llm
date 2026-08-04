# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the shared OpenAI-compatible summary client."""

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sphinx.errors import ExtensionError

from sphinx_llm.summary import SYSTEM_PROMPT, summarize_text


def test_summarize_text_uses_openai_compatible_endpoint(monkeypatch):
    """Test model, endpoint, credentials, and prompt forwarding."""
    monkeypatch.setenv("TEST_API_KEY", "secret")
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=" Generated summary. "))
        ]
    )

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = response
        summary = summarize_text(
            "Page contents.",
            "test-model",
            base_url="https://example.com/v1",
            api_key_env="TEST_API_KEY",
        )

    assert summary == "Generated summary."
    mock_openai.assert_called_once_with(
        api_key="secret", base_url="https://example.com/v1"
    )
    mock_openai.return_value.chat.completions.create.assert_called_once_with(
        model="test-model",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Page contents.\n\n"
                    "Respond only with a concise one-sentence summary of the above."
                ),
            },
        ],
    )


@pytest.mark.parametrize(
    "base_url",
    ["", "http://localhost:8000/v1", "http://models.internal/v1"],
)
def test_summarize_text_allows_missing_api_key(monkeypatch, base_url):
    """Test that any compatible endpoint can use a dummy credential."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Summary."))]
    )

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = response
        summarize_text(
            "Page contents.",
            "test-model",
            base_url=base_url,
        )

    expected_options = {"api_key": "not-used"}
    if base_url:
        expected_options["base_url"] = base_url
    mock_openai.assert_called_once_with(**expected_options)


def test_summarize_text_requires_an_explicit_model(monkeypatch):
    """Test that a local-server model is never sent to OpenAI by default."""
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    with pytest.raises(ExtensionError, match="summary model"):
        summarize_text("Page contents.")


def test_summarize_text_uses_environment_configuration(monkeypatch):
    """Test model, endpoint, and credential environment variables."""
    monkeypatch.setenv("OPENAI_MODEL", "env-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://models.example.com/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Summary."))]
    )

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = response
        assert summarize_text("Page contents.") == "Summary."

    mock_openai.assert_called_once_with(
        api_key="secret", base_url="https://models.example.com/v1"
    )
    assert (
        mock_openai.return_value.chat.completions.create.call_args.kwargs["model"]
        == "env-model"
    )


@pytest.mark.skipif(
    os.environ.get("SPHINX_LLM_LIVE_TEST") != "1",
    reason="requires a live OpenAI-compatible endpoint",
)
def test_summarize_text_with_live_endpoint():
    """Test summary generation against the CI Ollama service."""
    summary = summarize_text("Sphinx generates documentation from source files.")

    assert summary


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(choices=[]),
        SimpleNamespace(choices=[SimpleNamespace()]),
        SimpleNamespace(choices=[SimpleNamespace(message=None)]),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace())]),
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="  \n  "))]
        ),
    ],
)
def test_summarize_text_rejects_malformed_or_empty_responses(monkeypatch, response):
    """Test that invalid compatible-endpoint responses produce one clear error."""
    monkeypatch.setenv("OPENAI_API_KEY", "secret")

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = response
        with pytest.raises(ExtensionError, match="malformed or empty summary"):
            summarize_text("Page contents.", "test-model")
