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
| `llms_txt_enabled` | Enable or disable all llms.txt artefact generation. Set to `False` to skip the entire extension without removing it from `conf.py`. Use `sphinx-build -D llms_txt_enabled=0` to skip on a per-build basis. | `bool` | `True` |
| `llms_txt_description` | Override the project description set in `llms.txt` | `str` | Uses the project description from `pyproject.toml` by default |
| `llms_txt_build_parallel` | Build markdown files in parallel to the HTML files. | `bool` | `True` |
| `llms_txt_suffix_mode` | Suffix mode for generated markdown files. Options: `"auto"` (default behavior for each builder), `"file-suffix"` (spec-compliant format), `"url-suffix"` (URL-style format), or `"replace"` (replaces `.html` with `.md`). Note: `"both"` is deprecated but still supported (treated as `"auto"`). | `str` | `"auto"` |
| `llms_txt_full_build` | Whether to generate the `llms-full.txt` file. Set to `False` to disable generation, which is useful for large documentation sites where the concatenated file would be too large. | `bool` | `True` |
| `llms_txt_override_source` | Advanced option that overrides the automatically generated `llms.txt` sitemap with the rendered contents of a custom Sphinx source document. Specify a docname or source path relative to the source directory, such as `"llms-txt"` or `"llms-txt.rst"`. | `str` | `""` |
| `llms_txt_summary_enabled` | Generate one-sentence page descriptions with an OpenAI-compatible provider. | `bool` | `False` |
| `llms_txt_summary_provider` | Summary provider. The initial implementation supports `"openai-compatible"`. | `str` | `"openai-compatible"` |
| `llms_txt_summary_model` | Model used for generated page descriptions. Required when generation is enabled. | `str` | `""` |
| `llms_txt_summary_base_url` | Base URL of the OpenAI-compatible endpoint. An empty value uses the OpenAI client default. | `str` | `""` |
| `llms_txt_summary_api_key_env` | Name of the environment variable containing the API key. Set to `""` only for an endpoint that deliberately requires no authentication. | `str` | `"OPENAI_API_KEY"` |
| `llms_txt_summary_allow_insecure_auth` | Allow an API key to be sent to a non-loopback endpoint over plain HTTP. Use only for a trusted network where HTTPS is unavailable. | `bool` | `False` |
| `llms_txt_summary_max_input_chars` | Maximum Markdown characters sent to the provider. The complete page is still hashed for cache invalidation. | `int` | `12000` |
| `llms_txt_summary_timeout` | Provider request timeout in seconds. | `int` | `60` |
| `llms_txt_summary_cache_path` | JSON cache path. Relative paths use the Sphinx configuration directory; an empty value stores the cache under `app.doctreedir`. | `str` | `""` |
<!-- markdownlint-enable MD013 -->

Each page's entry in `llms.txt` includes a short description. If a page defines
an `html_meta` description, that non-empty author-provided value always wins and
no provider request is made. In reStructuredText, use:

```rst
.. meta::
   :description: An author-provided page description.
```

In MyST Markdown, use frontmatter:

```yaml
---
html_meta:
  description: An author-provided page description.
---
```

When no authored description exists, enabled summary generation uses a cached
or newly generated description. When generation is disabled, which is the
default, the extension retains the existing first-paragraph fallback and makes
no provider requests.

#### Generated page summaries

> [!WARNING]
> Enabling page summaries sends rendered documentation content to the configured
> provider. Review that provider's privacy and data-retention terms before using
> this feature with confidential documentation.

Install the optional generation dependencies and explicitly enable summaries:

```console
pip install sphinx-llm[gen]
export SPHINX_LLM_SUMMARY_ENABLED=1
export SPHINX_LLM_SUMMARY_MODEL=your-model
export SPHINX_LLM_SUMMARY_BASE_URL=https://llm.example.com/v1
export OPENAI_API_KEY=your-api-key
sphinx-build docs/source docs/build/html
```

The summary options can be configured in `conf.py` or supplied through
environment variables. Environment variables are useful when local and CI
builds need different providers or models, or when you do not want to commit
those settings to `conf.py`. The available variables are
`SPHINX_LLM_SUMMARY_ENABLED`, `SPHINX_LLM_SUMMARY_PROVIDER`,
`SPHINX_LLM_SUMMARY_MODEL`, `SPHINX_LLM_SUMMARY_BASE_URL`,
`SPHINX_LLM_SUMMARY_API_KEY_ENV`,
`SPHINX_LLM_SUMMARY_ALLOW_INSECURE_AUTH`,
`SPHINX_LLM_SUMMARY_MAX_INPUT_CHARS`, `SPHINX_LLM_SUMMARY_TIMEOUT`, and
`SPHINX_LLM_SUMMARY_CACHE_PATH`. Values resolve in this order: a
`sphinx-build -D` override, an environment variable, `conf.py`, then the
built-in default.
Installing the optional dependencies or detecting a local CLI does not enable
summaries; set `llms_txt_summary_enabled` explicitly.

`SPHINX_LLM_SUMMARY_API_KEY_ENV` is optional. Set it only to read the key from a
different environment variable, for example
`SPHINX_LLM_SUMMARY_API_KEY_ENV=NVIDIA_API_KEY`; it names the variable and does
not contain the key itself.

The API key itself is read only from the named environment variable; it is not
a Sphinx configuration value and is excluded from logs, the cache, and cache
fingerprints. The selected credential is sent to the configured endpoint, so
set `SPHINX_LLM_SUMMARY_API_KEY_ENV` when a non-OpenAI provider uses a different
key. For an explicitly unauthenticated endpoint, set
`llms_txt_summary_api_key_env = ""`; this does not fall back to `OPENAI_API_KEY`.
Configured keys are rejected for non-loopback plain-HTTP endpoints; use HTTPS,
or a loopback URL such as `http://localhost:8000/v1` for local development. If
neither is possible on a trusted network, set
`llms_txt_summary_allow_insecure_auth = True` in `conf.py` or
`SPHINX_LLM_SUMMARY_ALLOW_INSECURE_AUTH=1` in the environment. This sends the
API key without transport encryption and should not be used on untrusted
networks.

The versioned JSON cache is stored in the doctree directory by default and is
written atomically. Cache entries hash the complete generated Markdown plus the
provider, endpoint, model, prompt version, input limit, timeout, insecure-auth
setting, and credential environment-variable name. Only the configured Markdown
prefix is sent to the provider, but a change anywhere in a page invalidates that
page alone. Restore
the doctree directory or configured cache path in CI to reuse summaries across
jobs.

#### Custom `llms.txt` override

> [!IMPORTANT]
> This is an advanced option for users who need full control over `llms.txt`.
> Most projects should use the automatically generated sitemap.

To write `llms.txt` manually while retaining Sphinx features such as cross
references, create a source document and configure it in `conf.py`:

```python
llms_txt_override_source = "llms-txt.rst"
```

The document is rendered with the other Markdown pages, then its rendered
contents replace the automatically generated `llms.txt` sitemap. All per-page
Markdown files are still generated normally, while `llms-full.txt` remains
controlled independently by `llms_txt_full_build`. The custom source document
may be included in a toctree or marked with `:orphan:`.

### Docref

The `sphinx_llm.docref` extension adds a directive that summarises and links
to another page. It uses the same `llms_txt_summary_*` settings, environment
variables, provider safeguards, and versioned JSON cache described in
[Generated page summaries](#generated-page-summaries). Generation is disabled
by default.

Enable the extension in `conf.py`:

```python
extensions = [
    "sphinx_llm.docref",
]
```

An empty directive opts into automatic generation:

```rst
.. docref:: apples
```

A non-empty body is a permanent, reference-specific manual override:

```rst
.. docref:: apples

   A reviewed explanation of why the apples page is relevant here.
```

A page can also set its own description using page-level `html_meta` when you
want this content to be static.

Summary generation follows this order of precedence:

1. Non-empty directive body
2. Target page `html_meta` description
3. Valid generated summary from the shared page-summary cache
4. Content-derived fallback when generation is disabled or a target is missing

The optional directive `:model:` setting overrides
`llms_txt_summary_model` for one automatic reference. Identical references
to the same target and effective settings generate at most once. Requests and
effective rendering state live in the Sphinx environment, while generated
records are also persisted through `llms_txt_summary_cache_path` so clean
builds and `llms.txt` summary generation use one inspectable cache.

Each successful build writes `sphinx-llm-summaries.json` to the output
directory. It lists each effective summary, its origin, target, consuming
source locations, and generated-summary metadata without endpoints, API-key
environment-variable names, or credentials.

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

1. From `main`, create an annotated stable semantic-version tag with a `v`
   prefix (for example, `v0.0.0`; prerelease tags do not publish a release):

   ```console
   git tag -a v0.0.0 -m 'Version v0.0.0'
   ```

2. Push the tag to the upstream repository:

   ```console
   git push https://github.com/NVIDIA/sphinx-llm main --tags
   ```

The GitHub Actions workflow will automatically build the package and publish
it to PyPI using trusted publishing.
