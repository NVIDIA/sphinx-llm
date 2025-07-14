import hashlib
import os
from pathlib import Path

import ollama
from docutils.nodes import Text, admonition, inline, paragraph
from docutils.parsers.rst.directives.admonitions import BaseAdmonition
from langchain_ollama import ChatOllama
from sphinx.addnodes import pending_xref
from sphinx.application import Sphinx
from sphinx.errors import ExtensionError
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

from .version import __version__

logger = logging.getLogger(__name__)
DEFAULT_MODEL = "llama3.2:3b"
SYSTEM_PROMPT = "Keep responses concise and focused, avoiding unnecessary elaboration or additional context unless explicitly requested. Do not use bullet points, lists, or nested structures unless specifically asked. If a response requires further detail, prioritize the most relevant information and conclude promptly. Avoid apologies or mentions of limitations; simply deliver the most direct and straightforward answer."
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


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

    def generate_summary(self, doc_name: str) -> str:
        # Get the document contents
        doc_contents = self.state.document.settings.env.app.builder.env.get_doctree(
            doc_name
        ).astext()

        # Check the cached summary
        doc_hash = hashlib.md5(doc_contents.encode()).hexdigest()
        if "hash" in self.options and self.options["hash"] == doc_hash:
            return doc_hash, "\n".join(self.content.data)
        if hasattr(
            self.config, "sphinx_llm_options"
        ) and self.config.sphinx_llm_options.get("warn_on_cache_miss", True):
            logger.warning(
                f"LLM summary is out of date for document '{doc_name}', regenerating summary"
            )

        # Generate a summary using the LLM
        if "model" in self.options and self.options["model"]:
            model = self.options["model"]
        elif hasattr(self.config, "sphinx_llm_options"):
            model = self.config.sphinx_llm_options.get("model", DEFAULT_MODEL)
        else:
            model = DEFAULT_MODEL
        self.ensure_model(model)
        llm_client = ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=model,
            temperature=0,
        )
        doc_summary = llm_client.invoke(
            [
                ("system", SYSTEM_PROMPT),
                (
                    "human",
                    doc_contents
                    + "\n\nHere's a concise one-sentence summary of the above:",
                ),
            ]
        ).content

        return doc_hash, doc_summary

    def ensure_model(self, model: str):
        # Check if the model is already loaded
        ollama_client = ollama.Client(host=OLLAMA_BASE_URL)
        try:
            ollama_client.ps()
            try:
                ollama_client.show(model)
                return
            except ollama.ResponseError:
                logger.info(f"Model {model} not found, loading...")
                ollama_client.pull(model)
                logger.info(f"Pulled model {model}")
        except Exception as e:
            raise ExtensionError(
                f"Failed to connect to ollama at {OLLAMA_BASE_URL}", e, "sphinx-llm"
            ) from e

    def update_content(self, hash: str, summary: str):
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
