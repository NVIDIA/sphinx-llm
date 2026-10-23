Getting Started
=================

You can use sphinx-llm to publish Markdown for agents, add linked summaries
to your pages, or do both. Start by installing the package in the same Python
environment you use to build your Sphinx documentation, then choose the
extension that fits your project.

Installation
--------------

Install the base package from PyPI:

.. code-block:: console

   python -m pip install sphinx-llm

This includes what you need to publish Markdown and write your own linked
summaries. You don't need a model, API key or generation extra for either
workflow.

If you later want a model to write descriptions, install the optional
generation dependencies:

.. code-block:: console

   python -m pip install "sphinx-llm[gen]"

Installing the extra doesn't enable provider requests. You'll also need to
choose an OpenAI-compatible endpoint and model, supply any credentials it
requires, and explicitly enable summary generation. A local endpoint needs a
running server and an available model too. The
:doc:`provider guide <docref/how-to/providers>` walks through those choices
when you're ready to use generation.

Publish Markdown with sphinx_llm.txt
--------------------------------------

If you want agents to retrieve your documentation as Markdown, use
``sphinx_llm.txt``. It builds Markdown copies of your pages alongside HTML
and creates an ``llms.txt`` index to help consumers find them. You can keep
your existing Sphinx source and HTML site.

Start with the :doc:`TXT overview <txt/index>` for the minimal configuration
and a tutorial you can build without a model.

Add linked summaries with sphinx_llm.docref
---------------------------------------------

If you want to introduce another page with a short summary and link, use
``sphinx_llm.docref``. You can write the summary for one reference or reuse
a description from the target page. You can also choose to generate summaries
later, but authored references don't need a provider.

Start with the :doc:`docref overview <docref/index>` to see a rendered example
and follow the authored-summary tutorial. You don't need to enable TXT to use
docref, and you can enable both extensions if you want linked summaries in
your site as well as Markdown output.
