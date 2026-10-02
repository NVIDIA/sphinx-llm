Documentation version context
=============================

Generated Markdown preserves documentation context by default. Each page
starts with one YAML frontmatter block containing non-empty string values
from Sphinx's configured docinfo, plus ``project`` and ``release``. Both
``version`` (short software version) and ``release`` (full software version)
remain strings, including leading zeroes and prerelease suffixes. No version
is inferred when these values are absent or empty.

Inspect the actual generated output:

* `This page as Markdown <docinfo.html.md>`_
* `The documentation home as Markdown <index.html.md>`_
* `A nested example as Markdown <nested/example.html.md>`_

These example docs explicitly configure ``version`` and ``release`` from the
installed sphinx-llm build, so the generated files identify the software they
describe. For your own project, configure the version of your documented
software in ``conf.py``:

.. code-block:: python

   project = "Example software"
   author = "Example Documentation Team"
   copyright = "2026, Example Documentation Team"
   version = "0.6"
   release = "0.6.01rc1"

The resulting Markdown begins with:

.. code-block:: yaml

   ---
   "author": "Example Documentation Team"
   "copyright": "2026, Example Documentation Team"
   "version": "0.6"
   "project": "Example software"
   "release": "0.6.01rc1"
   ---

Opt out in ``conf.py`` with ``llms_txt_docinfo = False``, or for one build
with ``sphinx-build -D llms_txt_docinfo=0``. The Boolean setting defaults to
``True`` and governs sphinx-llm's generated Markdown even when the upstream
``markdown_docinfo`` setting differs. Command-line overrides of
``llms_txt_docinfo``, ``version`` and ``release`` reach the Markdown sub-build.
Native ``sphinx-build -b markdown`` continues to use ``markdown_docinfo`` and
its upstream HTML metadata format. HTML output is unaffected.

Supported docinfo keys are ``author``, ``contact``, ``copyright``, ``date``,
``organization``, ``revision``, ``status``, ``version``, ``project`` and
``release``. Matching page-local metadata collected by Sphinx overrides global
values for that page only; an explicitly empty local value omits the key.
For example, put ``:author: Page author`` at the beginning of an RST document.
For Markdown input, matching string metadata exposed by the source parser in
Sphinx's page metadata uses the same rule. Arbitrary source frontmatter and
non-string metadata are not copied verbatim. Existing ``html_meta`` description
overrides still control the page's ``llms.txt`` description.

Values use JSON double-quoted strings, which are valid YAML scalars. Quotes,
Unicode and multiline text round-trip without changing numeric-looking
versions into numbers. Generated docinfo replaces the builder's generated
HTML metadata; authored body content is not rewritten.

Frontmatter remains on every published per-page Markdown variant and within
each page section of the optional ``llms-full.txt`` concatenation. That file
is a collection of Markdown pages, not one YAML document. Generated indexes
and authored ``llms_txt_override_source`` indexes omit generated frontmatter;
page titles and fallback descriptions come from the body.
