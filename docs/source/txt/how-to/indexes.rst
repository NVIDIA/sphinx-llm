Generate full and nested indexes
================================

For a downloadable single-file copy of the included pages:

.. code-block:: python

   llms_txt_full_build = True

Rebuild and inspect ``llms-full.txt``. The generated root ``llms.txt``
adds an Optional entry pointing to it. Full text contains one canonical copy
per included page, root first and then path-sorted. It can become large;
per-page retrieval avoids sending unrelated pages to a model.

For a root-only index instead of directory-scoped indexes:

.. code-block:: python

   llms_txt_nested_enabled = False

Rebuild into a clean output directory and inspect the HTML
``rel="describedby"`` links: all now target the root index.
With nested indexes enabled, each output directory implied by included pages
gets an index containing its descendant pages and a link back to the root.
The directory is based on the published HTML path, not simply the source
directory; ``dirhtml`` creates more such directories.
