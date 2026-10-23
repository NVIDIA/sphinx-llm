Override summaries and titles
=============================

A summary can explain why a page matters at one particular point in your
documentation. To write that explanation yourself, put it in the directive body:

.. code-block:: rst

   .. docref:: /apples

      Start here for planting advice; see the pruning section next season.

Here, ``/apples`` selects the document from the source root.
Without a leading slash, the target is relative to the page containing the
docref. In either case, use the document name without its source extension.

Reuse the target's description
------------------------------

If every reference should introduce a page in the same way, write the
description on the target page instead:

.. code-block:: rst

   .. meta::
      :description: Plant and prune apple trees.

An empty docref uses that description. A reference with its own body still
uses the body, so you can keep a shared introduction and override it where
you need more context. MyST's ``html_meta.description`` frontmatter
works too; see :doc:`../../txt/how-to/descriptions` for an example.

Change the title's framing
--------------------------

The box's title comes from the target page's heading. You can edit that heading
to change all references, or give one reference a different prefix:

.. code-block:: rst

   .. docref:: /apples
      :style-title-prefix: Planting guide:

      Practical advice for choosing a sunny location.

This changes the framing, not the target title. There isn't a ``:title:``
option for an arbitrary per-reference title. You can find the complete
selection order and available options in the :doc:`../directive-reference`.
