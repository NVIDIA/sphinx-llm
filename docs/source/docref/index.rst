sphinx_llm.docref
=================

Render a linked reference to another Sphinx page as a static admonition with
a title, summary, and visit link. Use reviewed authored text without any model,
or opt into generation when you need it. This extension works independently
of TXT: you do not need to enable ``sphinx_llm.txt``.

Install ``sphinx-llm``, enable ``sphinx_llm.docref`` in ``conf.py``,
and reference an existing document:

.. code-block:: rst

   .. docref:: apples

      Learn how to plant and prune your first apple tree.

The rendered box is titled "See also: Apples", shows your paragraph, and
links to the target with "Read more >>". An authored body is a permanent,
reference-specific override; it is not silently replaced on later builds.
A target page can instead provide its own metadata description.
An empty directive uses that metadata, a valid generated cache entry, or
content-derived fallback. Generation requires explicit opt-in.

.. only:: html

   Here is a live, authored reference rendered by this site:

   .. docref:: tutorial

      Build a two-page project with reviewed summaries and inspect its provenance.

.. toctree::
   :maxdepth: 1

   tutorial
   how-to/index
   configuration
   directive-reference
   explanation
