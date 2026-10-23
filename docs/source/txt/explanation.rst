How it works
============

A second build, then a merge
----------------------------

At builder initialization, TXT starts a separate Sphinx Markdown build for
html or dirhtml. By default it overlaps the HTML build; sequential mode starts
after HTML finishes and can reuse the primary doctree directory.
The subprocess reloads the same configuration, receives command-line overrides
and custom tags, and sets its own Markdown builder tags. Extensions in
``conf.py`` therefore need to work in both builds.

The Markdown builder records link targets. During merging, TXT resolves them
to published layouts, copies per-page outputs, optionally concatenates full
text, and writes root and directory-scoped indexes. It detects output
collisions rather than silently choosing a document. A non-HTML primary builder
does not run this workflow.

One document, several URLs
--------------------------

Append and replace describe transformations of an HTML URL, not different page
contents. In dirhtml, a page can be addressed with or without a trailing slash;
these forms lead to distinct Markdown paths. A canonical representation makes
retrieval predictable without duplicating index entries. Alternative outputs
retain layout-appropriate links, while full text links to canonical pages.

Nested indexes follow published directory boundaries. An agent can start with
a subsection and retain a route to the complete index. HTML discovery chooses
the nearest covering index, independent of the HTML theme. Toctree ordering
is not an access policy.

Descriptions and standards tradeoffs
------------------------------------

An authored description is editorial metadata, not generated output. Without
one, TXT can use a generated summary or a short Markdown-content fallback.
Provider work is optional and separate from publishing machine-readable docs.

The `llms.txt v2 proposal <https://llmstxt.org/>`_ favors an index and
retrievable Markdown pages. sphinx-llm supports both layouts for compatibility
with clients. ``llms-full.txt`` is an optional sphinx-llm convenience,
not a required v2 artifact. Publishing these files does not guarantee crawler
adoption, search ranking, or a model's use of your content.

Limitations
-----------

The renderer does not implement every third-party node or directive.
Preserving unknown source avoids silently losing all context, but cannot make
it equivalent to an HTML widget. Inspect important generated pages.
Large full-text files may exceed a consumer's context window.
Index exclusion does not prevent access to a generated page.
Generated descriptions can be incorrect and require review.
See :doc:`how-to/troubleshooting` for operational checks.
