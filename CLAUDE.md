# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

`sphinx-llm` is a collection of Sphinx extensions for working with LLMs. It
serves two purposes:

1. **Enabling LLMs to consume documentation** - Generates `llms.txt`,
   `llms-full.txt`, and per-page markdown files following the
   [llms.txt](https://llmstxt.org/) standard
2. **Leveraging LLMs to generate content** - Uses LLMs to generate static
   content during builds (e.g., the `docref` directive for page summaries)

## Development Commands

### Setup

```bash
# Install dependencies with uv (recommended)
uv sync --dev --extra gen
```

### Testing

```bash
# Run all tests
uv run pytest src/sphinx_llm/tests/

# Run tests with coverage
uv run pytest src/sphinx_llm/tests/ --cov=sphinx_llm --cov-report=xml

# Run tests against a specific Sphinx version
uv run --with "sphinx>=7,<8" pytest src/sphinx_llm/tests/
```

### Linting and Formatting

```bash
# Run ruff linter with auto-fix
uv run pre-commit run ruff --all-files

# Run ruff formatter
uv run pre-commit run ruff-format --all-files

# Run all pre-commit hooks (includes ruff, prettier, markdownlint, codespell,
# license headers)
uv run pre-commit run --all-files
```

### Building Documentation

```bash
# Build the example docs (recommended for development)
uv run --dev sphinx-autobuild docs/source docs/build/html

# Build docs once
uv run --dev sphinx-build docs/source docs/build/html
```

## Architecture

### Core Extensions

**`sphinx_llm.txt` (src/sphinx_llm/txt.py)**

- Hooks into Sphinx's `builder-inited` and `build-finished` events
- Spawns a parallel subprocess running `sphinx-build -b markdown` to generate
  markdown files
- The `MarkdownGenerator` class orchestrates:
  1. Parallel markdown build (can be disabled via `llms_txt_build_parallel`
     config)
  2. Merging markdown output with HTML output (each page gets `.html.md`
     extension)
  3. Generating `llms-full.txt` (concatenated markdown)
  4. Generating `llms.txt` (sitemap with descriptions)
- Handles both `html` and `dirhtml` builders with different path structures
- For `dirhtml` builder, supports three suffix modes via `llms_txt_suffix_mode`:
  - `"file-suffix"`: Only generates `page/index.html.md` files
  - `"url-suffix"`: Only generates URL-style `page.md` files
  - `"both"` (default): Generates both formats for maximum compatibility

**`sphinx_llm.docref` (src/sphinx_llm/docref.py)**

- Custom Sphinx directive extending `BaseAdmonition`
- Generates LLM summaries of referenced documents using Ollama
- Caches summaries using MD5 hash of document content
- **Modifies source files in-place** to persist generated summaries (RST only currently)
- Requires Ollama running at `OLLAMA_BASE_URL` (default: `http://localhost:11434`)
- Default model: `llama3.2:3b`

## Test Structure

Tests live in `src/sphinx_llm/tests/` (not a separate `tests/` directory).
Tests use pytest fixtures that build the example docs in `docs/source/` into
temporary directories with different builders and parallel settings.

Key test fixture: `sphinx_build` - parametrized fixture that tests both `html`
and `dirhtml` builders with parallel and sequential markdown building.

## Commit Requirements

All commits by contributors who are not employed by NVIDIA must be signed off
using `git commit -s` (Developer Certificate of Origin). Pre-commit hooks
enforce:

- Ruff formatting and linting
- License header in all `.py` files (using `LICENSE_HEADER` file)
- Prettier for YAML
- Markdownlint for Markdown
- Codespell for spelling

## Version Management

Uses `hatch-vcs` for version management from git tags. Version is generated at
build time into `src/sphinx_llm/_version.py`.
