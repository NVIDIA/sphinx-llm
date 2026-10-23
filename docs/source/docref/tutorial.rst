Tutorial
========

Build an authored reference first, with only docref enabled. No model, key,
generation extra, or TXT extension is needed.

Create two pages
----------------

In an empty working directory:

.. code-block:: console

   python -m pip install sphinx-llm
   mkdir source

Create ``source/conf.py``:

.. code-block:: python

   project = "Orchard"
   extensions = ["sphinx_llm.docref"]

Create ``source/index.rst``:

.. code-block:: rst

   Orchard
   =======

   Choose a tree for your garden.

   .. toctree::

      apples

   .. docref:: apples

      Learn to plant an apple tree in a sunny garden.

Create ``source/apples.rst``:

.. code-block:: rst

   Apples
   ======

   Plant in a sunny location and water young trees regularly.

Build and inspect
-----------------

.. code-block:: console

   sphinx-build -W -b html source build/html

Open ``build/html/index.html``. Below the contents list, a
"See also: Apples" box contains the authored sentence and a "Read more >>"
link to Apples. Follow the link. Inspect
``build/html/sphinx-llm-summaries.json``: the entry has origin
``directive`` and records its consuming source and line.
There is no ``llms.txt`` because TXT is not enabled.

Use the target's description
----------------------------

Add this directly below the Apples title in ``source/apples.rst``:

.. code-block:: rst

   .. meta::
      :description: Plant and care for your first apple tree.

Remove the body from the docref so it is only ``.. docref:: apples``.
Rebuild with the same command. The rendered summary now uses the metadata,
and the report origin is ``html_meta``. If you remove that metadata too,
the reference uses a content-derived fallback while generation is off.

Optional: generate a summary
----------------------------

Follow :doc:`how-to/providers` to install ``sphinx-llm[gen]``,
select a provider and model, and enable summary generation. Keep the directive
empty and remove the target metadata if you want a generated result.
Rebuild only once the provider is available. A successful request produces
origin ``generated`` in the report; later unchanged builds reuse the cache.
This step sends target content to your selected provider and is not an offline
part of the tutorial. You can keep either authored version indefinitely.
