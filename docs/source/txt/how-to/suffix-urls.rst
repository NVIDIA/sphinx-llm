Choose Markdown suffix URLs
===========================

You can publish Markdown at URLs that append to or replace the HTML suffix.
If your consumers expect ``guide.md`` rather than ``guide.html.md``,
set the following in your ``conf.py``:

.. code-block:: python

   llms_txt_suffix_mode = "replace"

Build into a fresh output directory so you can see which files this mode
produces:

.. code-block:: console

   sphinx-build -b html source build/replace

For ``guide.rst``, the HTML builder now publishes ``guide.md``
as the canonical Markdown page. If you're using ``dirhtml``, the same
document is published at ``guide/index.md``.

Use ``"append"`` when a consumer adds ``.md`` to an HTML URL,
or keep ``"auto"`` to offer both layouts. The
:doc:`output reference <../output-reference>` shows the exact paths,
including the homepage and nested index pages.

When you change modes, deploy a clean output directory. The extension
overwrites the paths selected by the current mode, but doesn't remove other
files left by earlier builds.

Also check that source documents won't produce the same output path. For
example, ``guide.rst`` and ``guide/index.rst`` collide in a
directory-style build. The build reports the collision instead of choosing
one page to overwrite.
