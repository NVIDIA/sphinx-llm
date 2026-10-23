Troubleshoot builds and publishing
==================================

Unsupported nodes
-----------------

If a third-party directive emits an unknown node, inspect its generated
Markdown and warning. The builder normally preserves unknown source as inline
code or a fenced RST block; this is not semantic rendering of the directive.

For known acceptable output, suppress only reviewed node classes:

.. code-block:: python

   llms_txt_suppress_unknown_node_warnings = ["caption", "desc_inline"]

Use exact, case-sensitive class names. Set
``llms_txt_preserve_unknown_nodes = False`` only if dropping their content
is acceptable. Suppression and preservation are independent; a strict build
can fail on relayed unknown-node warnings.

Parallel builds
---------------

If extensions depend on state that differs between simultaneous builds, try:

.. code-block:: python

   llms_txt_build_parallel = False

This delays the Markdown subprocess until HTML finishes and allows doctree
reuse; it is separate from Sphinx's ``-j`` reader/writer parallelism.
Inspect the logged subprocess output if Markdown is missing. A successful HTML
render alone is not proof that indexes were produced: verify ``llms.txt``
and representative Markdown files.

Subpath publishing and stale URLs
---------------------------------

Serve the complete output directory, including Markdown and nested indexes.
HTML discovery links are relative and work below a site prefix such as
``/projects/orchard/``. If you set ``markdown_http_base``, include that
prefix in the absolute base:

.. code-block:: python

   markdown_http_base = "https://docs.example.org/projects/orchard"

Do not confuse it with ``html_baseurl``: the latter is not the Markdown
URL override. Check a deep page's discovery links and follow links from both
its Markdown and nearest index. If modes or index settings changed, deploy a
clean output tree; old unselected files are not garbage-collected.
