Override llms.txt
=================

Use this advanced workflow when the generated page list is not the structure
you want. Create ``source/llms-txt.rst``:

.. code-block:: rst

   :orphan:

   Orchard
   =======

   A focused index for orchard maintenance.

   Guides
   ------

   * :doc:`apples`

Point ``conf.py`` at that source document:

.. code-block:: python

   llms_txt_override_source = "llms-txt.rst"

Rebuild and inspect the root ``llms.txt``; it is the rendered Markdown
of this document, with Sphinx links rewritten for its output location.
A docname (``"llms-txt"``) also works. The source must exist in the
build and must not match ``llms_txt_exclude``.

Per-page Markdown, nested indexes, and optional full text are still generated
independently. Disable nested indexes if you also want to control all discovery
through your custom root. A custom root does not automatically acquire the
Optional link to full text; author that link yourself if needed.
