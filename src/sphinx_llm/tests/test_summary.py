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
    monkeypatch.delenv("OPENAI_REASONING_EFFORT", raising=False)
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
        extra_body={"reasoning_effort": "none"},
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
    """Test model, endpoint, credential, and reasoning environment variables."""
    monkeypatch.setenv("OPENAI_MODEL", "env-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://models.example.com/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "low")
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
    assert mock_openai.return_value.chat.completions.create.call_args.kwargs[
        "extra_body"
    ] == {"reasoning_effort": "low"}


def test_summarize_text_can_omit_reasoning_effort(monkeypatch):
    """Test endpoints without reasoning support can omit the setting."""
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "high")
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Summary."))]
    )

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = response
        summarize_text("Page contents.", "test-model", reasoning_effort="")

    assert (
        "extra_body"
        not in mock_openai.return_value.chat.completions.create.call_args.kwargs
    )


def test_summarize_text_can_disable_environment_defaults(monkeypatch):
    """Dedicated adapters can isolate themselves from ambient OPENAI settings."""
    monkeypatch.setenv("OPENAI_BASE_URL", "https://ambient.example/v1")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "high")
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Summary."))]
    )
    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = response
        summarize_text(
            "Page contents.",
            "test-model",
            api_key_env="",
            use_environment_defaults=False,
        )

    mock_openai.assert_called_once_with(api_key="not-used")
    assert mock_openai.return_value.chat.completions.create.call_args.kwargs[
        "extra_body"
    ] == {"reasoning_effort": "none"}


def test_summarize_text_rejects_key_over_remote_plain_http(monkeypatch):
    """Credentials are never sent to non-loopback endpoints without TLS."""
    monkeypatch.setenv("TEST_API_KEY", "top-secret")
    with patch("openai.OpenAI") as mock_openai:
        with pytest.raises(ExtensionError, match="plain HTTP") as error:
            summarize_text(
                "Page contents.",
                "test-model",
                base_url="http://models.example.com/v1",
                api_key_env="TEST_API_KEY",
            )
    mock_openai.assert_not_called()
    assert "top-secret" not in str(error.value)


def test_summarize_text_can_allow_key_over_remote_plain_http(monkeypatch):
    """An explicit override permits authentication on a trusted HTTP network."""
    monkeypatch.setenv("TEST_API_KEY", "secret")
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Summary."))]
    )
    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = response
        summarize_text(
            "Page contents.",
            "test-model",
            base_url="http://models.internal/v1",
            api_key_env="TEST_API_KEY",
            allow_insecure_auth=True,
        )
    mock_openai.assert_called_once_with(
        api_key="secret", base_url="http://models.internal/v1"
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "http://localhost:8000/v1",
        "http://service.localhost:8000/v1",
        "http://127.0.0.1:8000/v1",
        "http://[::1]:8000/v1",
    ],
)
def test_summarize_text_allows_key_over_loopback_http(monkeypatch, base_url):
    """Authenticated local development endpoints remain supported."""
    monkeypatch.setenv("TEST_API_KEY", "secret")
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Summary."))]
    )
    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = response
        summarize_text(
            "Page contents.",
            "test-model",
            base_url=base_url,
            api_key_env="TEST_API_KEY",
        )
    mock_openai.assert_called_once_with(api_key="secret", base_url=base_url)


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
