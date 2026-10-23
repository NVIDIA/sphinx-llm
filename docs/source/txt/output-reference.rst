Output reference
================

Use this reference to check the files and URLs you should see after a build.
For help choosing a layout, see :doc:`how-to/suffix-urls`.

Published Markdown paths
------------------------

The paths below are relative to your HTML output directory. A regular
``page.rst`` document produces the following Markdown files:

.. list-table::
   :header-rows: 1

   * - Builder / HTML
     - append
     - replace
     - auto
   * - html: ``page.html``
     - ``page.html.md``
     - ``page.md``
     - Both
   * - dirhtml: ``page/index.html`` (URL ``page/``)
     - ``page/index.html.md`` and ``page.md``
     - ``page/index.md``
     - All three

For root ``index.rst``, both builders publish ``index.html.md``
in append mode, ``index.md`` in replace mode, and both in auto mode.
There is no extra no-slash path for the root.

For ``guide/index.rst``:

.. list-table::
   :header-rows: 1

   * - Builder / HTML
     - append
     - replace
   * - html: ``guide/index.html``
     - ``guide/index.html.md``
     - ``guide/index.md``
   * - dirhtml: ``guide/index.html`` (URL ``guide/``)
     - ``guide/index.html.md`` and ``guide.md``
     - ``guide/index.md``

Auto publishes the union. ``both`` is an exact alias for auto.
Legacy ``file-suffix`` publishes only the ``.html.md`` path for
either builder. Legacy ``url-suffix`` publishes that same path for
html; for dirhtml it publishes only ``page.md`` (or ``guide.md``
for the nested index, ``index.md`` at root).

Append and auto select the ``.html.md`` path as canonical; replace
selects the path replacing ``.html``. Compatibility modes select
their only path. Indexes, full text, canonical Markdown links, and HTML discovery
agree on this choice. Each alternative physical Markdown output rewrites its
internal links to that output's layout.

Audience of generated content
-----------------------------

Per-page Markdown, rendered custom root-index source content, and optional full
text use the agent audience. HTML and dirhtml use the human audience.
Automatically generated index descriptions may come from page metadata or
content-derived/generated summaries; an audience condition is not a privacy
filter for metadata or provider inputs. See :doc:`how-to/audience-content`
for tag rules and :doc:`../docref/explanation` for summary data flow.

Index contents
--------------

The generated root ``llms.txt`` introduces your project and lists the
included pages. Its structure is:

* A project H1 and blockquoted project description.
* Copyright text when configured.
* A Pages H2 with Markdown links to included documents and short descriptions.
  Documents follow the global toctree order, then orphan document names.
* An Optional section linking ``llms-full.txt`` only when generated.

Nested ``llms.txt`` files contain the same project context, a
"Pages in this subsection" list for the directory and descendants, and an
Optional link to the top-level index. Every ancestor directory implied by
included published HTML paths gets a scoped index. Directories containing no
included descendants do not get one.

Full text contains one included canonical document at a time, prefixed with
an H1 naming its output path. Root is first, followed by lexicographic output
paths. This differs from the index's toctree order. Exclusions affect indexes
and full text, not per-page Markdown.

Links are relative to each index by default. ``markdown_http_base``
makes index destinations absolute. Titles and descriptions are serialized as
single-line Markdown-safe text; descriptions have markup stripped.
A custom root override replaces root contents, not nested indexes.

HTML discovery
--------------

Every source-backed HTML page receives head links such as:

.. code-block:: html

   <link rel="alternate" type="text/markdown" href="page.html.md">
   <link rel="describedby" href="llms.txt">

For ``guide/page/`` in dirhtml, the alternate is ``index.html.md``
in append/auto, ``index.md`` in replace, or ``../page.md`` in
legacy url-suffix. Links are relative to the published HTML URL, including
below a site prefix. Describedby selects the deepest generated covering index;
root-only mode selects root. Search and general-index pages have no Markdown
representation and receive neither link.

File ownership
--------------

The extension overwrites the Markdown paths selected for the current build
and leaves other existing files alone, including artifacts from earlier modes.
It removes the temporary ``_markdown_build`` directory after merging.
When you deploy, publish the whole output tree so the Markdown and index URLs
remain available alongside HTML.
