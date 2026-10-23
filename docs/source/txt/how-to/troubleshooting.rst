Troubleshoot builds and publishing
==================================

If your HTML looks right but the Markdown is missing or incomplete, start by
checking the build log and one affected Markdown file. The checks below help
you distinguish rendering problems from publishing problems.

Unsupported nodes
-----------------

A third-party directive may create a node the Markdown builder doesn't
understand. By default, the builder preserves the node's source as inline
code or a fenced RST block. That keeps some context, but isn't the same as
rendering the directive.

Once you've reviewed the output and decided it's useful, you can suppress
warnings for just those node classes:

.. code-block:: python

   llms_txt_suppress_unknown_node_warnings = ["caption", "desc_inline"]

Use the exact, case-sensitive class names from the warnings. Suppressing a
warning doesn't change the output. If you instead want to drop unknown-node
content, set ``llms_txt_preserve_unknown_nodes = False``, but check
that you aren't losing information readers need. Unknown-node warnings can
still fail a strict build when they are relayed from the Markdown subprocess.

Parallel builds
---------------

Some extensions depend on state that doesn't work well in simultaneous builds.
To check whether that affects your project, try this in ``conf.py``:

.. code-block:: python

   llms_txt_build_parallel = False

The Markdown subprocess will start after HTML finishes and can reuse the
doctrees. This is separate from Sphinx's ``-j`` option, which controls
parallel readers and writers.

If Markdown is still missing, inspect the logged subprocess output.
A completed HTML page doesn't by itself tell you whether the Markdown build
succeeded, so check for ``llms.txt`` and a representative Markdown file
before deploying.

Subpath publishing and stale URLs
---------------------------------

Publish the whole output directory, including Markdown and nested indexes.
The HTML discovery links are relative, so they work when your site lives
under a prefix such as ``/projects/orchard/``.

If you need absolute Markdown URLs, include the same prefix in your base:

.. code-block:: python

   markdown_http_base = "https://docs.example.org/projects/orchard"

This is different from Sphinx's ``html_baseurl``; that setting doesn't
override the Markdown URLs. After publishing, follow a deep page's discovery
links and then a link from its nearest index.

If you've changed suffix modes or index settings, deploy a clean output
directory. Files that the new mode doesn't select are left alone, so an
old file can otherwise make a stale URL appear to work.
