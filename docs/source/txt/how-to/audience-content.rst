Tailor content to humans and agents
===================================

With ``sphinx_llm.txt`` enabled, use Sphinx's built-in
`only directive <https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#directive-only>`_
to give readers instructions appropriate to the output they are consuming.
For example, place these directives in a source page:

.. code-block:: rst

   .. only:: human

      Use the navigation menu to explore this documentation.

   .. only:: agent

      Fetch the Markdown page for machine-readable project context.

Build HTML or dirhtml and inspect that page in both HTML and generated Markdown.
The first paragraph appears only in HTML; the second appears only in the
extension's Markdown output. This page uses the same directives below, so you
can inspect the behavior in this site's rendered outputs too.

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

Native boolean expressions and nesting work. For example:

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

Use audience conditions for presentation, not access control. When you publish
both HTML and Markdown, both audiences' content is publicly retrievable.
Other extension consumers can inspect doctrees before conditional content is
filtered: docref summary generation uses target doctree text, while TXT
summary generation uses final Markdown. Page-level metadata can also be reused
across outputs. Do not rely on ``only`` to keep confidential material out of
provider input, generated descriptions, or a deployed site.
