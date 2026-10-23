:orphan:

Contributing
============

Development setup
-----------------

Use a repository checkout and Python 3.10 or newer for the themed site.
The library itself supports Python 3.9 and newer.

.. code-block:: console

   git clone https://github.com/NVIDIA/sphinx-llm.git
   cd sphinx-llm
   uv sync --dev --extra gen --group docs
   uvx pre-commit install
   uv run pytest src/sphinx_llm/tests/

Build the site once, or serve it with automatic rebuilds:

.. code-block:: console

   uv run --group docs sphinx-build -W docs/source docs/build/html
   uv run --dev --group docs sphinx-autobuild docs/source docs/build/html

Normal primary-site builds publish Markdown and indexes without a model.
The theme is in a separate opt-in dependency group; do not use it to constrain
the library's Sphinx compatibility tests.

Integration fixtures
--------------------

The unthemed sample/test corpus lives separately from the primary site:

.. code-block:: console

   uv run --dev sphinx-build -W src/sphinx_llm/tests/fixtures/integration_docs docs/build/fixtures

Tests build this corpus into temporary directories and exercise HTML and
directory-style output, sequential and parallel Markdown builds, and
compatibility settings. Keep behavioral test content in the fixture corpus
rather than adding test pages to the user-facing site.

Before submitting
-----------------

Run the relevant tests, a strict documentation build, and all hooks:

.. code-block:: console

   uvx pre-commit run --all-files

Keep setting names, types, defaults, and basic behavior in the configuration
references as the single source of truth; use task guides for interactions.
See the repository's `AGENTS.md <https://github.com/NVIDIA/sphinx-llm/blob/main/AGENTS.md>`_
for architecture and detailed development conventions.
Contributors not employed by NVIDIA must sign off commits with
``git commit -s`` (Developer Certificate of Origin).
Maintainers can follow :doc:`releasing`.
