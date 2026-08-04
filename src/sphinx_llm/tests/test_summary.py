# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the shared OpenAI-compatible summary client."""

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
                    "Here's a concise one-sentence summary of the above:"
                ),
            },
        ],
    )


def test_summarize_text_allows_unauthenticated_local_endpoint(monkeypatch):
    """Test that local compatible endpoints do not require a credential."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Summary."))]
    )

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = response
        summarize_text(
            "Page contents.",
            "test-model",
            base_url="http://localhost:8000/v1",
        )

    mock_openai.assert_called_once_with(
        api_key="not-used", base_url="http://localhost:8000/v1"
    )


def test_summarize_text_requires_key_for_default_endpoint(monkeypatch):
    """Test that the default hosted endpoint requires configured credentials."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ExtensionError, match="OPENAI_API_KEY"):
        summarize_text("Page contents.", "test-model")


def test_summarize_text_requires_an_explicit_model(monkeypatch):
    """Test that a local-server model is never sent to OpenAI by default."""
    monkeypatch.setenv("OPENAI_API_KEY", "secret")

    with pytest.raises(ExtensionError, match="summary model"):
        summarize_text("Page contents.")


def test_summarize_text_rejects_api_key_over_remote_http(monkeypatch):
    """Test that credentials are not sent to unencrypted remote endpoints."""
    monkeypatch.setenv("TEST_API_KEY", "secret")

    with patch("openai.OpenAI") as mock_openai:
        with pytest.raises(ExtensionError, match="unencrypted"):
            summarize_text(
                "Page contents.",
                "test-model",
                base_url="http://example.com/v1",
                api_key_env="TEST_API_KEY",
            )

    mock_openai.assert_not_called()


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
