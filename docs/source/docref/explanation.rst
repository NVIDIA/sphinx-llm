How it works
============

Docref separates collecting references from choosing their summaries.
That lets it honor your authored text first and share automatic work between
references to the same page.

Collection and authored overrides
---------------------------------

When Sphinx parses a docref, it records a request and leaves a pending node
in the doctree. It doesn't contact a provider at that point. Each request
identifies the target page and the page that consumes the reference.

The reference also depends on its target's source file. If the target changes,
Sphinx can rewrite the consuming page. Purging and merging request data keeps
that state consistent across incremental builds and parallel readers.

At ``env-updated``, docref selects authored bodies and target metadata
before considering automatic requests. It groups those requests by target and
effective generation settings, so identical requests generate at most once
in that environment update.

At ``doctree-resolved``, the pending nodes become ordinary admonitions
and links. Generated prose stays in the build's state and output; it isn't
written back into your source files.

Persistent cache and invalidation
---------------------------------

Requests and selected summaries live in the Sphinx environment.
Generated records are also saved in the versioned JSON cache used by TXT.
Docref's keys start with ``docref:``, while TXT uses document names.

They share a cache file, not necessarily a generated result. Docref summarizes
the target's doctree text, while TXT summarizes final Markdown. Those inputs
can differ, so the two consumers keep separate records.

Both hash the complete input even though they send only a bounded prefix.
Their fingerprints include the endpoint, provider, model, prompt version,
reasoning effort, input limit, timeout and insecure-auth choice.
Docref also groups requests by effective settings, including the
credential-variable name, so that name affects its cache identity.
TXT's fingerprint doesn't include it. The API-key value never identifies
a summary, and neither the cache path nor the enabled switch identifies
its content.

A change beyond the transmitted prefix still invalidates that page's record.
When generation is off, docref can render a valid cached summary, but TXT
skips its summary cache and uses its content fallback.

Cache writes are atomic. An unreadable or incompatible file is ignored with
a warning, and docref prunes obsolete docref records when the corresponding
requests disappear. See :doc:`how-to/cache-ci` for a practical restore
and offline-build workflow.

Provider data flow and provenance
---------------------------------

For an enabled cache miss, docref takes the target's doctree text and truncates
it to the configured character limit. The client sends that text as a user
message with a one-sentence summary instruction and a system prompt.
It uses an OpenAI-compatible Chat Completions request with temperature zero
and reasoning effort ``none``.

The provider receives the content, selected model and any credential sent by
the client. The normal authored-summary workflow doesn't make that request.

The cache stores the returned text along with the target, fingerprint,
provider, model, prompt version and fingerprint, and generation settings.
The output report describes the effective summaries and their consumers,
including authored origins, but leaves out endpoint and credential details.

Both files still contain text derived from your documentation, so consider
that content when storing or publishing them. You should also review
generated wording: fixed request settings don't guarantee correctness or
identical output after a provider changes.
