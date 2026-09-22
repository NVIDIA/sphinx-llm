# Issue #159: single-read, concurrent-writer proof of concept

This branch is an intentionally narrow proof of concept for
[issue #159](https://github.com/NVIDIA/sphinx-llm/issues/159). It validates that
one Sphinx application can finish reading and finalizing its environment, then
fork an isolated Markdown writer while the original process writes HTML. It is
not a production-ready implementation.

## Running the experiment

The experimental path is opt-in:

```python
# conf.py
llms_txt_experimental_shared_doctrees = True
```

Run the focused evidence:

```bash
uv run pytest -q src/sphinx_llm/tests/test_shared_doctree_poc.py
```

The existing `llms_txt_build_parallel` modes are unchanged when the experimental
option is false.

## Architecture and handoff boundary

Sphinx 9.1's `Builder.build()` performs these operations in order:

1. `Builder.read()`, including source parsing and executable directives;
2. `env-updated`, parallel-reader merges, and dependent-document calculation;
3. environment pickling and the consistency check;
4. `Builder.write()` and `Builder.finish()`.

At `builder-inited`, the POC replaces only the primary builder instance's bound
`write` method. When Sphinx reaches that method, the POC deserializes every
prepared doctree to fail early on missing or corrupt state and emits
`llms-shared-doctrees-ready`. It then uses the POSIX `fork` start method.

The child inherits a copy-on-write snapshot of the finalized application,
environment, serialized doctree cache, config, tags, registry, and event
listeners. In the child only, the code constructs `SphinxLlmMarkdownBuilder`,
points it at a staging output directory, and directly calls `Builder.write()`
and `Builder.finish()` for all documents. It never calls `Sphinx.build()`, any
`build_*` method, `Builder.build()`, freshness discovery, or `Builder.read()`.
The parent immediately calls the original primary `write` method. The two
writers therefore can run concurrently.

The child always rewrites all Markdown from prepared doctrees. This is a
deliberate POC tradeoff: it avoids having to make two builders agree on an
incremental document selection while still avoiding source reads and execution.

## Evidence and distinct claims

The integration fixture contains six real read-time directives. Each obtains an
exclusive `fcntl` lock and appends its document name and generated ordinal to a
durable counter. It separately records `source-read`, `env-updated`, snapshot,
writer start/overlap/finish/failure/exit, and process IDs. POC-owned writer
lifecycle events are registered before the probe extension loads, so the same
instrumentation works on every supported Sphinx release and fires immediately
before each real writer call.

- **Exactly-once evaluation:** the established independent subprocess mode
  records twelve evaluations and twelve source reads for six documents. The POC
  records six evaluations and six source reads total. Both HTML and Markdown
  contain the same per-document generated value.
- **No secondary reread:** only the primary reader records `source-read`. The
  child entry point calls the Markdown builder's writing methods directly.
  Corrupting a prepared doctree causes an explicit failure before the child
  starts, with six source reads total and no fallback build.
- **Mutation isolation:** an adversarial `doctree-resolved` listener mutates the
  child environment and doctree. Markdown contains the child-only mutation;
  HTML contains the parent-only mutation and observes no child environment
  attribute. This is copy-on-write process isolation, not thread safety.
- **Writer overlap:** both processes touch a role-specific start marker and
  block on the other marker before either may continue. The trace then records
  overlap and completion for both roles. This is a synchronization barrier, not
  a sleep-based timing assertion.

The matrix covers `html` and `dirhtml`, serial reading and requested Sphinx
reader parallelism of two, titles, body text, internal links, HTML-tag-conditioned
content, metadata descriptions, nested paths, `llms.txt`, and `llms-full.txt`.
Six documents ensure Sphinx 7+ enters its parallel reader path; worker PID data
is diagnostic rather than an assertion because scheduling varies by release.
Sphinx 5.1 runs the requested-parallel case serially because
`sphinx-markdown-builder` 0.6.8 does not declare parallel-read safety. Two
independent clean runs produce byte-identical Markdown and llms text files.

The incremental scenario records:

- clean build: six evaluations;
- unchanged build: zero additional evaluations, with both writers still using
  the finalized cached environment;
- one changed source: one additional evaluation, updated HTML and Markdown, and
  an unchanged cached page still present in Markdown.

Failure probes show:

- a primary read error starts no secondary writer;
- a corrupt doctree fails before the fork and does not reread;
- a Markdown writer error produces a nonzero Sphinx status, removes staging,
  and removes previously published extension-owned Markdown and sitemap files.
  The trace independently records child start, child exception type, and the
  nonzero reaped child exit code;
- a primary writer error terminates and reaps a child held at a barrier, with
  bounded cleanup through the existing ten-second terminate/kill path.

## Shared and isolated state

- **Python environment and doctrees:** copy-on-write after finalization;
  resolved doctrees are process-local. Native libraries or extension-managed
  external resources may not be fork-safe.
- **Pickled environment and doctree files:** the parent finishes writes before
  fork; serialized doctrees are validated and cached before fork; writers only
  read. No filesystem permission enforces read-only access against a hostile
  extension.
- **Output:** HTML uses the primary directory; Markdown uses staging and is
  copied only after child success. Removal of documents between incremental
  builds needs a durable ownership manifest.
- **Config and tags:** inherited, then child-only Markdown tags are added.
  Extensions that inspect process-global state may make undocumented
  assumptions.
- **Registry and events:** inherited at fork; child mutations cannot leak back.
  Hooks may perform non-idempotent external side effects during both writers.
- **Logging and warnings:** child exceptions are captured and its exit code is
  propagated. Warning counts and warning-as-error semantics are not yet
  reliably relayed.
- **Cleanup:** the parent owns joining, termination, staging removal, and
  publication. SIGINT/SIGTERM behavior has not been independently exercised.

## Limitations and production work

- The POC requires the POSIX `fork` multiprocessing start method. Windows and
  spawn-only platforms are explicitly rejected. Forking applications that have
  initialized threads, GPU runtimes, network clients, or other native state can
  itself be unsafe; a production design needs a documented compatibility model.
- The focused experiment is exercised on Sphinx 5.1, 6.x, 7.4, 8.x, and 9.x
  on Linux.
  The full supported matrix remains CI evidence rather than a portability
  guarantee, and future Sphinx lifecycle compatibility remains a release
  concern.
- Secondary warnings are not yet integrated into the primary application's
  warning count or `-W` behavior. Structured child diagnostics are needed.
- Interrupt and external termination handling is not tested. The existing
  exception cleanup is bounded, but signal forwarding should be designed and
  tested.
- Every Markdown page is rewritten on incremental builds. Production code
  should define selection semantics and retain an ownership manifest so outputs
  for removed documents are deleted safely.
- The private bound-method interception is suitable for an experiment, not a
  stable extension API. Productionization should seek a supported Sphinx phase
  boundary or upstream hook.
- The child has a memory-efficient copy-on-write snapshot in the common case,
  but resolving many doctrees can dirty substantial memory. Large-project memory
  and disk benchmarks are needed.
- On Sphinx releases that provide it, extensions' `write-started` hooks run once
  per writer; `doctree-resolved` hooks do so on every supported release.
  Compatibility needs auditing for hooks with external side effects, global
  registries, file writes, or assumptions that `app.builder` never changes.
- The directly constructed child builder does not receive Sphinx's normal
  `builder-inited` event and retains the phase inherited from the primary
  application. Production code must either reproduce the required lifecycle or
  explicitly define and test a narrower extension compatibility contract.
- `llms_txt_experimental_shared_doctrees` is intentionally documented only in
  this report and should not be advertised as a supported public option.

The experiment supports the issue comment's hypothesis on this platform: a
read-only-in-practice, copy-on-write snapshot is sufficient to avoid duplicate
execution while retaining writer concurrency. It does not establish that a
portable or generally extension-safe production implementation should use
`fork`.
