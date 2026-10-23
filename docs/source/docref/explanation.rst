How it works
============

Collection and authored overrides
---------------------------------

Parsing a docref creates a pending node and a request in the Sphinx environment,
not a provider call. Each request records its consuming document and target.
Dependencies on target source files trigger consumer rewrites when targets
change. Environment purge and merge support incremental and parallel readers.

At ``env-updated``, docref selects authored bodies and target metadata
before grouping automatic requests by target and effective generation settings.
Identical requests generate at most once in that environment update. At
``doctree-resolved``, pending nodes become ordinary admonitions and links.
Source files are never rewritten with generated prose.

Persistent cache and invalidation
---------------------------------

Docref stores requests and effective state in the Sphinx environment and
generated records in the same versioned JSON cache file used by TXT.
Docref keys have a ``docref:`` prefix; TXT uses docnames. Sharing a file
does not mean the two consumers reuse the same generated record: docref
summarizes target doctree text, while TXT summarizes final Markdown.

Both hash the complete input, even though only a bounded prefix is sent.
Fingerprints include endpoint, provider, model, prompt version, reasoning
effort, input limit, timeout and insecure-auth choice. Docref also groups by
effective settings including credential-variable name; that name affects its
cache identity, while the API-key value never does. TXT's fingerprint does
not include the credential-variable name. The cache path and enabled switch
do not identify the summary content.

Content changes outside the transmitted prefix still invalidate the record.
A valid docref cache entry can be rendered with generation disabled;
TXT skips its summary cache when generation is disabled. Persistent writes are
atomic. Bad or incompatible cache files are ignored with warnings. Docref
prunes obsolete docref records as requests disappear.
See :doc:`how-to/cache-ci` for restore and offline workflows.

Provider data flow and provenance
---------------------------------

For an enabled cache miss, target doctree text is truncated to the configured
character limit and sent as a user message with a one-sentence summary
instruction, plus a system prompt. The OpenAI-compatible client makes a Chat
Completions request with temperature zero and reasoning effort ``none``.
The provider receives that content, selected model and any credential sent
by the client; the normal offline authored path makes no such request.

The returned text is stored with target, fingerprint, provider, model,
prompt version/fingerprint, and generation settings in the docref cache.
The output report records effective summaries and consumers, including authored
origins, but omits endpoint and credential details. Caches and reports still
contain documentation-derived text and must be handled accordingly.
Review generated wording: deterministic request settings cannot guarantee
correctness or identical output across provider changes.
