Generate full and nested indexes
================================

You can offer a full-text download for consumers that want to read all your
included pages at once. Add this to your ``conf.py``:

.. code-block:: python

   llms_txt_full_build = True

Rebuild and open ``llms-full.txt`` in the output directory. It contains
one canonical copy of each included page, with the root page first and the
others sorted by output path. The generated root ``llms.txt`` also
gains an Optional entry linking to it.

A full-text file can grow quickly. If you want agents to retrieve only the
pages relevant to a task, you can leave full text off and use the page indexes.

Use a root-only index
---------------------

Nested indexes let a consumer start with one directory and its descendants.
If you'd rather have every page advertise the same root index, set:

.. code-block:: python

   llms_txt_nested_enabled = False

Build into a clean output directory, then inspect a deep HTML page's
``rel="describedby"`` link. It now points back to the root
``llms.txt``, rather than a directory-scoped index.

With nested indexes enabled, every output directory implied by included pages
gets a list of its descendant pages and a link back to the root. These are
published HTML directories, not just source directories, so a ``dirhtml``
build creates more nested indexes than an ``html`` build.
