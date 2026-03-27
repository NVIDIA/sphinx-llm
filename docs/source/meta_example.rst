.. meta::
   :description: A page demonstrating the use of html_meta for llms.txt descriptions.

Page with html_meta description
================================

This page has an ``html_meta`` description set via the ``.. meta::`` directive.
The ``sphinx_llm.txt`` extension uses this description in ``llms.txt`` instead
of falling back to the first 100 characters of page content.

In MyST Markdown, the equivalent frontmatter is:

.. code-block:: yaml

   ---
   html_meta:
     description: A page demonstrating the use of html_meta for llms.txt descriptions.
   ---
