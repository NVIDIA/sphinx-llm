# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path

from docutils.nodes import Text, admonition, inline, paragraph
from docutils.parsers.rst.directives.admonitions import BaseAdmonition
from sphinx.addnodes import pending_xref
from sphinx.application import Sphinx
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

from .summary import (
    DEFAULT_API_KEY_ENV,
    DEFAULT_MODEL,
    DEFAULT_MODEL_ENV,
    summarize_text,
    summary_fingerprint,
)
from .version import __version__

logger = logging.getLogger(__name__)


def _escape_rst_directives(summary: str) -> str:
    """Escape directive-like lines before persisting generated RST."""
    escaped_lines = []
    for line in summary.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(".. "):
            indentation = line[: len(line) - len(stripped)]
            line = f"{indentation}\\{stripped}"
        escaped_lines.append(line)
    return "\n".join(escaped_lines)


class Docref(BaseAdmonition, SphinxDirective):
    node_class = admonition
    required_arguments = 1
    option_spec = {"model": str, "hash": str}

    def run(self):
        # Get the document name from the directive arguments
        [doc_name] = self.arguments
        doc_title = "See also: "
        doc_title += (
            self.state.document.settings.env.app.builder.env.get_doctree(doc_name)
            .traverse(lambda n: n.tagname == "title")[0]
            .astext()
        )
        self.arguments = [doc_title]

        # Generate a summary of the document contents and replace the directive content with it
        hash, summary = self.generate_summary(doc_name)
        self.update_content(hash, summary)

        # Specify that this page should be rebuilt when the referenced document changes
        self.state.document.settings.env.note_dependency(doc_name)

        # Run the base admonition directive
        nodes = super().run()

        # Add a link to the document
        custom_xref = pending_xref(
            reftype="doc",
            refdomain="std",
            refexplicit=True,
            reftarget=doc_name,
            refdoc=self.env.docname,
            refwarn=True,
        )
        text_wrapper = inline()
        text_wrapper += Text("Read more >>")
        custom_xref += text_wrapper
        wrapper = paragraph()
        wrapper["classes"] = ["visit-link"]
        wrapper += custom_xref
        nodes[0] += wrapper
        return nodes

    def generate_summary(self, doc_name: str) -> tuple[str, str]:
        # Get the document contents
        doc_contents = self.state.document.settings.env.app.builder.env.get_doctree(
            doc_name
        ).astext()

        # Resolve every generation setting before checking the persisted cache.
        shared_options = getattr(self.config, "sphinx_llm_options", {})
        if "model" in self.options and self.options["model"]:
            model = self.options["model"]
        else:
            model = (
                shared_options.get("model")
                or os.environ.get(DEFAULT_MODEL_ENV, "")
                or DEFAULT_MODEL
            )
        base_url = shared_options.get("base_url", "") or os.environ.get(
            "OPENAI_BASE_URL", ""
        )
        api_key_env = shared_options.get("api_key_env") or DEFAULT_API_KEY_ENV

        # Include the prompt version and all endpoint settings in the cache key.
        doc_hash = summary_fingerprint(
            doc_contents,
            model,
            base_url=base_url,
            api_key_env=api_key_env,
        )
        if "hash" in self.options and self.options["hash"] == doc_hash:
            return doc_hash, "\n".join(self.content.data)
        if shared_options.get("warn_on_cache_miss", True):
            logger.warning(
                f"LLM summary is out of date for document '{doc_name}', regenerating summary"
            )

        doc_summary = summarize_text(
            doc_contents,
            model,
            base_url=base_url,
            api_key_env=api_key_env,
        )

        return doc_hash, doc_summary

    def update_content(self, hash: str, summary: str):
        summary = _escape_rst_directives(summary)
        self.content.data = summary.splitlines()

        # Update the source file with the new summary
        source_file = Path(self.state.document.current_source)
        # TODO add support for myst and other markdown formats
        if source_file.suffix != ".rst":
            raise ValueError(f"Source file {source_file} is not an RST file")
        source = source_file.read_text().splitlines()
        original_source = source.copy()
        start_line_idx = self.lineno - 1

        # Figure out which lines to replace and the indent level
        lines = [line for (_, line) in self.content.items]
        indent = len(source[lines[0]]) - len(source[lines[0]].lstrip())

        # Remove original lines from the source
        for line in reversed(lines):
            source.pop(line)

        # Insert the summary into the source
        for line in reversed(summary.splitlines()):
            source.insert(lines[0], " " * indent + line)

        # Update the hash (rst specific for now)
        for i, line in enumerate(self.content.parent.data):
            if ":hash:" in line:
                source[start_line_idx + i] = " " * indent + f":hash: {hash}"
                break
        else:
            source.insert(start_line_idx + 1, " " * indent + f":hash: {hash}")

        # Only write if we are making changes
        if source != original_source:
            source_file.write_text("\n".join(source))


def setup(app: Sphinx) -> dict:
    app.add_directive("docref", Docref)
    app.add_config_value("sphinx_llm_options", {}, "env")

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
