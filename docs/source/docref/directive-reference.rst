Directive reference
===================

Syntax and target
-----------------

.. code-block:: rst

   .. docref:: /guide/apples
      :style-title-prefix: Related:
      :style-visit-link-text: Read the guide
      :style-visit-link-class: docref-link

      Optional authored summary with **inline markup**.

The single required argument is an extensionless Sphinx document name.
It is resolved relative to the consuming document; a leading slash addresses
the source root. It is not a URL or a section reference.
The title comes from the target document. A non-empty body is parsed as RST
and retained as authored content.

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

For each property: canonical directive option, legacy directive option,
explicit canonical configuration, explicit legacy configuration, then canonical
default. Thus a legacy directive option still overrides a global canonical
setting. Canonical wins over legacy at the same scope, even if empty.
Legacy use warns. Style defaults live in :doc:`configuration`.

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

Origins are ``directive``, ``html_meta``, ``generated``, or
``fallback``. Generated entries additionally contain
``fingerprint``, ``provider``, and ``model``.
Equivalent effective records are grouped with all consuming locations.
The report excludes endpoints, credential-variable names and key values.
It contains summary text and source locations, so consider that content when
publishing it. It is an output artifact, not the persistent generation cache.
