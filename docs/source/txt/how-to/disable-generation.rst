Disable artifact or summary generation
======================================

You can turn off TXT's output for one build without removing the extension.
For example, to produce an HTML-only build, run:

.. code-block:: console

   sphinx-build -b html -D llms_txt_enabled=0 source build/html-only

Use a clean output directory for this check. Turning generation off doesn't
delete files from an earlier build.

This switch controls TXT artifacts, not independent docref rendering.
The extension also continues to select the builder's human or agent audience;
see :doc:`audience-content` if you're using conditional content.

Keep Markdown without making provider requests
----------------------------------------------

If you want Markdown and indexes but don't want to generate new summaries,
override the shared summary setting instead:

.. code-block:: console

   sphinx-build -b html -D llms_txt_summary_enabled=0 source build/offline

Docref can still render valid generated results from its cache. The switch
prevents new requests; it doesn't erase or hide cached text. If you need
wording that won't depend on the cache, write a page description or docref
body yourself.
