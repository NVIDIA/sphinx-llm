Reuse caches in CI
==================

Use a stable cache location outside a disposable HTML output directory:

.. code-block:: python

   llms_txt_summary_cache_path = "../.cache/page-summaries.json"

Relative paths resolve from the Sphinx configuration directory, so for
``source/conf.py`` this selects ``.cache/page-summaries.json``
at the project root. Restore the file before building and save it after a
successful trusted build, or retain the default doctree directory instead.

For offline CI, keep generation disabled with a command-line override:

.. code-block:: console

   sphinx-build -W -b html -D llms_txt_summary_enabled=0 source build/html

Docref can render valid cached results while generation is off, but missing or
stale records use fallback text. TXT instead uses its content fallback when
generation is off; it does not consult generated descriptions in that mode.
Use authored summaries when exact wording must be reproducible independently
of cache state.

Treat caches as documentation-derived data: they contain generated text,
targets and metadata, and are not a substitute for a secret store.
Do not let untrusted jobs overwrite a cache used by a privileged build.
Changing a page or effective generation settings can invalidate its entry.
Inspect ``sphinx-llm-summaries.json`` to audit docref output origins; this
report is not the persistent cache and cannot be restored as one.
See :doc:`../explanation` for cache keys and data flow.
