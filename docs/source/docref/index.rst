sphinx_llm.docref
=================

You can use ``sphinx_llm.docref`` to introduce another page with a
title, a short summary and a link. The result is part of your built
documentation, not an interactive chat service.

Install ``sphinx-llm`` and enable the extension in ``conf.py``:

.. code-block:: python

   extensions = ["sphinx_llm.docref"]

Then add a reference to an existing page. For example, if you have an
``apples.rst`` page, you could write:

.. code-block:: rst

   .. docref:: apples

      Learn how to plant and prune your first apple tree.

When you build, readers see a box titled "See also: Apples", your summary and
a "Read more >>" link. The title comes from the target page, while the body
lets you explain why that page is useful in this particular context.

You can also reuse a description from the target page's metadata. If you leave
the directive empty, docref looks for that description, then a valid generated
summary, and finally a short content-based fallback. Your authored text won't
be silently replaced by a later model response.

.. only:: html

   Here's an authored reference rendered by this site:

   .. docref:: tutorial

      Build a two-page project with reviewed summaries and inspect its provenance.

You don't need TXT, a model or an API key to use authored references.
If you want a model to write summaries, you can enable that separately.
The tutorial starts with authored text so you can see the result before
deciding whether you need generation.

.. toctree::
   :maxdepth: 1

   tutorial
   how-to/index
   configuration
   directive-reference
   explanation
