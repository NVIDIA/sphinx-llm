Troubleshoot references and generation
======================================

A reference shows fallback text
-------------------------------

Check the build report's origin. With generation disabled, a missing cache
entry is expected to fall back. For generated text, confirm the shared enabled
switch, model and endpoint; installing the extra alone is insufficient.
An authored body or target metadata always takes priority, even when generation
is enabled. A ``:model:`` override does not itself enable generation.

The target cannot be loaded
---------------------------

Use a Sphinx document name without a source extension, relative to the
consuming document, or start with ``/`` for the source root.
The target must be part of the Sphinx build, not an external URL or a section
anchor. Missing targets warn and use a local fallback; do not suppress the
warning to repair a broken link. A warnings-as-errors build will catch it.

Provider or credential errors
-----------------------------

Verify the named API-key variable is present and the endpoint serves the chosen
model through Chat Completions. The key-variable setting is a name, not a key.
Check the generation extra is installed in the same Python environment as Sphinx.
For a plain-HTTP remote endpoint, use HTTPS rather than weakening the transport
guard. Empty/malformed provider responses and request failures fail the build;
they do not silently become authored summaries. No provider is contacted for
authored descriptions.

Stale summaries or unexpected requests
--------------------------------------

Remove legacy ``:hash:`` usage when migrating: remove the body for
automatic generation, or remove the hash for a permanent authored override.
Inspect the cache and report separately. A changed target, model, endpoint,
input limit or generation behavior can invalidate a record. Incompatible or
unreadable cache files warn and are ignored; enabled builds may regenerate.
If reproducibility matters, author the description instead of depending on a
model response. See :doc:`cache-ci` for offline CI behavior.
