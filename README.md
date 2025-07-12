# sphinx-llm

The `sphinx-llm` package includes a collection of extensions for working with LLMs.

There are two categories of tools in this package:

- **Enabling LLMs and agents to consume your docs** - This is useful when you want your project to be well indexed and represented in LLMs when users ask about projects in your domain.
- **Leveraging LLMs to generate content dynamically during the Sphinx build** - This is useful for generating static content that gets baked into the documentation. It it not intended to provide an interactive chat service in your documentation.

## Installation

```console
pip install sphinx-llm

# For extensions that use LLMs to generate text
pip install sphinx-llm[gen]
```

## Extensions

### llms.txt Support

The `sphinx_llm.txt` extension automatically generates markdown files for consumption by LLMs following the [llms.txt](https://llmstxt.org/) standard alongside HTML files during the Sphinx build process.

The [llms.txt](https://llmstxt.org/) standard describes how you can provide documentation in a way that can be easily consumed by LLMs, either during model training or by agents at inference time when using tools that gather context from the web. The standard describes that your documentation sitemap should be provided in markdown in `llms.txt` and then the entire documentation should be provided in markdown via a single file called `llms-full.txt`. Additionally each individual page on your website should also have a markdown version of the page at the same URL with an additional `.md` extension.

To use the extension add it to your `conf.py`:

```python
# conf.py
# ...

extensions = [
    "sphinx_llm.txt",
]
```

When you build your documentation with `sphinx-build` (or `make html`), the extension will:

1. Find all HTML files generated in the output directory
2. Convert each HTML file to markdown format
3. Save the markdown files with the same name plus an extra `.md` extension
4. Concatenates all generated markdown into a single `llms-full.txt` file

For example, if your build generates:
- `_build/html/index.html`
- `_build/html/apples.html`

The extension will also create:
- `_build/html/index.html.md`
- `_build/html/apples.html.md`
- `_build/html/llms-full.txt`

Note: This extension only works with HTML builders (like `html` and `dirhtml`).

### Docref

The `sphinx_llm.docref` extension adds a directive for summarising and referencing other pages in your documentation.
Instead of just linking to a page the extension will generate a summary of the page being linked to and include that too.

To use this extension you need to have [ollama](https://github.com/ollama/ollama) running.

If you have a GPU then generation will be much faster, but it is optional. See [the GitHub Actions](.github/workflows/build-docs.yml) for an example of using it in CI.

![](docs/source/_static/images/pig-feeding-summary.png)

To use the extension add it to your `conf.py`.

```python
# conf.py
# ...

extensions = [
    "sphinx_llm.docref",
]
```

Then use the `docref` directive in your documents to reference other documents.

```rst
Testing page
============


.. docref:: apples
   
   Summary of apples page.
```

Then when you run `sphinx-build` (or `make html`) a summary will be generated and your source file will be updated too.

```rst
Testing page
============


.. docref:: apples
   :hash: 31ec12a54205539af3cde39b254ec766
   :model: llama3.2:3b
   
   Feeding apples to a friendly pig involves selecting ripe, pesticide-free apples, washing them thoroughly, cutting into manageable pieces, introducing them calmly, monitoring the pig's reaction, and cleaning up afterwards.
```

A hash of the referenced document is included to avoid generating summaries unnecessarily. But if the referenced page changes the summary will be regenerated.

You can also modify the summary if you need to clean up the language generated, and as long as the hash still matches the file it will be used.

## Building the docs

Try it out yourself by building the example documentation.

```console
uv run --dev sphinx-autobuild docs/source docs/build/html
```
