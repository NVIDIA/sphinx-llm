.. sphinx-llm documentation master file, created by
   sphinx-quickstart on Thu Nov 28 09:52:02 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to sphinx-llm's documentation!
======================================

.. Keep this toctree intentionally non-alphabetical so the test suite exercises
   generated navigation ordering.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   test
   apples
   meta_example
   nested/index


Doctree cache reuse
===================

Sequential Markdown builds (``llms_txt_build_parallel = False``) reuse the
primary HTML build's doctree cache by default to avoid parsing sources twice.
If an extension applies builder-specific transformations during
``doctree-read``, disable reuse in ``conf.py``::

   llms_txt_reuse_doctrees = False

``llms_txt_reuse_doctrees`` is a boolean option that defaults to ``True``.
When disabled, Markdown uses a separate cache inside its temporary build
directory, which is removed after the build. The primary build's cache is left
unchanged, at the cost of parsing sources again. Parallel builds always use
a separate cache, regardless of this setting. Generated page-summary caching
is not controlled by this option.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
