sphinx_llm.txt
==============

Publish documentation that agents can retrieve as Markdown while keeping your
normal HTML site. The extension creates ``llms.txt``, one or more Markdown
representations of each page, and optionally ``llms-full.txt``.
It supports Sphinx's ``html`` and ``dirhtml`` builders and source formats
such as reStructuredText and MyST.

Install ``sphinx-llm`` and add to ``conf.py``:

.. code-block:: python

   extensions = ["sphinx_llm.txt"]

Build with ``sphinx-build -b html source build/html``. For ``source/guide.rst``,
the default output includes ``build/html/guide.html``,
``guide.html.md``, and ``guide.md``. The index points to one canonical
Markdown representation, not both. HTML pages advertise it with discovery links.

Use :doc:`how-to/audience-content` to tailor conditional content for human
readers and agent workflows without maintaining separate source trees.

No model is required. Descriptions come from authored page metadata or page
content unless you explicitly enable generation.

.. toctree::
   :maxdepth: 1

   tutorial
   how-to/index
   configuration
   output-reference
   explanation
