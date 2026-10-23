# sphinx-llm

[Sphinx](https://www.sphinx-doc.org/) extensions for LLM-friendly documentation
and static build-time content. Use either extension independently or combine them.

## Install and start

```console
pip install sphinx-llm
```

Enable an extension in your Sphinx `conf.py` and build normally:

```python
extensions = ["sphinx_llm.txt"]
```

```console
sphinx-build -b html path/to/your/docs path/to/your/build/html
```

For more information, check out the
[first build tutorial](https://sphinx-llm.readthedocs.io/en/latest/txt/tutorial.html).

## Publish LLM-friendly documentation

**sphinx_llm.txt** adds an llms.txt index and per-page Markdown alongside HTML,
with append/replace URL layouts, nested indexes, exclusions, discovery links
and optional concatenated full text. No model or API key is required.

For more information, check out the
[output reference](https://sphinx-llm.readthedocs.io/en/latest/txt/output-reference.html)
and [task guides](https://sphinx-llm.readthedocs.io/en/latest/txt/how-to/index.html).

## Render linked page summaries

**sphinx_llm.docref** renders a target page's title, a summary and a link as
static content. Author a summary per reference or reuse page metadata, and
customize the wording and styles without enabling TXT or calling a model.

For more information, check out the
[authored-reference tutorial](https://sphinx-llm.readthedocs.io/en/latest/docref/tutorial.html)
and [directive reference](https://sphinx-llm.readthedocs.io/en/latest/docref/directive-reference.html).

## Generate descriptions with a model

Both extensions can optionally generate summaries through an OpenAI-compatible
provider, with caching and docref provenance reports.
Install `sphinx-llm[gen]` and explicitly enable generation.

For more information, check out the
[provider guide](https://sphinx-llm.readthedocs.io/en/latest/docref/how-to/providers.html)
and [shared settings reference](https://sphinx-llm.readthedocs.io/en/latest/txt/configuration.html#shared-summary-settings).

## Project and contributions

For more information, check out the
[documentation](https://sphinx-llm.readthedocs.io/en/latest/),
[contributor guide](https://sphinx-llm.readthedocs.io/en/latest/project/contributing.html),
[release instructions](https://sphinx-llm.readthedocs.io/en/latest/project/releasing.html)
and [alternatives comparison](https://sphinx-llm.readthedocs.io/en/latest/project/alternatives.html).

Report problems in [GitHub issues](https://github.com/NVIDIA/sphinx-llm/issues).
Licensed under [Apache-2.0](LICENSE).
