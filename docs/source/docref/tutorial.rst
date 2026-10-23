Tutorial
========

Let's add a linked summary to a small documentation site. You'll write the
first summary yourself, then reuse a description from the target page.
Both versions work with docref alone, without TXT, a model or an API key.

Create two pages
----------------

Start in an empty working directory. Install the base package in your Python
environment and create a directory for the source pages:

.. code-block:: console

   python -m pip install sphinx-llm
   mkdir source

Create ``source/conf.py`` and enable only docref:

.. code-block:: python

   project = "Orchard"
   extensions = ["sphinx_llm.docref"]

Next, create ``source/index.rst``. It links to an Apples page in the
contents list and introduces that page with a summary:

.. code-block:: rst

   Orchard
   =======

   Choose a tree for your garden.

   .. toctree::

      apples

   .. docref:: apples

      Learn to plant an apple tree in a sunny garden.

Now create the target page in ``source/apples.rst``:

.. code-block:: rst

   Apples
   ======

   Plant in a sunny location and water young trees regularly.

Build and inspect
-----------------

Build the site with warnings treated as errors:

.. code-block:: console

   sphinx-build -W -b html source build/html

Open ``build/html/index.html``. Beneath the contents list, you'll see
a "See also: Apples" box containing the sentence you wrote. Follow its
"Read more >>" link to check that it takes you to the Apples page.

You can also inspect ``build/html/sphinx-llm-summaries.json``.
The entry has origin ``directive``, which tells you that its text came
from the directive body, along with the consuming source and line.
There's no ``llms.txt`` in this project because we haven't enabled TXT.

Use the target's description
----------------------------

If several pages refer to Apples, you may prefer to maintain its description
in one place. Add this below the title in ``source/apples.rst``:

.. code-block:: rst

   .. meta::
      :description: Plant and care for your first apple tree.

Remove the body from the docref, leaving just ``.. docref:: apples``,
and rebuild with the same command. The box now uses the description from
Apples. In the report, the origin changes to ``html_meta``.

If you remove the metadata too, docref falls back to the page's content while
generation is off. That gives you a useful reference without contacting a
provider, but an authored description gives you control over the wording.

Optional: generate a summary
----------------------------

You now have a working reference and can keep either authored version.
If you'd rather generate summaries, follow the
:doc:`provider guide <how-to/providers>` to install
``sphinx-llm[gen]``, choose an endpoint and model, and enable generation.

Leave the directive empty and remove the target metadata before trying that
workflow; authored descriptions take priority. Once your provider is available,
rebuild and look for origin ``generated`` in the report. Later unchanged
builds can reuse the cached result.

Unlike the steps above, this optional step sends target content to your
selected provider. You don't need it to complete the tutorial.
