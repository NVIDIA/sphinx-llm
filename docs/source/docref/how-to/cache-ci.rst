Reuse caches in CI
==================

You can reuse generated summaries across builds by restoring their cache.
Choose a path that won't disappear with your HTML output directory, for example:

.. code-block:: python

   llms_txt_summary_cache_path = "../.cache/page-summaries.json"

Relative paths start at the Sphinx configuration directory. If your
configuration is ``source/conf.py``, this example puts the cache in
``.cache/page-summaries.json`` at the project root.

Restore the file before a trusted build and save it afterwards.
You can instead retain the default doctree directory, which also holds the
cache when you haven't chosen a separate path.

Build without a provider
------------------------

To prevent new provider requests in an offline job, override the shared
summary switch:

.. code-block:: console

   sphinx-build -W -b html -D llms_txt_summary_enabled=0 source build/html

Docref can still render valid cached summaries. If a record is missing or
stale, it uses fallback text. TXT behaves differently in this mode: it uses
the content fallback rather than consulting generated descriptions.

If exact wording must be reproducible without a particular cache file, author
the summary. A cache saves requests, but isn't a replacement for reviewed text.

Handle the cache and report separately
--------------------------------------

The cache contains generated text, targets and metadata. Treat it as
documentation-derived data, not a secret store, and don't let untrusted jobs
overwrite a cache used by a privileged build. Changes to a page or its
effective generation settings can invalidate a record.

You can inspect ``sphinx-llm-summaries.json`` to see which text docref
actually rendered and where it came from. That report isn't the persistent
cache, so restoring it won't restore generated summaries.
:doc:`../explanation` describes the cache keys and the difference between
TXT and docref inputs.
