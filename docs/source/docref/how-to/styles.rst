Style reference boxes
=====================

Choose site-wide wording and link classes in ``conf.py``:

.. code-block:: python

   llms_txt_docref_style_title_prefix = "Related:"
   llms_txt_docref_style_visit_link_text = "Visit page"
   llms_txt_docref_style_visit_link_class = "docref-link prominent"

For one box, set the corresponding directive options:

.. code-block:: rst

   .. docref:: /apples
      :style-title-prefix: More about
      :style-visit-link-text: Read the guide
      :style-visit-link-class: docref-link compact

      Learn to grow apples.

Separate CSS classes with whitespace. Add your stylesheet through Sphinx's
``html_css_files`` and ``html_static_path`` configuration; for example:

.. code-block:: css

   .docref-link a {
       font-weight: bold;
   }

The class is on the paragraph wrapping the link, not on the anchor.
An empty option removes its prefix, link text, or wrapper classes; the target
title still appears. See :doc:`../configuration` for canonical defaults
and migration from deprecated option names.
