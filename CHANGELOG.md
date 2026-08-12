# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Changed

- Reworked the `docref` directive around Sphinx's environment lifecycle,
  including incremental purge, parallel merge, deferred generation, and
  doctree resolution.
- Made authored directive bodies and page-level `html_meta` descriptions
  explicit overrides, followed by generated cache entries and local fallback
  content.
- Reused the `llms_txt_summary_*` configuration, provider safeguards, and
  versioned JSON cache for both `docref` and generated `llms.txt` page
  descriptions.
- Deduplicated matching target/settings requests, added complete-content cache
  invalidation, and pruned stale namespaced `docref` cache records.
- Added the inspectable `sphinx-llm-summaries.json` artifact with effective
  summaries, provenance, and consumers while excluding credentials and
  endpoint details.
- Added coverage for missing targets, legacy Docutils metadata nodes, builders
  without relative URIs, Sphinx 6 incremental doctrees, and provider-error
  redaction.

### Migration

The deprecated `:hash:` option remains accepted for existing `docref`
directives. Matching pre-#115 MD5 hashes and PR #115 setting-aware hashes seed
the shared cache from the existing body and avoid immediate regeneration.

- Remove the body and `:hash:` to return to automatic generation.
- Remove only `:hash:` to keep the body as permanent authored content.
