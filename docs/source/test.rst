Testing page
============


.. docref:: apples

Docref presentation
===================

By default, a ``docref`` title is prefixed with ``See also:``, and its link
uses the text ``Read more >>`` and the CSS class ``visit-link``. Configure
these defaults in ``conf.py`` with:

.. code-block:: python

   llms_txt_docref_title_prefix = "Related:"
   llms_txt_docref_visit_link_text = "Visit page"
   llms_txt_docref_visit_link_class = "docref-link prominent"

Override any setting for an individual directive with ``:title-prefix:``,
``:visit-link-text:``, and ``:visit-link-class:``. Directive options take
precedence over the corresponding ``conf.py`` setting:

.. code-block:: rst

   .. docref:: apples
      :title-prefix: More about
      :visit-link-text: Read the guide
      :visit-link-class: docref-link compact

Set an option or configuration value to an empty string to render no title
prefix, link text, or CSS class. Multiple CSS classes may be separated by
whitespace.
