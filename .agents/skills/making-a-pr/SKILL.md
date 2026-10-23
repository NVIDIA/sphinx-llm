---
name: making-a-pr
description: Use when creating or updating a sphinx-llm pull request.
---

# Making a PR

## Prepare the evidence

1. Inspect the full diff against the PR's base branch. Identify the change's
   value to the project, the detailed changes, and whether extension behavior
   or rendered appearance changes.
   **Done when:** the summary and change list account for the full PR scope.
2. For changes to extension functionality, add or update an example in the
   main documentation under `docs/source/` that actually uses the affected
   functionality. Configuration or API reference text alone is insufficient;
   reviewers should be able to see the behavior demonstrated in the docs.
   Build the documentation to check the example.
   **Done when:** the documentation demonstrates the changed behavior and the
   build succeeds, or a build blocker is explicitly recorded.
3. After the PR exists, infer its Read the Docs preview links from the PR
   number, the project's preview URL pattern, and the changed documentation
   paths. Add these links in a follow-up edit to the PR body, pointing directly
   to relevant example pages or sections, including generated artifacts when
   those are what changed. Once the preview is built, verify the links and
   that the content matches the current changes. For visual changes, capture
   screenshots of the affected preview pages and embed them in the PR with
   descriptive captions. Include before-and-after views when useful.
   **Done when:** the contributor has added and verified the live example
   links and, for visual changes, embedded screenshots from the preview build.

Create the PR with the available evidence, then add the inferred preview links
once its number is known. Mark the links as awaiting verification while the
build is pending. If the preview fails or is unavailable, state the blocker
and what remains to verify; keep those items outstanding. Use screenshots
from the preview build and distinguish inferred links from verified ones.

## Write and verify the PR

Use the template below. Start the body with a short, plain-language description
of what changed and why it adds value to sphinx-llm, followed by a detailed
bullet list of changes. Replace all placeholders and omit inapplicable
sections. Retain documentation examples for functionality changes and
screenshots for visual changes, or explicitly explain the outstanding blocker.

Record checks actually run and their results. If using `gh`, write the body to
a temporary file and pass it with `--body-file` to preserve Markdown formatting.
After creating or updating the PR, inspect the published body and check that
links and images work. Update preview evidence after further changes when it
no longer represents the PR.

**Done when:** the published PR follows the requested format, its evidence
matches the current changes, and any unavailable evidence is clearly marked.

## PR body template

```markdown
<Describe the change in a few sentences and explain its value to the project.>

## Changes

- <Describe a specific change and its effect.>
- <Describe another change, including relevant documentation or tests.>

## Documentation examples

- [<Live functionality example>](<verified RTD preview URL and anchor>)
  — <What reviewers can try or inspect here.>

## Screenshots

<Describe the visual change shown in this preview-build screenshot.>

![<Descriptive alt text>](<screenshot attachment URL>)

## Validation

- `<command or check>` — <result>
- Read the Docs preview — <build result and what was verified>
```
