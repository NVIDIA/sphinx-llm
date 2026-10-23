Author or generate descriptions
===============================

Prefer an authored description for important pages. In reStructuredText:

.. code-block:: rst

   .. meta::
      :description: Install Orchard and plant your first trees.

For MyST projects with ``myst_parser`` enabled, put this frontmatter at
the top of a page:

.. code-block:: yaml

   ---
   html_meta:
     description: Install Orchard and plant your first trees.
   ---

Build and inspect the page's entry in ``llms.txt``. Non-empty authored
metadata wins without a provider request. Some versions of the Markdown builder
warn about the metadata node even though TXT can read its description from the
HTML doctree. Inspect the Markdown; if the only unsupported content is that
metadata, add ``"meta"`` to ``llms_txt_suppress_unknown_node_warnings``.
See :doc:`troubleshooting` for the preservation/suppression controls.

Otherwise, with generation off, TXT
extracts a short first meaningful paragraph from the generated Markdown.

For generated descriptions, follow :doc:`../../docref/how-to/providers`
to configure an OpenAI-compatible endpoint, install the generation extra and
enable summaries. The same settings apply to TXT even without docref installed.
Only included pages lacking authored metadata need generated descriptions.
TXT sends a bounded prefix of final rendered Markdown, not raw RST.
See :ref:`shared-summary-settings` and
:doc:`../../docref/how-to/cache-ci` before enabling this in CI.
