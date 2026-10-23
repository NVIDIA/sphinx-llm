Style reference boxes
=====================

You can change how docref introduces a page and how it labels the visit link.
To use the same wording across your site, add these settings to ``conf.py``:

.. code-block:: python

   llms_txt_docref_style_title_prefix = "Related:"
   llms_txt_docref_style_visit_link_text = "Visit page"
   llms_txt_docref_style_visit_link_class = "docref-link prominent"

After rebuilding, each box uses the new prefix and link text. For a single
reference, you can set the matching directive options instead:

.. code-block:: rst

   .. docref:: /apples
      :style-title-prefix: More about
      :style-visit-link-text: Read the guide
      :style-visit-link-class: docref-link compact

      Learn to grow apples.

The classes belong to the paragraph around the link, rather than the anchor
itself. For example, this CSS makes links in a ``docref-link``
paragraph bold:

.. code-block:: css

   .docref-link a {
       font-weight: bold;
   }

Add the stylesheet using Sphinx's ``html_css_files`` and
``html_static_path``. You can separate multiple classes with whitespace.

To omit a prefix or class, set that option to an empty string.
An empty link-text option leaves a link without visible text, so choose that
only if you intend it. The target title still appears.
See :doc:`../configuration` for the defaults and migration from deprecated
styling names.
