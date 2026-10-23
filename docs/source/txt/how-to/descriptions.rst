Author or generate descriptions
===============================

Each entry in ``llms.txt`` has a short description to help a reader
choose a page. You can write that description yourself using page metadata.
For a reStructuredText page, add:

.. code-block:: rst

   .. meta::
      :description: Install Orchard and plant your first trees.

If you're writing MyST with ``myst_parser`` enabled, put the description
in frontmatter at the top of the page instead:

.. code-block:: yaml

   ---
   html_meta:
     description: Install Orchard and plant your first trees.
   ---

Rebuild and find that page's entry in ``llms.txt``. It should use the
description you've written. A non-empty metadata description takes priority,
so the extension won't make a provider request for that page.

Some Markdown-builder versions warn about the metadata node even though TXT
can read the description from the HTML doctree. If you see that warning,
inspect the Markdown first. When the metadata is the only unsupported content,
you can add ``"meta"`` to
``llms_txt_suppress_unknown_node_warnings``. The
:doc:`troubleshooting guide <troubleshooting>` explains how warning
suppression differs from preserving content.

Generate descriptions for other pages
-------------------------------------

Without metadata or generation, TXT uses a short part of the first meaningful
paragraph in the rendered Markdown. If you'd like a model to write these
descriptions, follow the :doc:`provider guide <../../docref/how-to/providers>`
to install the generation extra and configure an endpoint.

Those settings also work when you only enable TXT; docref isn't required.
Generation applies to included pages that don't have authored metadata.
TXT sends a bounded prefix of the final Markdown, rather than raw RST.

Before enabling this in CI, read the :ref:`shared-summary-settings` and
:doc:`cache guide <../../docref/how-to/cache-ci>` so you know which content
will be sent and when a description will be regenerated.
