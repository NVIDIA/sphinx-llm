sphinx-llm
==========

Sphinx extensions for working with LLMs in your documentation.

Two extension families
----------------------

* **Make documentation consumable by LLMs and agents** with ``sphinx_llm.txt``.
  Generate an ``llms.txt`` index and per-page Markdown alongside your HTML.
* **Generate content during documentation builds** with ``sphinx_llm.docref``.
  Render references and page summaries as static documentation content, using
  authored descriptions or an explicitly configured model.

Quick start
-----------

Install the package in your documentation environment:

.. code-block:: console

   pip install sphinx-llm

Add the extension to your existing Sphinx ``conf.py``:

.. code-block:: python

   extensions = [
       "sphinx_llm.txt",
   ]

Build your documentation:

.. code-block:: console

   sphinx-build -b html docs/source docs/build/html

The output includes HTML, an ``llms.txt`` index, and Markdown versions of your
pages. No model or API key is needed for this workflow. To generate summaries
with a model, install ``sphinx-llm[gen]`` and follow the configuration instructions
in the README.

Learn more
----------

* `README: extension usage and configuration <https://github.com/NVIDIA/sphinx-llm#readme>`_
* `Source repository <https://github.com/NVIDIA/sphinx-llm>`_
* `Issue tracker <https://github.com/NVIDIA/sphinx-llm/issues>`_
