# sphinx-llm

The `sphinx-llm` package includes a collection of
[Sphinx](https://www.sphinx-doc.org/) extensions for working with LLMs.

There are two categories of tools in this package:

- **Enabling LLMs and agents to consume your docs** - Produces additional build
  output for consumption by LLMs and agents. This is useful when you want your
  project to be well indexed and represented in LLMs when users ask about
  projects in your domain.
- **Leveraging LLMs to generate content dynamically during the Sphinx build** -
  Uses LLMs to generate content as part of the build process. This is useful
  for generating static content that gets baked into the documentation. It is
  not intended to provide an interactive chat service in your documentation.

## Installation

```console
pip install sphinx-llm

# For extensions that use LLMs to generate text
pip install sphinx-llm[gen]
```

## Extensions

### llms.txt Support

The `sphinx_llm.txt` extension automatically generates markdown files for
consumption by LLMs following the [llms.txt](https://llmstxt.org/) standard
alongside HTML files during the Sphinx build process.

The [llms.txt](https://llmstxt.org/) standard describes how you can provide
documentation in a way that can be easily consumed by LLMs, either during
model training or by agents at inference time when using tools that gather
context from the web. The standard describes that your documentation sitemap
should be provided in markdown in `llms.txt` and then the entire documentation
should be provided in markdown via a single file called `llms-full.txt`.
Additionally each individual page on your website should also have a markdown
version of the page at the same URL with an additional `.md` extension.

To use the extension add it to your `conf.py`:

```python
# conf.py
# ...

extensions = [
    "sphinx_llm.txt",
]
```

When you build your documentation with `sphinx-build` (or `make html`), the
extension will:

1. Builds your documentation as usual
2. Also builds your documentation with the
   [markdown builder](https://pypi.org/project/sphinx-markdown-builder/)
3. Merges the build outputs together
   - The markdown files will have the same as the HTML name plus an extra
     `.md` extension
4. Generates an index file for all the markdown files named `llms.txt`
5. Concatenates all generated markdown into a single `llms-full.txt` file

For example, if your build with the `html` builder generates:

- `_build/html/index.html`
- `_build/html/apples.html`

The extension will also create:

- `_build/html/llms.txt`
- `_build/html/llms-full.txt`
- `_build/html/index.html.md`
- `_build/html/apples.html.md`

With the `dirhtml` builder, which creates URLs like `/apples/` instead of
`/apples.html`, the extension generates markdown files in both the file-suffix
format (`page/index.html.md`) and the URL-suffix format (`page.md`) by default:

- `_build/dirhtml/llms.txt`
- `_build/dirhtml/llms-full.txt`
- `_build/dirhtml/index.html.md`
- `_build/dirhtml/apples/index.html.md` (file-suffix)
- `_build/dirhtml/apples.md` (URL-suffix, matches Claude docs behavior like
  `https://platform.claude.com/docs/overview.md`)

You can control which format(s) are generated using the `llms_txt_suffix_mode`
configuration option:

- `"auto"` (default): For `dirhtml`, generates both file-suffix and URL-suffix
  formats; for `html`, generates the standard `.html.md` format
- `"file-suffix"`: For `dirhtml`, only generates `page/index.html.md`; for
  `html`, generates the standard `.html.md` format
- `"url-suffix"`: For `dirhtml`, only generates `page.md`; for `html`,
  generates the standard `.html.md` format
- `"replace"`: Replaces the `.html` extension with `.md` in the HTML output
  path. For `html` builder: `page.html` → `page.md`. For `dirhtml` builder:
  `page/index.html` → `page/index.md`

> [!NOTE]
> This extension only works with HTML builders (like `html` and `dirhtml`).

#### Configuration

Supported `conf.py` configuration options for `sphinx_llm.txt`.

<!-- markdownlint-disable MD013 -->
| **Name** | **Description** | **Type** | **Default** |
| --- | --- | --- | --- |
| `llms_txt_description` | Override the project description set in `llms.txt` | `str` | Uses the project description from `pyproject.toml` by default |
| `llms_txt_build_parallel` | Build markdown files in parallel to the HTML files. | `bool` | `True` |
| `llms_txt_suffix_mode` | Suffix mode for generated markdown files. Options: `"auto"` (default behavior for each builder), `"file-suffix"` (spec-compliant format), `"url-suffix"` (URL-style format), or `"replace"` (replaces `.html` with `.md`). Note: `"both"` is deprecated but still supported (treated as `"auto"`). | `str` | `"auto"` |
| `llms_txt_full_build` | Whether to generate the `llms-full.txt` file. Set to `False` to disable generation, which is useful for large documentation sites where the concatenated file would be too large. | `bool` | `True` |
<!-- markdownlint-enable MD013 -->

### Docref

The `sphinx_llm.docref` extension adds a directive for summarising and
referencing other pages in your documentation. Instead of just linking to a
page the extension will generate a summary of the page being linked to and
include that too.

To use this extension you need to have [ollama](https://github.com/ollama/ollama)
running.

If you have a GPU then generation will be much faster, but it is optional. See
[the GitHub Actions](.github/workflows/build-docs.yml) for an example of using
it in CI.

![Docref summary example](docs/source/_static/images/pig-feeding-summary.png)

To use the extension add it to your `conf.py`.

```python
# conf.py
# ...

extensions = [
    "sphinx_llm.docref",
]
```

Then use the `docref` directive in your documents to reference other
documents.

```rst
Testing page
============


.. docref:: apples

   Summary of apples page.
```

Then when you run `sphinx-build` (or `make html`) a summary will be generated
and your source file will be updated too.

```rst
Testing page
============


.. docref:: apples
   :hash: 31ec12a54205539af3cde39b254ec766
   :model: llama3.2:3b

   Feeding apples to a friendly pig involves selecting ripe, pesticide-free
   apples, washing them thoroughly, cutting into manageable pieces,
   introducing them calmly, monitoring the pig's reaction, and cleaning up
   afterwards.
```

A hash of the referenced document is included to avoid generating summaries
unnecessarily. But if the referenced page changes the summary will be
regenerated.

You can also modify the summary if you need to clean up the language
generated, and as long as the hash still matches the file it will be used.

## Building the docs

Try it out yourself by building the example documentation.

```console
uv run --dev sphinx-autobuild docs/source docs/build/html
```

## Alternatives

There are other projects that solve this same problem, that's the wonderful
nature of open source software. This section compares the various approaches
each project has taken.

These comparisons have been put together with the best of intentions and
involvement from the maintainers of all projects compared here, but we
acknowledge they are highly subjective. If you spot any information on this
page that you believe to be incorrect or incomplete please don't hesitate to
open a Pull Request. The goal here is to provide you with all the information
you need to make the right choice for your needs.

<!-- markdownlint-disable MD013 -->
| **Dimension**                           | [sphinx-llm](https://github.com/NVIDIA/sphinx-llm)                                                                                                                                          | [sphinx-llms-txt](https://github.com/jdillard/sphinx-llms-txt/)                                |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------| ---------------------------------------------------------------------------------------------- |
| **Purpose**                             | Rich `llms.txt` and `llms-full.txt` markdown creation with individual pages and LLM summarization capabilities.                                                                             | Simple `llms.txt` and `llms-full.txt` files creation.                                          |
| **Individual pages**                    | Outputs a Markdown rendered version for each page.                                                                                                                                          | Source of each page is available at a Sphinx specific `_sources` URL.                          |
| **Supported docs input formats**        | Works with any Sphinx source format including RST, MyST, etc.                                                                                                                               | Works with any Sphinx source format including RST, MyST, etc.                                  |
| **Supported `llms.txt` output formats** | Markdown.                                                                                                                                                                                   | `llm.txt` is markdown; `llms-full.txt` and pages pass through source format.                   |
| **Additional features**                 | In the future could allow `llms.txt` to include LLM generated summaries of each page (see [#28](https://github.com/NVIDIA/sphinx-llm/issues/28)).                                           | Allows manual configuration of `llms-full.txt` content.                                        |
| **Build-time behavior**                 | Minimal build time impact; a separate build of the markdown is run in parallel, then the two build outputs are merged.                                                                      | Minimal build time impact; post build runs a converter/aggregator of `_sources`.               |
| **Limitations**                         | Not all directives are supported by the markdown builder.                                                                                                                                   | Source documentation files are not processed, so directives like `automodule` aren't expanded. |
<!-- markdownlint-enable MD013 -->

## Making a release

Releases are automated via GitHub Actions and any maintainers with write
access to the repository can create one in just a couple of steps. To create
a new release:

1. Create a new tag with the version number:

   ```console
   git tag -a 0.0.0 -m 'Version 0.0.0'
   ```

2. Push the tag to the upstream repository:

   ```console
   git push https://github.com/NVIDIA/sphinx-llm main --tags
   ```

The GitHub Actions workflow will automatically build the package and publish
it to PyPI using trusted publishing.
