Override llms.txt
=================

The generated page list is usually enough to help agents explore a site.
If you want to curate a different starting point, you can write the root
index as a Sphinx document and still use cross-references.

Create ``source/llms-txt.rst``:

.. code-block:: rst

   :orphan:

   Orchard
   =======

   A focused index for orchard maintenance.

   Guides
   ------

   * :doc:`apples`

The ``:orphan:`` marker lets you keep this document outside a toctree
without a warning. You can include it in a toctree instead if readers should
see it in the HTML navigation.

Point to the document in your ``conf.py``:

.. code-block:: python

   llms_txt_override_source = "llms-txt.rst"

After rebuilding, open the root ``llms.txt``. It now contains the
rendered Markdown from your document, with Sphinx links adjusted for the
index's location. You can also use the extensionless docname
``"llms-txt"``. Either way, the document must be part of the build
and must not match ``llms_txt_exclude``.

This replaces only the root index. Individual Markdown pages, nested indexes
and optional full text are still generated. If you want all discovery to go
through your curated root, :doc:`turn off nested indexes <indexes>` too.
A custom root doesn't gain the full-text link automatically, so add that link
yourself if you offer the download.
