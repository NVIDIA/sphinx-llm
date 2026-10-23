Tutorial
========

Let's build a small site about an orchard. By the end, you'll have HTML pages,
Markdown copies and an index that links them together. You only need the base
package for this tutorial; none of the steps call a model.

Create a project
----------------

Start in an empty working directory and install sphinx-llm in your Python
environment. We'll keep the source pages in a directory called ``source``:

.. code-block:: console

   python -m pip install sphinx-llm
   mkdir source

Create ``source/conf.py`` with a project name and the TXT extension:

.. code-block:: python

   project = "Orchard"
   extensions = ["sphinx_llm.txt"]

Next, create ``source/index.rst``. This is the homepage, and its
``toctree`` tells Sphinx about the Apples page we're going to add:

.. code-block:: rst

   Orchard
   =======

   Grow and care for a small orchard.

   .. toctree::

      apples

Create that page in ``source/apples.rst``:

.. code-block:: rst

   Apples
   ======

   Plant in a sunny location and water young trees regularly.

Build and inspect
-----------------

You can now build the site. The ``-W`` option makes warnings fail the
build, which helps catch mistakes while you're writing:

.. code-block:: console

   sphinx-build -W -b html source build/html

Open ``build/html/index.html`` in your browser and follow the link to
Apples. The site works like any other Sphinx HTML site.

Now open ``build/html/llms.txt`` in a text editor. Its Pages list links
to ``index.html.md`` and ``apples.html.md``. Each entry has a short
description taken from the page's content. Open ``apples.html.md`` to
see the Apples page rendered as Markdown rather than raw reStructuredText.

You'll also find ``apples.md`` in the output. By default, we publish
both URL layouts, but the index chooses ``apples.html.md`` as the
canonical, or preferred, URL. It doesn't add a second entry for the same page.

If you inspect the head of ``apples.html``, you'll see an
``alternate`` link to ``apples.html.md`` and a ``describedby``
link to ``llms.txt``. These let a consumer discover the Markdown
without knowing your site's structure.

You now have a site that people can browse and agents can retrieve page by page.
Next, you can :doc:`choose a different URL layout <how-to/suffix-urls>`
or :doc:`add a full-text download <how-to/indexes>`. The full-text file
is optional, so you won't find ``llms-full.txt`` in this build yet.
