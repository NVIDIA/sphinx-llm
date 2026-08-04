# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Shared helpers for generating summaries with an OpenAI-compatible API."""

import hashlib
import ipaddress
import os
from urllib.parse import urlparse

from sphinx.errors import ExtensionError

DEFAULT_MODEL = ""
SYSTEM_PROMPT = "Keep responses concise and focused, avoiding unnecessary elaboration or additional context unless explicitly requested. Do not use bullet points, lists, or nested structures unless specifically asked. If a response requires further detail, prioritize the most relevant information and conclude promptly. Avoid apologies or mentions of limitations; simply deliver the most direct and straightforward answer."
DEFAULT_API_KEY_ENV = "OPENAI_API_KEY"
SUMMARY_PROMPT_VERSION = 1


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


def _is_loopback_url(url: str) -> bool:
    """Return whether an endpoint URL targets the local machine."""
    hostname = urlparse(url).hostname
    if not hostname:
        return False
    if hostname.lower() == "localhost" or hostname.lower().endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def summarize_text(
    text: str,
    model: str = DEFAULT_MODEL,
    *,
    base_url: str = "",
    api_key_env: str = DEFAULT_API_KEY_ENV,
) -> str:
    """Generate a concise summary using an OpenAI-compatible chat endpoint."""
    if not isinstance(model, str) or not model.strip():
        raise ExtensionError(
            "No summary model is configured. Set 'model' in sphinx_llm_options "
            "or pass a model explicitly."
        )

    try:
        from openai import OpenAI
    except ImportError as error:
        raise _missing_generation_dependencies(error) from error

    effective_base_url = base_url or os.environ.get("OPENAI_BASE_URL", "")
    configured_api_key = os.environ.get(api_key_env) if api_key_env else None
    if (
        configured_api_key
        and urlparse(effective_base_url).scheme.lower() == "http"
        and not _is_loopback_url(effective_base_url)
    ):
        raise ExtensionError(
            "Refusing to send an API key to an unencrypted non-loopback HTTP "
            "endpoint. Use HTTPS, a loopback URL, or an unauthenticated endpoint."
        )

    api_key = configured_api_key
    if not api_key and effective_base_url:
        # Many local OpenAI-compatible servers do not authenticate, but the
        # OpenAI client requires a non-empty value.
        api_key = "not-used"
    elif not api_key:
        raise ExtensionError(
            f"API key environment variable {api_key_env!r} is not set. "
            "Set it or configure an OpenAI-compatible base URL."
        )

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
                    text + "\n\nHere's a concise one-sentence summary of the above:"
                ),
            },
        ],
    )
    try:
        summary = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as error:
        raise ExtensionError(
            "The OpenAI-compatible endpoint returned a malformed or empty summary"
        ) from error
    if not isinstance(summary, str) or not summary.strip():
        raise ExtensionError(
            "The OpenAI-compatible endpoint returned a malformed or empty summary"
        )
    return summary.strip()
