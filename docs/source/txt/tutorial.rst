Tutorial
========

Build a tiny documentation site and inspect the artifacts. This tutorial uses
only the base package and makes no provider requests.

Create a project
----------------

In an empty working directory, install into your Python environment:

.. code-block:: console

   python -m pip install sphinx-llm
   mkdir source

Create ``source/conf.py``:

.. code-block:: python

   project = "Orchard"
   extensions = ["sphinx_llm.txt"]

Create ``source/index.rst``:

.. code-block:: rst

   Orchard
   =======

   Grow and care for a small orchard.

   .. toctree::

      apples

Create ``source/apples.rst``:

.. code-block:: rst

   Apples
   ======

   Plant in a sunny location and water young trees regularly.

Build and inspect
-----------------

.. code-block:: console

   sphinx-build -W -b html source build/html

Open ``build/html/index.html`` in your browser. Then read
``build/html/llms.txt``: its Pages list links to ``index.html.md``
and ``apples.html.md``, and Apples uses a content-derived description.
Read ``build/html/apples.html.md`` to see the rendered Markdown.
The default also publishes ``apples.md`` as an alternative layout;
it is not a second index entry.

Inspect the head of ``apples.html`` for ``rel="alternate"`` pointing to
``apples.html.md`` and ``rel="describedby"`` pointing to ``llms.txt``.
There is no ``llms-full.txt`` until you opt into it.
Next, :doc:`how-to/suffix-urls` or :doc:`how-to/indexes`.
