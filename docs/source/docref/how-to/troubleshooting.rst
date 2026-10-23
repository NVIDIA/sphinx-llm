Troubleshoot references and generation
======================================

Start with ``sphinx-llm-summaries.json`` in your build directory.
Each entry's origin tells you whether docref used a directive body, page
metadata, a generated summary or fallback text. That often explains a result
that looks different from what you expected.

A reference shows fallback text
-------------------------------

If generation is off and there's no valid cached summary, fallback text is
expected. To generate text, check that you've enabled summaries and selected
a model and endpoint. Installing the extra alone isn't enough, and a
``:model:`` override doesn't enable generation.

If you expected a generated result but see authored text, check the directive
body and target metadata. Those take priority even when generation is enabled.

The target cannot be loaded
---------------------------

Check that the target is a Sphinx document name without its source extension.
It resolves relative to the consuming page unless it starts with ``/``,
which selects from the source root. The document must be included in the build;
a URL or section anchor isn't a valid target.

A missing target produces a warning and local fallback text.
Fix the target rather than suppressing the warning. A warnings-as-errors build
will help you catch the broken reference before publishing.

Provider or credential errors
-----------------------------

Check that the API-key variable named in your configuration is present and that
the endpoint serves the selected model through Chat Completions.
The key-variable setting is a name, not the key itself. Also check that the
generation extra is installed in the same Python environment as Sphinx.

For a remote plain-HTTP endpoint, prefer switching to HTTPS rather than
weakening the transport guard. Empty or malformed responses and request
failures stop the build; they don't silently turn into authored summaries.
Authored descriptions don't contact a provider.

Stale summaries or unexpected requests
--------------------------------------

If you're migrating legacy ``:hash:`` directives, remove the body for
automatic generation, or remove the hash to keep a permanent authored override.
Inspect the cache separately from the report so you can distinguish persisted
results from the text selected for this build.

A changed target, model, endpoint, input limit or generation behavior can
invalidate a record. An unreadable or incompatible cache also causes a warning
and is ignored, so an enabled build may make new requests. For text that
shouldn't depend on a provider response, use an authored description.
The :doc:`cache guide <cache-ci>` covers offline CI in more detail.
