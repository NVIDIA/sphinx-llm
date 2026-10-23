Exclude pages from indexes
==========================

Keep generated API pages out of the indexes and optional full text:

.. code-block:: python

   llms_txt_exclude = ["reference/generated/**", "drafts/*"]

Patterns match extensionless Sphinx document names relative to the source root,
such as ``reference/generated/client``, not filesystem paths or regular
expressions. Use ``**`` across directories and ``*`` within one directory.

Rebuild and check the root and nested ``llms.txt`` lists. Per-page Markdown
and HTML are still published for excluded documents. This is an indexing
choice, not an access-control or confidential-content filter. To remove a
document from the build entirely, use Sphinx's own ``exclude_patterns``
and remove any references to it.
