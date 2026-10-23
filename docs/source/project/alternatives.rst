:orphan:

Alternatives
============

There are other projects that solve this problem; that is the wonderful nature
of open source software. These comparisons were put together with the best of
intentions and involvement from maintainers of the projects compared, but are
subjective. If information is incorrect or incomplete, please open a pull
request. The goal is to help you choose for your needs.

Compare `sphinx-llm <https://github.com/NVIDIA/sphinx-llm>`_ with
`sphinx-llms-txt <https://github.com/jdillard/sphinx-llms-txt/>`_:

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Dimension
     - sphinx-llm
     - sphinx-llms-txt
   * - Purpose
     - llms.txt v2 index and per-page Markdown, optional full text and LLM summaries.
     - Simple llms.txt and llms-full.txt creation.
   * - Individual pages
     - Markdown-rendered version of each page.
     - Source for each page at a Sphinx-specific _sources URL.
   * - Input formats
     - Any Sphinx source format, including RST and MyST.
     - Any Sphinx source format, including RST and MyST.
   * - Output formats
     - Markdown index and pages; optional full text is Markdown too.
     - llm.txt is Markdown; full text and pages pass through the source format.
   * - Additional features
     - Generated summaries and optional concatenated full text.
     - Manual configuration of full-text content.
   * - Build behavior
     - Separate Markdown build, run in parallel by default, then merged.
     - Post-build conversion and aggregation of _sources.
   * - Limitations
     - The Markdown builder does not support every directive.
     - Source files are not processed, so directives such as automodule are not expanded.

See :doc:`../txt/explanation` for sphinx-llm's design and tradeoffs.
