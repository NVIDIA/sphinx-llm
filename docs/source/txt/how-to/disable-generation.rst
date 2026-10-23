Disable artifact or summary generation
======================================

For a build without TXT artifacts, keep the extension installed and run:

.. code-block:: console

   sphinx-build -b html -D llms_txt_enabled=0 source build/html-only

Use a clean directory; disabling generation does not remove artifacts already
on disk. This setting controls TXT artifacts, not independent docref rendering.
The extension still normalizes the human/agent audience tags for the builder;
see :doc:`audience-content`.

To retain Markdown and indexes while avoiding provider requests:

.. code-block:: console

   sphinx-build -b html -D llms_txt_summary_enabled=0 source build/offline

Docref can still reuse valid generated cache entries with generation off;
the switch prevents new requests, not cached rendering. For a permanently
reviewed description, use page metadata or a docref body.
