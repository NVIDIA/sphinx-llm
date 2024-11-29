import os
import hashlib
from pathlib import Path

from docutils.nodes import Text, admonition, inline, paragraph
from docutils.parsers.rst.directives.admonitions import BaseAdmonition
from sphinx.addnodes import pending_xref
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective
from sphinx.util import logging

logger = logging.getLogger(__name__)

import ollama
from langchain_ollama import ChatOllama

DEFAULT_MODEL = "llama3.2:3b"
SYSTEM_PROMPT = "Keep responses concise and focused, avoiding unnecessary elaboration or additional context unless explicitly requested. Do not use bullet points, lists, or nested structures unless specifically asked. If a response requires further detail, prioritize the most relevant information and conclude promptly. Avoid apologies or mentions of limitations; simply deliver the most direct and straightforward answer."
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

class Docref(BaseAdmonition, SphinxDirective):
    node_class = admonition
    required_arguments = 1
    option_spec = {"model": str}    

    def run(self):
        # Get the document name from the directive arguments
        [doc_name] = self.arguments
        doc_title = "See also: "
        doc_title += self.state.document.settings.env.app.builder.env.get_doctree(doc_name).traverse(lambda n: n.tagname == "title")[0].astext()
        self.arguments = [doc_title]

        # Generate a summary of the document contents and replace the directive content with it
        summary = self.generate_summary(doc_name)
        self.content.data = [summary]

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
        doc_contents = self.state.document.settings.env.app.builder.env.get_doctree(doc_name).astext()

        # Set up cache
        env = self.state.document.settings.env
        if not hasattr(env, "sphinx_llm_cache"):
            env.sphinx_llm_cache = {}

        # Check for a summary in the build cache
        doc_hash = hashlib.md5(doc_contents.encode()).hexdigest()
        if doc_hash in env.sphinx_llm_cache:
            return env.sphinx_llm_cache[doc_hash]

        # Generate a summary using the LLM
        if "model" in self.options and self.options["model"]:
            model = self.options["model"]
        elif hasattr(env.app.config, "sphinx_llm_options"):
            model = env.app.config.sphinx_llm_options.get("model", DEFAULT_MODEL)
        else:
            model = DEFAULT_MODEL
        self.ensure_model(model)
        llm_client = ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=model,
            temperature=0,
        )
        doc_summary = llm_client.invoke([("system", SYSTEM_PROMPT), ("human", doc_contents + "\n\nHere's a concise one-sentence summary of the above:")]).content

        # Cache the summary and return it
        env.sphinx_llm_cache[doc_hash] = doc_summary
        return doc_summary
    
    def ensure_model(self, model: str):
        # Check if the model is already loaded
        ollama_client = ollama.Client(host=OLLAMA_BASE_URL)
        try:
            ollama_client.show(model)
            return
        except ollama.ResponseError:
            logger.info(f"Model {model} not found, loading...")
            ollama_client.pull(model)
            logger.info(f"Pulled model {model}")



def setup(app: Sphinx) -> dict:
    app.add_directive("docref", Docref)
    app.add_config_value('sphinx_llm_options', {}, 'env')

    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
