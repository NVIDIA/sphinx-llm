# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "sphinx-llm"
copyright = "2024, Jacob Tomlinson"
author = "Jacob Tomlinson"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx_llm.docref",
    "sphinx_llm.txt",
]

sphinx_llm_options = {
    "model": "llama3.2:3b",
}
llms_txt_description = """A collection of Sphinx extensions for working with LLMs in your documentation.
This includes:
- Generating rich `llms.txt` and `llms-full.txt` markdown context files and individual page markdown context files.
- A directive for summarising and referencing other pages in your documentation.
"""
llms_txt_build_parallel = False

templates_path = ["_templates"]
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "alabaster"
html_static_path = ["_static"]
