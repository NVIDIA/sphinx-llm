Contributing
============

You can work on sphinx-llm with a local checkout and uv.
Use Python 3.10 or newer if you're building the themed site; the library itself
also supports Python 3.9.

Development setup
-----------------

Clone the repository, install the development and documentation dependencies,
then install the pre-commit hooks:

.. code-block:: console

   git clone https://github.com/NVIDIA/sphinx-llm.git
   cd sphinx-llm
   uv sync --dev --extra gen --group docs
   uvx pre-commit install

You can now run the tests from the repository root:

.. code-block:: console

   uv run pytest src/sphinx_llm/tests/

To check the site once, build with warnings treated as errors. While you're
writing, you can use the automatic rebuild server instead:

.. code-block:: console

   uv run --group docs sphinx-build -W docs/source docs/build/html
   uv run --dev --group docs sphinx-autobuild docs/source docs/build/html

Normal site builds generate Markdown and indexes without calling a model.
The theme lives in an opt-in dependency group so its requirements don't
constrain the library's Sphinx compatibility tests.

Integration fixtures
--------------------

The test documentation lives separately from the site and doesn't use its
theme. You can build it directly to inspect an example's output:

.. code-block:: console

   uv run --dev sphinx-build -W src/sphinx_llm/tests/fixtures/integration_docs docs/build/fixtures

Tests build this corpus into temporary directories for HTML, directory-style
output, sequential and parallel Markdown builds, and compatibility settings.
For automated build coverage, prefer adding an example to the fixture corpus
and asserting against its rendered output rather than inlining documentation
source in a test. Keep scenario-specific configuration and assertions in
the test that needs them.

A user-facing example has a different purpose: it helps someone try the
feature. Add those examples to the primary site as well when you change
extension functionality.

Before submitting
-----------------

If you're changing documentation, follow :doc:`../maintainers/writing-style`.
Keep setting names, types, defaults and basic behavior in their configuration
references, then link to them from the task guides.

Run the relevant tests, a strict site build and all the hooks:

.. code-block:: console

   uvx pre-commit run --all-files

The repository's
`AGENTS.md <https://github.com/NVIDIA/sphinx-llm/blob/main/AGENTS.md>`_
has more architecture and development guidance. Contributors who aren't
employed by NVIDIA must sign off their commits with ``git commit -s``
for the Developer Certificate of Origin.

When preparing a pull request, follow the
`making-a-pr skill <https://github.com/NVIDIA/sphinx-llm/blob/main/.agents/skills/making-a-pr/SKILL.md>`_.
Link to the relevant Read the Docs examples and include preview screenshots
for visual changes. Those examples complement the fixture tests rather
than replacing them.

If you're preparing a release, continue with :doc:`releasing`.
