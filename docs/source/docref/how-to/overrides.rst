Override summaries and titles
=============================

For context specific to one reference, put the reviewed summary in its body:

.. code-block:: rst

   .. docref:: /apples

      Start here for planting advice; see the pruning section next season.

A leading slash selects a docname from the Sphinx source root. Without it,
targets resolve relative to the consuming document. Use extensionless docnames.

To reuse one description everywhere, put metadata on the target page instead:

.. code-block:: rst

   .. meta::
      :description: Plant and prune apple trees.

An empty docref uses this description, while a non-empty body still wins.
MyST's ``html_meta.description`` frontmatter works too.
See :doc:`../../txt/how-to/descriptions` for syntax.

The title is the target document's title, not a directive option.
Edit that target heading to change it globally, or change
``:style-title-prefix:`` for one reference's framing:

.. code-block:: rst

   .. docref:: /apples
      :style-title-prefix: Planting guide:

      Practical advice for choosing a sunny location.

There is no ``:title:`` override for arbitrary per-reference titles.
For selection order and all supported options, see :doc:`../directive-reference`.
