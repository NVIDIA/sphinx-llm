Configuration
=============

Once you've enabled ``sphinx_llm.docref`` in ``extensions``,
you can configure shared summary generation and the appearance of reference
boxes. Docref loads the summary settings itself; you don't need TXT.

Summary settings
----------------

Use the :ref:`shared-summary-settings` reference for summary option
names, types, defaults, environment overrides and precedence.
The ``llms_txt_summary_*`` names apply to docref too.

A directive's ``:model:`` option selects a model for that automatic
reference after shared model resolution. It doesn't turn generation on.

Style settings
--------------

You can set site-wide styles in ``conf.py`` or with Sphinx's
``-D`` option. Styling doesn't have dedicated environment overrides.
For per-reference changes and a CSS example, see :doc:`how-to/styles`.

.. list-table::
   :header-rows: 1

   * - Name
     - Purpose
     - Type
     - Default
   * - ``llms_txt_docref_style_title_prefix``
     - Prefix before the target document title; empty omits the prefix.
     - str
     - ``"See also:"``
   * - ``llms_txt_docref_style_visit_link_text``
     - Visit link text; empty renders an empty-text link.
     - str
     - ``"Read more >>"``
   * - ``llms_txt_docref_style_visit_link_class``
     - Whitespace-separated CSS classes on the link's wrapping paragraph; empty means none.
     - str
     - ``"visit-link"``

Deprecated configuration
------------------------

``llms_txt_docref_title_prefix``,
``llms_txt_docref_visit_link_text``, and
``llms_txt_docref_visit_link_class`` are deprecated str-or-None aliases
with default ``None``. Replace them with the corresponding
``llms_txt_docref_style_*`` name. An explicitly configured canonical
value wins over a legacy configuration value, including an empty string.
Use of legacy configuration warns.

``sphinx_llm_options`` remains registered as a dictionary (default
``{}``) for compatibility, but docref does not read it for model or
summary configuration. Migrate old model settings to the shared reference.
