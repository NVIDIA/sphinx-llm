Choose Markdown suffix URLs
===========================

Choose the URL contract you want to publish before distributing links.
To publish only the representation that replaces the HTML extension:

.. code-block:: python

   llms_txt_suffix_mode = "replace"

Build into a fresh directory with ``sphinx-build -b html source build/replace``.
A ``guide.rst`` page now has ``guide.md`` as its canonical representation.
With ``dirhtml``, its canonical path is ``guide/index.md``.

Choose ``"append"`` when clients append ``.md`` to HTML URLs, or
keep ``"auto"`` to serve both layouts. Compare the exact root and nested
paths in :doc:`../output-reference`.

When changing modes, deploy a clean build directory: unselected files from
older builds are deliberately not deleted. Do not add source documents whose
outputs collide (for example, ``guide.rst`` and ``guide/index.rst`` in
a directory-style build). A collision fails rather than overwriting a page.
