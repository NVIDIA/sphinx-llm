sphinx_llm.txt
==============

Your HTML site is useful for people browsing the documentation. With
``sphinx_llm.txt``, you can publish Markdown versions of the same pages
for agents to retrieve, along with an ``llms.txt`` index to help them
find the right page.

Install ``sphinx-llm``, then add the extension to your ``conf.py``:

.. code-block:: python

   extensions = ["sphinx_llm.txt"]

You can now build your site as usual:

.. code-block:: console

   sphinx-build -b html source build/html

For a page such as ``source/guide.rst``, you'll get ``guide.html``,
``guide.html.md`` and ``guide.md`` in the HTML output directory.
The index links to one preferred Markdown URL, so it doesn't list the same page
twice. Your HTML pages also include links that advertise their Markdown versions.

You don't need a model for this workflow. Page descriptions come from your
metadata or page content unless you choose to generate them.
You can also :doc:`tailor content for each audience <how-to/audience-content>`
or publish a single full-text download. The extension supports the
``html`` and ``dirhtml`` builders, with Sphinx sources such as
reStructuredText and MyST.

Start with the tutorial to build a small site, or pick a guide for a change
you'd like to make to your existing project.

.. toctree::
   :maxdepth: 1

   tutorial
   how-to/index
   configuration
   output-reference
   explanation
