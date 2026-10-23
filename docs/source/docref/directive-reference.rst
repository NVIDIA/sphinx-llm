Directive reference
===================

Use ``docref`` to render a summary and link to a Sphinx document.
For a first working project, follow the :doc:`tutorial`.

Syntax and target
-----------------

.. code-block:: rst

   .. docref:: /guide/apples
      :style-title-prefix: Related:
      :style-visit-link-text: Read the guide
      :style-visit-link-class: docref-link

      Optional authored summary with **inline markup**.

The directive takes one required argument: a Sphinx document name without
its source extension. The target resolves relative to the consuming document;
a leading slash addresses the source root. URLs and section references
aren't accepted.

The title comes from the target document. If you provide a non-empty body,
docref parses it as RST and keeps it as authored content.

Options
-------

.. list-table::
   :header-rows: 1

   * - Option
     - Value and behavior
   * - ``:model:``
     - String model override for this automatic reference. Empty uses shared model.
   * - ``:style-title-prefix:``
     - String title prefix override; empty omits the prefix.
   * - ``:style-visit-link-text:``
     - String visit-link text override; empty leaves the link without visible text.
   * - ``:style-visit-link-class:``
     - Whitespace-separated CSS classes on the link paragraph; empty removes classes.
   * - ``:title-prefix:``, ``:visit-link-text:``, ``:visit-link-class:``
     - Deprecated aliases for the corresponding style options.
   * - ``:hash:``
     - Deprecated migration input. A non-empty hash treats a body as a legacy generated seed, not a permanent authored override.

Summary precedence
------------------

For an existing target:

1. Non-empty directive body, unless legacy ``:hash:`` is present.
2. Non-empty target ``html_meta`` description.
3. Valid generated cache entry, or a newly generated one when enabled.
4. Target's first paragraph (truncated after 100 characters with an ellipsis)
   when no generated result is available and generation is disabled.

A target without a paragraph falls back to ``See <target>.``.
A missing target warns and falls back locally before authored-summary selection.
Enabled generation failures raise build errors, not a silent fallback.

A legacy body with a recognized current legacy hash may seed a generated cache
record. Remove ``:hash:`` to retain its body permanently, or remove
the body and hash for the current automatic workflow.

Styling precedence
------------------

For each property, docref checks these values in order:

1. Canonical directive option.
2. Legacy directive option.
3. Explicit canonical configuration.
4. Explicit legacy configuration.
5. Canonical default.

A legacy directive option therefore still overrides a global canonical setting.
At the same scope, the canonical form wins even when it's empty.
Legacy use produces a warning. The defaults are in :doc:`configuration`.

Build report
------------

Every successful docref build writes ``sphinx-llm-summaries.json`` in
the output directory. Its format version is ``1``:

.. code-block:: json

   {
     "version": 1,
     "summaries": [
       {
         "target": "apples",
         "summary": "Plant and care for your first apple tree.",
         "origin": "html_meta",
         "consumers": [
           {"docname": "index", "source": "index.rst", "line": 9}
         ]
       }
     ]
   }

The origin is ``directive``, ``html_meta``, ``generated``
or ``fallback``. Generated entries also contain ``fingerprint``,
``provider`` and ``model``. Equivalent effective records are
grouped together with all their consuming locations.

The report leaves out endpoints, credential-variable names and key values.
It still contains summary text and source locations, which you should consider
before publishing it. It records the output of this build; it isn't the
persistent generation cache.
