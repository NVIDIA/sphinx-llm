How it works
============

The TXT extension uses Sphinx to render your pages twice: once for people
browsing HTML, and once for consumers that want Markdown. Keeping both builds
in Sphinx means your cross-references and other supported directives can be
resolved before the outputs are combined.

A second build, then a merge
----------------------------

When you start an HTML or dirhtml build, TXT starts a separate Markdown build.
The two normally run at the same time. If you choose sequential mode, the
Markdown build starts after HTML finishes and can reuse the primary doctrees.

The subprocess loads your configuration again and receives your command-line
overrides and unrelated custom tags. It selects its own builder and audience
tags, though, so it doesn't inherit HTML's human audience. Your extensions
therefore need to work in both builds.

Only the dedicated ``llms-markdown`` builder selects ``agent``;
every other builder selects ``human``. These tags are complementary,
even if you supplied conflicting tags on the command line or in
``conf.py``. The extension also clears cached condition results after
normalizing the tags, so conditions evaluated during configuration loading
don't keep an outdated result. Sphinx still evaluates the boolean expressions
itself. You can see examples in :doc:`how-to/audience-content`.

During the Markdown build, the builder records link targets. TXT then resolves
those links to the published layouts, copies the pages into your HTML output
directory and writes the indexes and optional full text. If two documents
would claim the same output path, it reports a collision instead of silently
overwriting one. This generation workflow doesn't run for a non-HTML primary
builder.

One document, several URLs
--------------------------

An append or replace layout changes how a Markdown URL relates to an HTML URL,
not which document it represents. With dirhtml, the HTML page can be addressed
with or without a trailing slash, which gives the append layout more than
one possible path.

We choose one canonical Markdown representation so the indexes don't list a
page twice. Each additional physical output still has links appropriate to
its own layout. Full text uses canonical page links because a concatenated
file doesn't have a single per-page layout.

Nested indexes follow published directories. That lets a consumer begin with
a subsection and then follow a link back to the complete index. HTML discovery
uses the nearest covering index, regardless of your theme. Changing the
toctree changes listing order, but doesn't restrict access to a page.

Descriptions and standards tradeoffs
------------------------------------

An authored description lets you decide how a page is introduced. If you
haven't written one, TXT can use a generated summary or an extract from the
Markdown. Generating descriptions is a separate choice from publishing
Markdown; you don't need an account or model for ordinary builds.

The `llms.txt v2 proposal <https://llmstxt.org/>`_ favors a small index
and retrievable Markdown pages. We support both append and replace layouts
to accommodate consumers with different URL conventions.
``llms-full.txt`` is an optional convenience, not a required v2
artifact. Publishing these files doesn't guarantee that a crawler or model
will use them, or improve your search ranking.

Limitations
-----------

A Markdown renderer can't reproduce every third-party directive or HTML widget.
Preserving an unknown node's source can retain useful context, but you should
still inspect important generated pages.

A full-text download may be too large for a consumer's context window, and an
index exclusion won't stop someone retrieving an individual page.
Generated descriptions can also be wrong, so review wording that matters to
your readers. The :doc:`troubleshooting guide <how-to/troubleshooting>`
covers the build and publishing checks you can make.
