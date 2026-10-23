Exclude pages from indexes
==========================

You may want to publish generated API pages without listing every one in
``llms.txt``. Add their document names to the exclusion patterns in
your ``conf.py``:

.. code-block:: python

   llms_txt_exclude = ["reference/generated/**", "drafts/*"]

These patterns match Sphinx document names such as
``reference/generated/client``, without a source extension.
They aren't regular expressions or filesystem paths. Use ``*`` to match
within one directory and ``**`` to match across directories.

After rebuilding, check the root and nested ``llms.txt`` files.
The matching pages won't appear in those lists or in ``llms-full.txt``.
Their HTML and individual Markdown files are still available.

Excluding a page from an index doesn't make it private. If you don't want a
document in the published output at all, use Sphinx's ``exclude_patterns``
and remove references to that document from your other pages.
