:orphan:

Alternatives
============

You may only need a small index, or you may want rendered Markdown pages
and optional summaries as well. This comparison can help you decide between
`sphinx-llm <https://github.com/NVIDIA/sphinx-llm>`_ and
`sphinx-llms-txt <https://github.com/jdillard/sphinx-llms-txt/>`_.

The comparison was prepared with input from the projects' maintainers, but
some judgments are subjective. If something is wrong or incomplete, please
open a pull request so we can keep it useful.

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

If you'd like to understand why sphinx-llm takes this approach,
:doc:`../txt/explanation` connects the build process to those tradeoffs.
