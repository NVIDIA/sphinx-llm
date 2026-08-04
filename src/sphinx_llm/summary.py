# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Shared helpers for generating summaries with an OpenAI-compatible API."""

import hashlib
import os

from sphinx.errors import ExtensionError

DEFAULT_MODEL = ""
DEFAULT_MODEL_ENV = "OPENAI_MODEL"
SYSTEM_PROMPT = "Keep responses concise and focused, avoiding unnecessary elaboration or additional context unless explicitly requested. Do not use bullet points, lists, or nested structures unless specifically asked. If a response requires further detail, prioritize the most relevant information and conclude promptly. Avoid apologies or mentions of limitations; simply deliver the most direct and straightforward answer."
DEFAULT_API_KEY_ENV = "OPENAI_API_KEY"
SUMMARY_PROMPT_VERSION = 2


def _missing_generation_dependencies(error: ImportError) -> ExtensionError:
    """Return a helpful error when the optional generation extra is absent."""
    return ExtensionError(
        "LLM summarization requires the optional generation dependencies. "
        "Install them with 'pip install sphinx-llm[gen]'.",
        error,
        "sphinx-llm",
    )


def summary_fingerprint(
    text: str,
    model: str,
    *,
    base_url: str = "",
    api_key_env: str = DEFAULT_API_KEY_ENV,
) -> str:
    """Return a stable cache key for text and every generation setting."""
    return hashlib.sha256(
        (
            f"{SUMMARY_PROMPT_VERSION}\0{model}\0{base_url}\0{api_key_env}\0{text}"
        ).encode()
    ).hexdigest()


def _extract_summary(response: object) -> str:
    """Validate and extract summary text from a chat completion response."""
    try:
        summary = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError):
        summary = None
    if not isinstance(summary, str) or not summary.strip():
        raise ExtensionError(
            "The OpenAI-compatible endpoint returned a malformed or empty summary"
        )
    return summary.strip()


def summarize_text(
    text: str,
    model: str = DEFAULT_MODEL,
    *,
    base_url: str = "",
    api_key_env: str = DEFAULT_API_KEY_ENV,
) -> str:
    """Generate a concise summary using an OpenAI-compatible chat endpoint."""
    model = model or os.environ.get(DEFAULT_MODEL_ENV, "")
    if not isinstance(model, str) or not model.strip():
        raise ExtensionError(
            "No summary model is configured. Set 'model' in sphinx_llm_options "
            f"or set {DEFAULT_MODEL_ENV}."
        )

    try:
        from openai import OpenAI
    except ImportError as error:
        raise _missing_generation_dependencies(error) from error

    effective_base_url = base_url or os.environ.get("OPENAI_BASE_URL", "")
    configured_api_key = os.environ.get(api_key_env) if api_key_env else None
    # The OpenAI client requires a non-empty value even when the endpoint does
    # not authenticate requests.
    api_key = configured_api_key or "not-used"

    client_options = {"api_key": api_key}
    if effective_base_url:
        client_options["base_url"] = effective_base_url
    client = OpenAI(**client_options)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    text
                    + "\n\nRespond only with a concise one-sentence summary of the above."
                ),
            },
        ],
    )
    return _extract_summary(response)
