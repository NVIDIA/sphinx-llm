# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Acceptance tests for generated llms.txt page summaries."""

import json
import sys
import traceback
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import docutils.nodes
import pytest
from sphinx.errors import ExtensionError

import sphinx_llm
from sphinx_llm.tests.test_txt import (
    _HTML_META_PAGE,
    _build_sphinx,
    _get_html_meta_description,
)
from sphinx_llm.txt import MarkdownGenerator


def _generator(tmp_path: Path, **config_values) -> tuple[MarkdownGenerator, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    defaults = {
        "llms_txt_summary_enabled": True,
        "llms_txt_summary_provider": "openai-compatible",
        "llms_txt_summary_model": "test-model",
        "llms_txt_summary_base_url": "https://example.com/v1",
        "llms_txt_summary_api_key_env": "TEST_API_KEY",
        "llms_txt_summary_max_input_chars": 12_000,
        "llms_txt_summary_timeout": 60,
        "llms_txt_summary_cache_path": "",
    }
    defaults.update(config_values)
    config = SimpleNamespace(**defaults, overrides={})
    environment = SimpleNamespace(
        get_doctree=lambda _: SimpleNamespace(traverse=lambda _: [])
    )
    app = SimpleNamespace(
        config=config,
        env=environment,
        doctreedir=tmp_path / "doctrees",
        confdir=tmp_path,
    )
    generator = MarkdownGenerator(app)
    markdown_file = tmp_path / "page.html.md"
    markdown_file.write_text(
        "# Page\n\nComplete **Markdown** contents.", encoding="utf-8"
    )
    generator._docname_by_output_file[markdown_file] = "page"
    return generator, markdown_file


def test_summary_configuration_precedence(monkeypatch, tmp_path):
    """Command-line overrides beat environment, then conf.py, then defaults."""
    generator, _ = _generator(
        tmp_path,
        llms_txt_summary_model="conf-model",
        llms_txt_summary_timeout=20,
    )
    monkeypatch.setenv("SPHINX_LLM_SUMMARY_MODEL", "env-model")
    monkeypatch.setenv("SPHINX_LLM_SUMMARY_TIMEOUT", "30")

    options = generator._get_summary_options()
    assert options.model == "env-model"
    assert options.timeout == 30

    generator.app.config.overrides = {
        "llms_txt_summary_model": "cli-model",
        "llms_txt_summary_timeout": "40",
    }
    generator.app.config.llms_txt_summary_model = "cli-model"
    generator.app.config.llms_txt_summary_timeout = 40
    options = generator._get_summary_options()
    assert options.model == "cli-model"
    assert options.timeout == 40


def test_sphinx_command_line_override_and_built_in_defaults(monkeypatch):
    """A real Sphinx ``-D`` value wins over env and defaults remain exact."""
    monkeypatch.setenv("SPHINX_LLM_SUMMARY_MODEL", "env-model")
    build = _build_sphinx(
        "html",
        {
            "llms_txt_summary_enabled": False,
            "llms_txt_summary_model": "cli-model",
        },
    )
    try:
        app, _, _ = next(build)
        options = MarkdownGenerator(app)._get_summary_options()
    finally:
        build.close()

    assert options.enabled is False
    assert options.provider == "openai-compatible"
    assert options.model == "cli-model"
    assert options.base_url == ""
    assert options.api_key_env == "SPHINX_LLM_SUMMARY_API_KEY"
    assert options.max_input_chars == 12_000
    assert options.timeout == 60
    assert options.cache_path == ""


@pytest.mark.parametrize("value", ["maybe", "-1", "0"])
def test_invalid_summary_environment_values_raise(monkeypatch, tmp_path, value):
    """Invalid environment configuration fails clearly when generation is used."""
    generator, _ = _generator(tmp_path)
    if value == "maybe":
        monkeypatch.setenv("SPHINX_LLM_SUMMARY_ENABLED", value)
    else:
        monkeypatch.setenv("SPHINX_LLM_SUMMARY_MAX_INPUT_CHARS", value)
    with pytest.raises(ExtensionError, match="SPHINX_LLM_SUMMARY"):
        generator._get_summary_options()


def test_disabled_summary_path_does_not_call_provider(tmp_path):
    """Default-disabled descriptions retain the Markdown fallback."""
    generator, markdown_file = _generator(tmp_path, llms_txt_summary_enabled=False)
    with patch.object(generator, "generate_page_summary") as generate:
        assert generator.get_page_description(markdown_file) == (
            "Complete **Markdown** contents."
        )
    generate.assert_not_called()


def test_html_meta_precedence_and_whitespace_fallback(tmp_path):
    """Non-empty authored metadata wins, while whitespace-only metadata does not."""
    generator, markdown_file = _generator(tmp_path)
    meta = docutils.nodes.meta()
    meta["name"] = "description"
    meta["content"] = "  Authored description.  "
    generator.app.env.get_doctree = lambda _: SimpleNamespace(traverse=lambda _: [meta])
    with patch.object(generator, "generate_page_summary") as generate:
        assert generator.get_page_description(markdown_file) == "Authored description."
    generate.assert_not_called()

    meta["content"] = "  \n "
    with patch.object(
        generator, "generate_page_summary", return_value="Generated description."
    ) as generate:
        assert generator.get_page_description(markdown_file) == "Generated description."
    generate.assert_called_once_with("page", markdown_file)


def test_summary_uses_bounded_markdown_and_complete_fingerprint(
    monkeypatch, tmp_path, caplog
):
    """Only a prefix is sent, but changes beyond it invalidate the page cache."""
    monkeypatch.setenv("TEST_API_KEY", "top-secret")
    generator, markdown_file = _generator(tmp_path, llms_txt_summary_max_input_chars=12)
    with patch(
        "sphinx_llm.summary.summarize_text",
        side_effect=[" First\nsummary. ", "Second summary."],
    ) as summarize:
        assert generator.get_page_description(markdown_file) == "First summary."
        markdown_file.write_text(
            "# Page\n\nComplete **Markdown** contents changed after prefix.",
            encoding="utf-8",
        )
        assert generator.get_page_description(markdown_file) == "Second summary."

    assert summarize.call_count == 2
    assert all(call.args[0] == "# Page\n\nComp" for call in summarize.call_args_list)
    cache_text = generator._summary_cache_path.read_text(encoding="utf-8")
    assert "top-secret" not in cache_text
    assert all(
        "top-secret" not in str(value) for value in vars(generator.app.config).values()
    )
    assert "top-secret" not in caplog.text


@pytest.mark.parametrize(
    ("setting", "changed"),
    [
        ("llms_txt_summary_provider", "other-provider"),
        ("llms_txt_summary_model", "other-model"),
        ("llms_txt_summary_base_url", "https://other.example/v1"),
        ("llms_txt_summary_max_input_chars", 100),
        ("llms_txt_summary_timeout", 15),
    ],
)
def test_generation_setting_changes_invalidate_cache(
    monkeypatch, tmp_path, setting, changed
):
    """Every generation parameter participates in the page fingerprint."""
    monkeypatch.setenv("TEST_API_KEY", "secret")
    generator, markdown_file = _generator(tmp_path)
    with patch(
        "sphinx_llm.summary.summarize_text",
        side_effect=["First summary.", "Second summary."],
    ) as summarize:
        assert generator.get_page_description(markdown_file) == "First summary."
        setattr(generator.app.config, setting, changed)
        if setting == "llms_txt_summary_provider":
            with pytest.raises(ExtensionError, match="provider"):
                generator.get_page_description(markdown_file)
            return
        assert generator.get_page_description(markdown_file) == "Second summary."
    assert summarize.call_count == 2


@pytest.mark.parametrize(
    "cache_content",
    ["not json", json.dumps({"version": 999, "summaries": {}})],
)
def test_corrupt_or_incompatible_cache_regenerates(
    monkeypatch, tmp_path, cache_content
):
    """Bad cache files recover without suppressing generation."""
    monkeypatch.setenv("TEST_API_KEY", "secret")
    generator, markdown_file = _generator(tmp_path)
    generator._summary_cache_path.parent.mkdir(parents=True)
    generator._summary_cache_path.write_text(cache_content, encoding="utf-8")
    with patch("sphinx_llm.summary.summarize_text", return_value="Summary.") as call:
        assert generator.get_page_description(markdown_file) == "Summary."
    call.assert_called_once()


def test_failed_cache_write_removes_temporary_file(monkeypatch, tmp_path):
    """An interrupted atomic write does not leave its temporary file behind."""
    generator, _ = _generator(tmp_path)
    generator._summary_cache_path.parent.mkdir(parents=True)
    with patch("sphinx_llm.txt.json.dump", side_effect=OSError("disk full")):
        with pytest.raises(OSError, match="disk full"):
            generator._save_summary_cache()
    temporary_files = generator._summary_cache_path.parent.glob(
        f".{generator._summary_cache_path.name}.*"
    )
    assert list(temporary_files) == []


def test_failed_cache_persistence_does_not_discard_summary(monkeypatch, tmp_path):
    """A valid provider response remains usable when its cache cannot be saved."""
    monkeypatch.setenv("TEST_API_KEY", "secret")
    generator, markdown_file = _generator(tmp_path)
    with (
        patch("sphinx_llm.summary.summarize_text", return_value="Summary."),
        patch("sphinx_llm.txt.logger.warning") as warning,
        patch.object(
            generator,
            "_save_summary_cache",
            side_effect=OSError("read-only filesystem"),
        ),
    ):
        assert generator.get_page_description(markdown_file) == "Summary."
    warning.assert_called_once()
    assert "summaries will be regenerated" in warning.call_args.args[0]


def test_provider_failure_is_redacted(monkeypatch, tmp_path):
    """Provider failures become clear ExtensionErrors without credential leakage."""
    monkeypatch.setenv("TEST_API_KEY", "top-secret")
    generator, markdown_file = _generator(tmp_path)
    with patch(
        "sphinx_llm.summary.summarize_text",
        side_effect=RuntimeError("request failed with top-secret"),
    ):
        with pytest.raises(ExtensionError, match="page") as error:
            generator.get_page_description(markdown_file)
    assert "top-secret" not in str(error.value)
    formatted = "".join(
        traceback.format_exception(
            type(error.value), error.value, error.value.__traceback__
        )
    )
    assert "top-secret" not in formatted


def test_unchanged_second_build_uses_cache_without_credentials(monkeypatch, tmp_path):
    """A cache hit does not import or contact the provider and needs no credential."""
    monkeypatch.setenv("TEST_API_KEY", "secret")
    generator, markdown_file = _generator(tmp_path)
    with patch("sphinx_llm.summary.summarize_text", return_value="Summary.") as call:
        assert generator.get_page_description(markdown_file) == "Summary."
    call.assert_called_once()

    monkeypatch.delenv("TEST_API_KEY")
    second, second_markdown_file = _generator(tmp_path)
    with patch("sphinx_llm.summary.summarize_text") as call:
        assert second.get_page_description(second_markdown_file) == "Summary."
    call.assert_not_called()


def test_api_key_rotation_does_not_invalidate_cache(monkeypatch, tmp_path):
    """The credential value is excluded from the cache fingerprint."""
    monkeypatch.setenv("TEST_API_KEY", "secret-one")
    generator, markdown_file = _generator(tmp_path)
    with patch("sphinx_llm.summary.summarize_text", return_value="Summary."):
        assert generator.get_page_description(markdown_file) == "Summary."

    monkeypatch.setenv("TEST_API_KEY", "secret-two")
    second, second_markdown_file = _generator(tmp_path)
    with patch("sphinx_llm.summary.summarize_text") as call:
        assert second.get_page_description(second_markdown_file) == "Summary."
    call.assert_not_called()


def test_missing_credential_errors_but_empty_name_opts_out(monkeypatch, tmp_path):
    """Named credentials are required; an empty name explicitly opts out."""
    monkeypatch.delenv("TEST_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-secret")
    generator, markdown_file = _generator(tmp_path)
    with pytest.raises(ExtensionError, match="API key"):
        generator.get_page_description(markdown_file)

    unauthenticated, unauthenticated_file = _generator(
        tmp_path / "local", llms_txt_summary_api_key_env=""
    )
    with patch("sphinx_llm.summary.summarize_text", return_value="Summary.") as call:
        assert unauthenticated.get_page_description(unauthenticated_file) == "Summary."
    assert call.call_args.kwargs["api_key_env"] == ""


def test_prompt_version_change_invalidates_cache(monkeypatch, tmp_path):
    """Prompt revisions regenerate cached summaries."""
    monkeypatch.setenv("TEST_API_KEY", "secret")
    generator, markdown_file = _generator(tmp_path)
    with patch(
        "sphinx_llm.summary.summarize_text",
        side_effect=["First summary.", "Second summary."],
    ) as summarize:
        assert generator.get_page_description(markdown_file) == "First summary."
        monkeypatch.setattr("sphinx_llm.summary.SUMMARY_PROMPT_VERSION", 999)
        assert generator.get_page_description(markdown_file) == "Second summary."
    assert summarize.call_count == 2


def test_changing_one_page_only_regenerates_that_page(monkeypatch, tmp_path):
    """Cache invalidation is page-granular."""
    monkeypatch.setenv("TEST_API_KEY", "secret")
    generator, first_file = _generator(tmp_path)
    second_file = tmp_path / "second.html.md"
    second_file.write_text("# Second\n\nSecond page contents.", encoding="utf-8")
    generator._docname_by_output_file[second_file] = "second"
    with patch(
        "sphinx_llm.summary.summarize_text",
        side_effect=["First page.", "Second page.", "Updated first page."],
    ) as summarize:
        assert generator.get_page_description(first_file) == "First page."
        assert generator.get_page_description(second_file) == "Second page."
        first_file.write_text("# Page\n\nChanged page contents.", encoding="utf-8")
        assert generator.get_page_description(first_file) == "Updated first page."
        assert generator.get_page_description(second_file) == "Second page."
    assert summarize.call_count == 3


def test_custom_cache_path_from_environment(monkeypatch, tmp_path):
    """A relative configured cache path is resolved from the config directory."""
    generator, _ = _generator(tmp_path)
    monkeypatch.setenv("SPHINX_LLM_SUMMARY_CACHE_PATH", "cache/summaries.json")
    assert generator._summary_cache_path == tmp_path / "cache" / "summaries.json"


def test_all_environment_options(monkeypatch, tmp_path):
    """Every public environment variable maps to its documented option."""
    values = {
        "SPHINX_LLM_SUMMARY_ENABLED": "yes",
        "SPHINX_LLM_SUMMARY_PROVIDER": "openai-compatible",
        "SPHINX_LLM_SUMMARY_MODEL": "env-model",
        "SPHINX_LLM_SUMMARY_BASE_URL": "https://env.example/v1",
        "SPHINX_LLM_SUMMARY_API_KEY_ENV": "ENV_KEY",
        "SPHINX_LLM_SUMMARY_MAX_INPUT_CHARS": "345",
        "SPHINX_LLM_SUMMARY_TIMEOUT": "12",
        "SPHINX_LLM_SUMMARY_CACHE_PATH": "env-cache.json",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    generator, _ = _generator(tmp_path)
    options = generator._get_summary_options()
    assert options.enabled is True
    assert options.provider == "openai-compatible"
    assert options.model == "env-model"
    assert options.base_url == "https://env.example/v1"
    assert options.api_key_env == "ENV_KEY"
    assert options.max_input_chars == 345
    assert options.timeout == 12
    assert options.cache_path == "env-cache.json"


def test_default_disabled_path_does_not_import_summary_module(monkeypatch, tmp_path):
    """Normal builds do not import provider code."""
    monkeypatch.delitem(sys.modules, "sphinx_llm.summary", raising=False)
    monkeypatch.delattr(sphinx_llm, "summary", raising=False)
    generator, markdown_file = _generator(tmp_path, llms_txt_summary_enabled=False)
    assert generator.get_page_description(markdown_file)
    assert "sphinx_llm.summary" not in sys.modules


def test_page_summary_disables_ambient_openai_defaults(monkeypatch, tmp_path):
    """Dedicated options never inherit shared OPENAI_* environment settings."""
    monkeypatch.setenv("TEST_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://ambient.example/v1")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "high")
    generator, markdown_file = _generator(tmp_path, llms_txt_summary_base_url="")
    with patch("sphinx_llm.summary.summarize_text", return_value="Summary.") as call:
        assert generator.get_page_description(markdown_file) == "Summary."
    assert call.call_args.kwargs["base_url"] == ""
    assert call.call_args.kwargs["reasoning_effort"] == "none"
    assert call.call_args.kwargs["use_environment_defaults"] is False


@pytest.mark.parametrize(
    ("error_type", "provider_message", "expected"),
    [
        (
            "MissingGenerationDependenciesError",
            "missing provider dependency",
            r"pip install sphinx-llm\[gen\]",
        ),
        (
            "MalformedSummaryResponseError",
            "bad provider response",
            "malformed or empty summary",
        ),
    ],
)
def test_known_safe_provider_errors_remain_actionable(
    monkeypatch, tmp_path, error_type, provider_message, expected
):
    """Safe setup/response errors survive redaction with useful guidance."""
    monkeypatch.setenv("TEST_API_KEY", "secret")
    generator, markdown_file = _generator(tmp_path)
    error_class = getattr(import_module("sphinx_llm.summary"), error_type)
    with patch(
        "sphinx_llm.summary.summarize_text",
        side_effect=error_class(provider_message),
    ):
        with pytest.raises(ExtensionError, match=expected):
            generator.get_page_description(markdown_file)


def test_page_summary_rejects_key_over_remote_plain_http(monkeypatch, tmp_path):
    """The page adapter preserves safe HTTPS guidance without leaking the key."""
    monkeypatch.setenv("TEST_API_KEY", "top-secret")
    generator, markdown_file = _generator(
        tmp_path, llms_txt_summary_base_url="http://models.example.com/v1"
    )
    with patch("openai.OpenAI") as mock_openai:
        with pytest.raises(ExtensionError, match="use HTTPS") as error:
            generator.get_page_description(markdown_file)
    mock_openai.assert_not_called()
    assert "top-secret" not in str(error.value)


@pytest.mark.parametrize(
    ("builder", "parallel"),
    [
        ("html", True),
        ("html", False),
        ("dirhtml", True),
        ("dirhtml", False),
    ],
)
def test_page_summaries_in_full_build_matrix(monkeypatch, builder, parallel):
    """Generated summaries work across supported builders and build modes."""
    monkeypatch.setenv("TEST_API_KEY", "secret")
    build = _build_sphinx(
        builder,
        {
            "llms_txt_build_parallel": parallel,
            "llms_txt_summary_enabled": True,
            "llms_txt_summary_model": "test-model",
            "llms_txt_summary_base_url": "https://example.com/v1",
            "llms_txt_summary_api_key_env": "TEST_API_KEY",
        },
    )
    try:
        with patch(
            "sphinx_llm.summary.summarize_text",
            return_value="Generated page summary.",
        ) as summarize:
            app, build_dir, _ = next(build)

        content = (build_dir / "llms.txt").read_text(encoding="utf-8")
        apples_line = next(
            line for line in content.splitlines() if "apples" in line.lower()
        )
        assert apples_line.endswith(": Generated page summary.")

        authored = _get_html_meta_description(app, _HTML_META_PAGE)
        meta_line = next(
            line for line in content.splitlines() if _HTML_META_PAGE in line
        )
        assert meta_line.endswith(f": {authored}")
        assert all(authored not in call.args[0] for call in summarize.call_args_list)
    finally:
        build.close()
