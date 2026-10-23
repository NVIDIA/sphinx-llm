Writing style
=============

Our documentation should help you get something working, understand the result
and choose a sensible next step. Write as if you're explaining the project
to a colleague who knows Python but hasn't used sphinx-llm before.

Use this guide when you write or edit the site or README. The
:doc:`contributor guide <../project/contributing>` covers the build tools
and pull-request evidence.

Write to the reader
-------------------

Address the reader as **you**. Use active sentences that name the action
and its result: "Add the extension to your configuration" is clearer than
"Extension configuration must be performed." You can use **we** when
explaining a project choice or walking through an example together.
Avoid a vague "we" when it's the reader who needs to run a command.

Use natural contractions such as "you'll" and "doesn't" where they fit.
The tone should be friendly and matter-of-fact, without a sales pitch or a
running commentary on how easy everything is. Give a necessary term a short
explanation when it first appears. For example, introduce a canonical URL as
the preferred representation of a page before discussing how indexes use it.

Prefer short, connected paragraphs to a series of commands with no context.
A useful paragraph often answers one question: what are we trying to do,
what should you change, or what should you see afterwards?
Use lists for choices and ordered steps, not as a replacement for an explanation.

Before and after
~~~~~~~~~~~~~~~~

A clipped instruction might read:

   Set the suffix mode. Rebuild. Check canonical output.

Give the reader a reason and something concrete to inspect instead:

   If your consumers expect ``guide.md`` rather than ``guide.html.md``,
   set ``llms_txt_suffix_mode = "replace"`` in ``conf.py``.
   After rebuilding with the HTML builder, open ``guide.md`` and check
   that the index links to it.

This isn't a reason to make every sentence longer. Keep a reference entry
compact, while giving a task guide enough context to use that reference.

Put code in a small story
-------------------------

Introduce a snippet with the task it solves and say where it belongs.
Follow it with the expected result, not another unrelated snippet.

For example, this leaves several questions unanswered:

.. code-block:: python

   llms_txt_full_build = True

A useful guide connects the setting to the output:

   To offer a single download of your included pages, add this to
   ``conf.py``:

.. code-block:: python

   llms_txt_full_build = True

Then explain what to inspect:

   After rebuilding, open ``llms-full.txt`` in the output directory.
   The generated root index also includes a link to it.

Keep examples small enough to run as written. We use an Orchard project with
``index.rst`` and ``apples.rst`` for introductory examples so readers
can move between pages without learning a new scenario each time.
A different example is fine when it makes the task clearer.

State the working directory, filenames, required extensions and dependencies.
Use ``console`` blocks for shell commands without prompt characters,
``python`` for configuration, and ``rst`` for source directives.
Quote package extras in shell commands, as in
``python -m pip install "sphinx-llm[gen]"``.

Use complete local examples for the default path. If an optional example
requires a provider, running server, model or credential, say so before the
reader tries it. Use obvious example endpoints and explain which values
need replacing. Keep credentials out of source files and example output.

Choose the right page shape
---------------------------

Overview
~~~~~~~~

Start with what the extension helps the reader do. Show a minimal setup
and explain the result, then link to a tutorial or task guide.
Leave the full inventory of settings and exceptional cases to the references.

Tutorial
~~~~~~~~

Guide a reader from a known starting point to a working result.
Name the prerequisites, create the files in order and show how to build.
After each important action, explain what changed and how to check it.
Finish with a small number of relevant next steps.

Keep the main path runnable without a model or network service.
For docref, show an authored summary before optional generation.
Avoid branching into every supported configuration while the reader is still
trying to complete a first build.

How-to guide
~~~~~~~~~~~~

Use a task heading such as "Exclude pages from indexes".
Assume the reader has a project and state any extra prerequisite.
Introduce the reason for the change, show the smallest useful example and
explain how to verify it. Put consequences next to the step they affect:
an indexing exclusion still publishes the page, for example.

For troubleshooting, start with a symptom or observation, then explain what
to inspect and what the result means. Help the reader distinguish a missing
file, a stale cache and a provider failure rather than offering a list of
unrelated settings.

Reference
~~~~~~~~~

Make exact facts easy to find. Keep setting names, types, defaults and basic
behavior in the authoritative configuration tables, and link to them from
guides rather than repeating their definitions. Keep directive options,
precedence rules, report fields and output paths precise and complete.

Reference prose doesn't need to sound conversational in every cell.
Use full sentences around tables to explain their scope, and spell out
important distinctions such as an empty value versus an omitted option.

Explanation
~~~~~~~~~~~

Start with the question the design answers, then connect the decisions and
their consequences. For example, explain why two URL layouts can represent
one page before describing canonical links. Use implementation terms only
when they help explain behavior, such as why TXT and docref don't reuse the
same generated record.

Link to a guide when a reader needs steps to apply the idea.
An explanation should clarify the model, not repeat a tutorial or an option table.

Use consistent terms and links
------------------------------

Use **sphinx-llm** for the package, ``sphinx_llm.txt`` and
``sphinx_llm.docref`` for extension names, and **TXT** and **docref**
as short forms once the context is clear. Write **Markdown** and
**reStructuredText** consistently. Distinguish a source document name, a
published file path and a URL when their layouts differ.

Call text **authored** when a person or source file supplies it, **generated**
when a provider produced it, and **fallback** when the extension derives it
without generation. Don't describe a cache hit as a new provider request.
Keep the human/agent audience terms separate from builder/format tags.

Use Sphinx ``:doc:`` and ``:ref:`` links inside the site, with
descriptive labels at the point a reader needs them. Preserve existing URLs
and useful anchors when reorganizing pages. Use canonical hosted URLs in
README, since its links also need to work on GitHub and PyPI.

The site is the source of truth for detailed usage. README should preview the
features, show a short starting example and link to the relevant pages.
Keep contributor and release instructions discoverable from Maintainers,
rather than growing a second handbook in README.

Use admonitions sparingly
-------------------------

Put ordinary context in paragraphs. Use a note when it explains a surprising
detail, or a warning when the next action has a meaningful consequence,
such as sending documentation to an external provider.
Explain the consequence and the practical choice the reader can make.
Repeated warning boxes can hide the one that matters.

Verify the reader's path
------------------------

Run tutorials and representative task examples from their stated starting
point. Check both the command and the promised output; an HTML build alone
doesn't prove that a Markdown file or summary report exists.
For optional provider examples, record whether you used a real provider,
a local test endpoint or only checked the configuration.

Build with warnings treated as errors. Check HTML and dirhtml when paths,
links or navigation matter, and inspect the Markdown output too.
Follow links and anchors, including README links to the generated pages.
Check root and deep pages at desktop and mobile widths: the extension
sections should remain available, and Maintainers should be easy to find.

For a pull request, follow the repository's
`making-a-pr guidance <https://github.com/NVIDIA/sphinx-llm/blob/main/.agents/skills/making-a-pr/SKILL.md>`_
for live previews and screenshots. Say which evidence is local, which is
from the published preview and what remains unverified.

Review checklist
----------------

Before asking someone to review a documentation change, check that:

* The opening tells a reader what they can do and where to start.
* Each example names its files and prerequisites, and explains the result.
* Tutorials have a working main path; optional provider steps are clearly separate.
* Headings describe a task or a useful question rather than a vague category.
* Terms, links and examples are consistent across related pages.
* Settings, defaults, precedence, output paths and data-handling claims match the code.
* Detailed facts have one authoritative home, with links from the other pages.
* Existing contributor/release URLs and README targets still resolve.
* Strict builds, representative examples and responsive navigation checks pass,
  or any remaining gap is stated with its cause.
