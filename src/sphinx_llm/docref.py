# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Sphinx-native generated summaries for the :rst:dir:`docref` directive."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from docutils import nodes
from docutils.nodes import Text, admonition, paragraph
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.errors import ExtensionError, NoUri
from sphinx.util import docname_join, logging
from sphinx.util.docutils import SphinxDirective

from . import summary as summary_client
from .txt import MarkdownGenerator, SummaryOptions
from .version import __version__

logger = logging.getLogger(__name__)

REPORT_FILENAME = "sphinx-llm-summaries.json"
ENV_VERSION = 2

DEFAULT_TITLE_PREFIX = "See also:"
DEFAULT_VISIT_LINK_TEXT = "Read more >>"
DEFAULT_VISIT_LINK_CLASS = "visit-link"

REQUESTS_ATTRIBUTE = "sphinx_llm_summary_requests"
CACHE_ATTRIBUTE = "sphinx_llm_summary_cache"
EFFECTIVE_ATTRIBUTE = "sphinx_llm_effective_summaries"

LEGACY_STYLING_NAMES = {
    "style_title_prefix": "title_prefix",
    "style_visit_link_text": "visit_link_text",
    "style_visit_link_class": "visit_link_class",
}


class DocrefNode(nodes.General, nodes.Element):
    """A reference awaiting summary selection during the Sphinx write phase."""


def _findall(node: nodes.Node, condition):
    findall = getattr(node, "findall", None)
    if findall is not None:
        return findall(condition)
    return node.traverse(condition)


def _environment_mapping(env, attribute: str) -> dict:
    mapping = getattr(env, attribute, None)
    if mapping is None:
        mapping = {}
        setattr(env, attribute, mapping)
    return mapping


def _requests(env) -> dict[str, dict[str, Any]]:
    return _environment_mapping(env, REQUESTS_ATTRIBUTE)


def _cache(env) -> dict[str, dict[str, Any]]:
    return _environment_mapping(env, CACHE_ATTRIBUTE)


def _effective(env) -> dict[str, dict[str, Any]]:
    return _environment_mapping(env, EFFECTIVE_ATTRIBUTE)


def _summary_settings(
    generator: MarkdownGenerator, request: dict[str, Any]
) -> SummaryOptions:
    """Resolve shared options plus a directive-specific model override."""
    options = generator._get_summary_options()
    return replace(options, model=request["model"]) if request.get("model") else options


def _stable_hash(value: dict[str, Any]) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def _summary_id(target: str, settings: SummaryOptions) -> str:
    identity = asdict(settings)
    identity.pop("enabled")
    identity.pop("cache_path")
    return _stable_hash({"target": target, "settings": identity})


def _fingerprint(target: str, contents: str, settings: SummaryOptions) -> str:
    return MarkdownGenerator._summary_fingerprint(
        contents,
        settings,
        summary_client.SUMMARY_PROMPT_VERSION,
        summary_client.DEFAULT_REASONING_EFFORT,
    )


def generate_summary(settings: SummaryOptions, contents: str) -> str:
    """Generate a summary with the shared bounded and secure provider options."""
    if not settings.model:
        raise ExtensionError(
            "No summary model is configured; set llms_txt_summary_model "
            "or SPHINX_LLM_SUMMARY_MODEL"
        )
    if settings.api_key_env and not os.environ.get(settings.api_key_env):
        raise ExtensionError(
            "No summary API key is configured; set the environment variable "
            f"named by llms_txt_summary_api_key_env ({settings.api_key_env!r})"
        )
    try:
        return summary_client.summarize_text(
            contents[: settings.max_input_chars],
            settings.model,
            base_url=settings.base_url,
            api_key_env=settings.api_key_env,
            reasoning_effort=summary_client.DEFAULT_REASONING_EFFORT,
            timeout=settings.timeout,
            use_environment_defaults=False,
            allow_insecure_auth=settings.allow_insecure_auth,
        )
    except summary_client.MissingGenerationDependenciesError:
        raise ExtensionError(
            "LLM summarization requires the optional generation dependencies. "
            "Install them with 'pip install sphinx-llm[gen]'."
        ) from None
    except summary_client.MalformedSummaryResponseError:
        raise ExtensionError(
            "The OpenAI-compatible endpoint returned a malformed or empty summary"
        ) from None
    except summary_client.InsecureEndpointError:
        raise ExtensionError(
            "Refusing to send the summary API key to a non-loopback endpoint "
            "over plain HTTP; use HTTPS, a loopback URL, or explicitly allow "
            "insecure authentication"
        ) from None
    except Exception:
        raise ExtensionError(
            "Failed to generate a docref summary; "
            "check the provider configuration and credentials"
        ) from None


class Docref(SphinxDirective):
    """Create a deferred cross-reference with an authored or generated summary."""

    required_arguments = 1
    has_content = True
    option_spec = {
        "model": directives.unchanged,
        "hash": directives.unchanged,
        "style-title-prefix": directives.unchanged,
        "style-visit-link-text": directives.unchanged,
        "style-visit-link-class": directives.unchanged,
        "title-prefix": directives.unchanged,
        "visit-link-text": directives.unchanged,
        "visit-link-class": directives.unchanged,
    }

    def run(self) -> list[nodes.Node]:
        target = docname_join(self.env.docname, self.arguments[0].strip())
        pending = DocrefNode()
        pending.source, pending.line = self.state_machine.get_source_and_line(
            self.lineno
        )
        if self.content:
            self.state.nested_parse(self.content, self.content_offset, pending)

        legacy_hash = self.options.get("hash", "").strip()
        if legacy_hash:
            logger.warning(
                ":hash: is deprecated; remove the body to use automatic generation, "
                "or remove :hash: to keep the body as a permanent manual override",
                location=(pending.source, pending.line),
                type="sphinx_llm",
                subtype="legacy_hash",
            )

        for styling_name, legacy_name in LEGACY_STYLING_NAMES.items():
            legacy_option = legacy_name.replace("_", "-")
            canonical_option = styling_name.replace("style_", "style-").replace(
                "_", "-"
            )
            if legacy_option in self.options and canonical_option in self.options:
                logger.warning(
                    ":%s: is deprecated and ignored because :%s: is set",
                    legacy_option,
                    canonical_option,
                    location=(pending.source, pending.line),
                    type="sphinx_llm",
                    subtype="deprecated_docref_styling",
                )

        request_id = f"{self.env.docname}:{self.env.new_serialno('docref')}"
        body = pending.astext().strip()
        request = {
            "request_id": request_id,
            "source_docname": self.env.docname,
            "source": str(self.env.doc2path(self.env.docname, base=False)),
            "line": pending.line or self.lineno,
            "target": target,
            "model": self.options.get("model", "").strip(),
            "body": body,
            "manual_override": bool(body) and not legacy_hash,
            "legacy_hash": legacy_hash,
            "style_title_prefix": self.options.get("style-title-prefix"),
            "style_visit_link_text": self.options.get("style-visit-link-text"),
            "style_visit_link_class": self.options.get("style-visit-link-class"),
            "title_prefix": self.options.get("title-prefix"),
            "visit_link_text": self.options.get("visit-link-text"),
            "visit_link_class": self.options.get("visit-link-class"),
        }
        _requests(self.env)[request_id] = request
        pending["request_id"] = request_id

        # A change to the target must also rewrite each consuming document.
        self.env.note_dependency(self.env.doc2path(target, base=False))
        return [pending]


def _target_data(env, target: str) -> tuple[nodes.document, str]:
    try:
        doctree = env.get_doctree(target)
    except Exception as exc:
        raise ExtensionError(
            f"Unable to load document referenced by docref: {target!r}",
            exc,
            "sphinx-llm",
        ) from exc
    return doctree, doctree.astext().strip()


def _html_meta_description(doctree: nodes.document) -> str:
    meta_type = getattr(nodes, "meta", lambda node: node.tagname == "meta")
    for node in _findall(doctree, meta_type):
        if node.get("name") == "description" and node.get("content"):
            return str(node["content"]).strip()
    return ""


def _content_fallback(doctree: nodes.document, target: str) -> str:
    for node in _findall(doctree, nodes.paragraph):
        text = node.astext().strip()
        if text:
            return f"{text[:100]}..." if len(text) > 100 else text
    return f"See {target}."


def _generated_record(
    *,
    target: str,
    summary: str,
    fingerprint: str,
    settings: SummaryOptions,
) -> dict[str, Any]:
    return {
        "target": target,
        "summary": summary,
        "fingerprint": fingerprint,
        "provider": settings.provider,
        "model": settings.model,
        "prompt_version": summary_client.SUMMARY_PROMPT_VERSION,
        "prompt_fingerprint": _stable_hash(
            {
                "system": summary_client.SYSTEM_PROMPT,
                "summary": summary_client.SUMMARY_PROMPT,
            }
        ),
        "generation_settings": {
            "reasoning_effort": summary_client.DEFAULT_REASONING_EFFORT,
            "temperature": summary_client.SUMMARY_TEMPERATURE,
        },
    }


def _effective_generated(cache_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "target": cache_record["target"],
        "summary": cache_record["summary"],
        "origin": "generated",
        "fingerprint": cache_record["fingerprint"],
        "provider": cache_record["provider"],
        "model": cache_record["model"],
    }


def _legacy_seed(
    requests: list[dict[str, Any]],
    *,
    target: str,
    contents: str,
    fingerprint: str,
    settings: SummaryOptions,
) -> dict[str, Any] | None:
    legacy_hashes = {
        hashlib.md5(contents.encode()).hexdigest(),
        summary_client.summary_fingerprint(
            contents,
            settings.model,
            base_url=settings.base_url,
            api_key_env=settings.api_key_env,
            reasoning_effort=summary_client.DEFAULT_REASONING_EFFORT,
        ),
    }
    for request in requests:
        if request["legacy_hash"] in legacy_hashes and request["body"].strip():
            return _generated_record(
                target=target,
                summary=request["body"].strip(),
                fingerprint=fingerprint,
                settings=settings,
            )
    return None


def update_summaries(app: Sphinx, env) -> None:
    """Choose effective summaries and generate each missing cache entry once."""
    requests = _requests(env)
    cache = _cache(env)
    generator = MarkdownGenerator(app)
    shared_cache = generator._load_summary_cache()
    for key, record in shared_cache.items():
        if key.startswith("docref:"):
            cache.setdefault(key.removeprefix("docref:"), record)
    cache_changed = False
    effective: dict[str, dict[str, Any]] = {}
    target_data: dict[str, tuple[nodes.document, str]] = {}
    automatic: dict[str, list[dict[str, Any]]] = {}
    group_details: dict[str, tuple[str, str, SummaryOptions]] = {}

    for request_id, request in sorted(requests.items()):
        target = request["target"]
        if target not in target_data:
            try:
                target_data[target] = _target_data(env, target)
            except ExtensionError:
                logger.warning(
                    "Unable to load document referenced by docref: %r; "
                    "using a local fallback",
                    target,
                    location=(request["source"], request["line"]),
                    type="sphinx_llm",
                    subtype="missing_docref_target",
                )
                effective[request_id] = {
                    "target": target,
                    "summary": f"See {target}.",
                    "origin": "fallback",
                }
                continue
        doctree, contents = target_data[target]

        if request["manual_override"]:
            effective[request_id] = {
                "target": target,
                "summary": request["body"],
                "origin": "directive",
            }
            continue

        meta_description = _html_meta_description(doctree)
        if meta_description:
            effective[request_id] = {
                "target": target,
                "summary": meta_description,
                "origin": "html_meta",
            }
            continue

        settings = _summary_settings(generator, request)
        summary_id = _summary_id(target, settings)
        automatic.setdefault(summary_id, []).append(request)
        group_details[summary_id] = (target, contents, settings)

    for summary_id, grouped_requests in sorted(automatic.items()):
        target, contents, settings = group_details[summary_id]
        fingerprint = _fingerprint(target, contents, settings)
        cache_record = cache.get(summary_id)
        if not cache_record or cache_record.get("fingerprint") != fingerprint:
            cache_record = _legacy_seed(
                grouped_requests,
                target=target,
                contents=contents,
                fingerprint=fingerprint,
                settings=settings,
            )
            if cache_record is None and settings.enabled:
                logger.info(
                    "Generating summary for document %r with %s/%s",
                    target,
                    settings.provider,
                    settings.model,
                )
                cache_record = _generated_record(
                    target=target,
                    summary=generate_summary(settings, contents),
                    fingerprint=fingerprint,
                    settings=settings,
                )
            if cache_record is not None:
                cache[summary_id] = cache_record
                shared_cache[f"docref:{summary_id}"] = cache_record
                cache_changed = True

        shared_key = f"docref:{summary_id}"
        if (
            cache_record
            and cache_record.get("fingerprint") == fingerprint
            and shared_cache.get(shared_key) != cache_record
        ):
            shared_cache[shared_key] = cache_record
            cache_changed = True

        for request in grouped_requests:
            if cache_record and cache_record.get("fingerprint") == fingerprint:
                effective[request["request_id"]] = _effective_generated(cache_record)
            else:
                effective[request["request_id"]] = {
                    "target": target,
                    "summary": _content_fallback(target_data[target][0], target),
                    "origin": "fallback",
                }

    active_ids = set(automatic)
    for stale_id in set(cache) - active_ids:
        cache.pop(stale_id, None)
    for key in list(shared_cache):
        if key.startswith("docref:") and key.removeprefix("docref:") not in active_ids:
            shared_cache.pop(key)
            cache_changed = True

    if cache_changed:
        try:
            generator._save_summary_cache()
        except OSError as error:
            logger.warning(
                "Could not persist the shared page-summary cache; "
                "summaries will be regenerated on the next clean build: %s",
                error,
            )
    setattr(env, EFFECTIVE_ATTRIBUTE, effective)


def _clear_sphinx_doctree_cache(env, docnames) -> None:
    """Discard stale Sphinx 6 doctree bytes for documents being reread."""
    pickled_cache = getattr(env, "_pickled_doctree_cache", {})
    for docname in docnames:
        pickled_cache.pop(docname, None)


def purge_docref_data(app: Sphinx, env, docname: str) -> None:
    """Remove request and resolution data owned by a source document."""
    _clear_sphinx_doctree_cache(env, [docname])
    requests = _requests(env)
    request_ids = {
        request_id
        for request_id, request in requests.items()
        if request["source_docname"] == docname
    }
    for request_id in request_ids:
        requests.pop(request_id, None)
        _effective(env).pop(request_id, None)


def merge_docref_data(app: Sphinx, env, docnames, other) -> None:
    """Merge requests collected by parallel Sphinx reader processes."""
    _clear_sphinx_doctree_cache(env, docnames)
    requests = _requests(env)
    for request_id, request in _requests(other).items():
        if request["source_docname"] in docnames:
            requests[request_id] = request


def _target_title(env, target: str) -> str:
    title = getattr(env, "titles", {}).get(target)
    if title is not None:
        text = title.astext().strip()
        if text:
            return text
    return target


def _link_node(
    app: Sphinx,
    from_docname: str,
    target: str,
    *,
    text: str = DEFAULT_VISIT_LINK_TEXT,
    css_class: str = DEFAULT_VISIT_LINK_CLASS,
) -> paragraph | None:
    try:
        refuri = app.builder.get_relative_uri(from_docname, target)
    except NoUri:
        return None
    reference = nodes.reference("", "", Text(text), refuri=refuri)
    reference["internal"] = True
    wrapper = paragraph()
    wrapper["classes"] = css_class.split()
    wrapper += reference
    return wrapper


def _styling_value(app: Sphinx, request: dict[str, Any], name: str) -> str:
    """Resolve canonical styling values, preserving deprecated aliases."""
    value = request.get(name)
    legacy_name = LEGACY_STYLING_NAMES[name]
    legacy_value = request.get(legacy_name)
    if value is not None:
        return value
    if legacy_value is not None:
        logger.warning(
            ":%s: is deprecated; use :%s: instead",
            legacy_name.replace("_", "-"),
            name.replace("style_", "style-").replace("_", "-"),
            type="sphinx_llm",
            subtype="deprecated_docref_styling",
        )
        return legacy_value

    config_name = f"llms_txt_docref_{name}"
    legacy_config_name = f"llms_txt_docref_{legacy_name}"
    raw_config = getattr(app.config, "_raw_config", {})
    overrides = getattr(app.config, "overrides", {})
    canonical_is_set = config_name in raw_config or config_name in overrides
    legacy_is_set = legacy_config_name in raw_config or legacy_config_name in overrides
    if legacy_is_set:
        logger.warning(
            "%s is deprecated; use %s instead",
            legacy_config_name,
            config_name,
            type="sphinx_llm",
            subtype="deprecated_docref_styling",
        )
        if not canonical_is_set:
            return getattr(app.config, legacy_config_name)
    return getattr(app.config, config_name)


def resolve_docrefs(app: Sphinx, doctree: nodes.document, docname: str) -> None:
    """Replace pending docref nodes with their effective summaries and links."""
    requests = _requests(app.env)
    effective = _effective(app.env)
    for pending in list(_findall(doctree, DocrefNode)):
        request_id = pending["request_id"]
        request = requests[request_id]
        selected = effective[request_id]
        target = request["target"]
        title_prefix = _styling_value(app, request, "style_title_prefix")
        target_title = _target_title(app.env, target)
        title_text = f"{title_prefix} {target_title}" if title_prefix else target_title

        rendered = admonition()
        rendered.source = pending.source
        rendered.line = pending.line
        rendered["classes"] = [f"admonition-{nodes.make_id(title_text)}"]
        rendered += nodes.title("", Text(title_text))
        if selected["origin"] == "directive":
            for child in pending.children:
                rendered += child.deepcopy()
        else:
            rendered += paragraph("", Text(selected["summary"]))
        link = _link_node(
            app,
            docname,
            target,
            text=_styling_value(app, request, "style_visit_link_text"),
            css_class=_styling_value(app, request, "style_visit_link_class"),
        )
        if link is not None:
            rendered += link
        pending.replace_self(rendered)


def _report_summaries(env) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    effective = _effective(env)
    for request_id, request in sorted(_requests(env).items()):
        selected = effective.get(request_id)
        if selected is None:
            continue
        entry = dict(selected)
        identity = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        report_entry = grouped.setdefault(identity, {**entry, "consumers": []})
        report_entry["consumers"].append(
            {
                "docname": request["source_docname"],
                "source": request["source"],
                "line": request["line"],
            }
        )

    summaries = list(grouped.values())
    for summary in summaries:
        summary["consumers"].sort(
            key=lambda consumer: (
                consumer["docname"],
                consumer["source"],
                consumer["line"],
            )
        )
    summaries.sort(
        key=lambda summary: (
            summary["target"],
            summary["origin"],
            summary["summary"],
        )
    )
    return summaries


def write_summary_report(app: Sphinx, exception: Exception | None) -> None:
    """Write the credential-free summary provenance artifact."""
    if exception is not None:
        return
    report_path = Path(app.outdir) / REPORT_FILENAME
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {"version": 1, "summaries": _report_summaries(app.env)}
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def setup(app: Sphinx) -> dict[str, Any]:
    app.setup_extension("sphinx_llm.summary")
    app.add_node(DocrefNode)
    app.add_directive("docref", Docref)

    # Keep the old dictionary registered for legacy configuration compatibility.
    app.add_config_value("sphinx_llm_options", {}, "env")
    app.add_config_value(
        "llms_txt_docref_style_title_prefix", DEFAULT_TITLE_PREFIX, "env"
    )
    app.add_config_value(
        "llms_txt_docref_style_visit_link_text", DEFAULT_VISIT_LINK_TEXT, "env"
    )
    app.add_config_value(
        "llms_txt_docref_style_visit_link_class", DEFAULT_VISIT_LINK_CLASS, "env"
    )
    app.add_config_value("llms_txt_docref_title_prefix", None, "env")
    app.add_config_value("llms_txt_docref_visit_link_text", None, "env")
    app.add_config_value("llms_txt_docref_visit_link_class", None, "env")

    app.connect("env-purge-doc", purge_docref_data)
    app.connect("env-merge-info", merge_docref_data)
    app.connect("env-updated", update_summaries)
    app.connect("doctree-resolved", resolve_docrefs)
    app.connect("build-finished", write_summary_report)

    return {
        "version": __version__,
        "env_version": ENV_VERSION,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
