# sphinx-llm

You can use [Sphinx](https://www.sphinx-doc.org/) to write documentation for
people and publish Markdown for agents from the same source. sphinx-llm adds
that output and can also introduce pages with linked summaries. You can use
either extension on its own.

## Install and start

Install the package in your documentation environment:

```console
pip install sphinx-llm
```

Add the TXT extension to your Sphinx `conf.py`:

```python
extensions = ["sphinx_llm.txt"]
```

Then build your site as usual:

```console
sphinx-build -b html path/to/your/docs path/to/your/build/html
```

You'll find Markdown pages and an llms.txt index alongside your HTML, without
configuring a model or API key.

For more information, check out the
[first build tutorial](https://sphinx-llm.readthedocs.io/en/latest/txt/tutorial.html).

## Publish LLM-friendly documentation

With **sphinx_llm.txt**, you can let agents retrieve one page at a time or
offer a full-text download. You can choose a Markdown URL layout, exclude
pages from indexes and use nested indexes to introduce parts of a larger site.

For more information, check out the
[output reference](https://sphinx-llm.readthedocs.io/en/latest/txt/output-reference.html)
and [task guides](https://sphinx-llm.readthedocs.io/en/latest/txt/how-to/index.html).

## Tailor content to its audience

Your readers may need navigation advice, while an agent needs instructions
for fetching a page. You can write both in one source and let the TXT
extension select the text for each output.

For more information, check out the
[audience-specific content guide](https://sphinx-llm.readthedocs.io/en/latest/txt/how-to/audience-content.html).

## Render linked page summaries

With **sphinx_llm.docref**, you can introduce another page with a title,
summary and link. Write a summary for one reference or reuse the target
page's description, then adjust the box's wording and style to fit your site.
You don't need TXT or a model for authored references.

For more information, check out the
[authored-reference tutorial](https://sphinx-llm.readthedocs.io/en/latest/docref/tutorial.html)
and [directive reference](https://sphinx-llm.readthedocs.io/en/latest/docref/directive-reference.html).

## Generate descriptions with a model

If you'd rather have a model write summaries, both extensions can use an
OpenAI-compatible provider and cache its results. Docref also writes a report
showing where each rendered summary came from. Generation needs the
`sphinx-llm[gen]` extra and explicit configuration; installing it doesn't
start provider requests.

For more information, check out the
[provider guide](https://sphinx-llm.readthedocs.io/en/latest/docref/how-to/providers.html)
and [shared settings reference](https://sphinx-llm.readthedocs.io/en/latest/txt/configuration.html#shared-summary-settings).

## Work on sphinx-llm

You'll find local setup, our documentation writing guide and release
instructions in the Maintainers section.

For more information, check out the
[Maintainers guide](https://sphinx-llm.readthedocs.io/en/latest/maintainers/index.html),
[contributor setup](https://sphinx-llm.readthedocs.io/en/latest/project/contributing.html)
and [release instructions](https://sphinx-llm.readthedocs.io/en/latest/project/releasing.html).

You can browse the [documentation](https://sphinx-llm.readthedocs.io/en/latest/),
[compare alternatives](https://sphinx-llm.readthedocs.io/en/latest/project/alternatives.html)
or [report an issue](https://github.com/NVIDIA/sphinx-llm/issues).
The project is licensed under [Apache-2.0](LICENSE).
