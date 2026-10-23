Tailor content to humans and agents
===================================

People browsing your site may need navigation advice, while an agent may
need instructions for fetching a page. You can write both in one source file
and use Sphinx's
`only directive <https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#directive-only>`_
to select the appropriate text.

With ``sphinx_llm.txt`` enabled, add this to a page:

.. code-block:: rst

   .. only:: human

      Use the navigation menu to explore this documentation.

   .. only:: agent

      Fetch the Markdown page for machine-readable project context.

Build with HTML or dirhtml, then open that page in both HTML and generated
Markdown. You'll see the first paragraph in HTML and the second in Markdown.
This page includes the same live example below, so you can compare its two
outputs without creating a project first.

.. only:: human

   Use the navigation menu to explore this documentation.

.. only:: agent

   Fetch the Markdown page for machine-readable project context.

Choose audience or format conditions
------------------------------------

The extension sets exactly one audience tag at builder initialization:

.. list-table::
   :header-rows: 1

   * - Tag
     - When selected
   * - ``agent``
     - Only Sphinx LLM's dedicated ``llms-markdown`` builder: generated per-page Markdown, rendered custom ``llms.txt`` source content, and optional ``llms-full.txt``.
   * - ``human``
     - Every other builder, including ``html``, ``dirhtml``, standalone ``markdown``, and ``text``. Equivalent to ``not agent``.

Audience tags do not replace Sphinx's native builder/format tags.
``only:: html`` still selects HTML output. ``only:: markdown`` selects both
standalone Markdown and the extension's Markdown. To select standalone Markdown
only, use ``only:: markdown and human``. With ``sphinx_markdown_builder``
also enabled in ``extensions``, a standalone ``sphinx-build -b markdown``
build is human-facing, not agent-facing.
The tags are provided by TXT; docref alone does not add audience selection.

Combine conditions and custom tags
----------------------------------

You can combine audience conditions with your own tags or nest them inside
other conditions. For example, you might keep internal instructions out of
the public agent-facing text:

.. code-block:: rst

   .. only:: agent and not internal

      Use the published API rather than internal maintenance commands.

   .. only:: human

      .. only:: html

         Follow the links in the sidebar to find related pages.

Pass unrelated tags with Sphinx's ``-t`` option, or add them in ``conf.py``.
For example, ``sphinx-build -t internal -b html source build/internal``
preserves ``internal`` in the Markdown sub-build too. In that build the
``agent and not internal`` paragraph above is absent.

The audience tags are complementary: ``human and agent`` is always false,
and ``human or agent`` is always true. Explicit ``-t human``, ``-t agent``,
and corresponding ``conf.py`` audience tags are normalized to the actual
builder; they cannot override its audience. This normalization still happens
with ``llms_txt_enabled = False``. It does not change native builder/format
tags or unrelated custom tags.

Publishing and summary considerations
-------------------------------------

Audience conditions change how you present content; they don't make it
private. If you publish HTML and Markdown, someone can retrieve either version.

There's also a distinction when generating summaries. Docref uses target
doctree text, which can be read before conditional content is filtered, while
TXT uses final Markdown. Page metadata can be reused across outputs too.
Don't rely on ``only`` to keep confidential material out of provider
input, generated descriptions or your published site.
