sphinx-llm
==========

You can use sphinx-llm to make your Sphinx documentation easier for agents to
read, or to add linked summaries to your pages. The two extensions work
independently, so you can start with the one you need.

.. toctree::
   :maxdepth: 2
   :hidden:

   txt/index
   docref/index
   maintainers/index

* :doc:`txt/index` adds an **llms.txt index and Markdown pages** alongside
  your HTML. You don't need a model or API key.
* :doc:`docref/index` adds **linked page summaries** to your documentation.
  You can write the summaries yourself or choose a model to generate them.

Install the package with ``pip install sphinx-llm``, then follow the
:doc:`TXT tutorial <txt/tutorial>` or
:doc:`docref tutorial <docref/tutorial>`. Both start with an example you can
build without a provider. If you later want generated summaries, you'll need
the ``sphinx-llm[gen]`` extra and an explicitly configured model.

Working on sphinx-llm?
----------------------

You'll find setup instructions, our writing guide and release instructions in
:doc:`maintainers/index`. You can also browse the
`source repository <https://github.com/NVIDIA/sphinx-llm>`_,
`report an issue <https://github.com/NVIDIA/sphinx-llm/issues>`_,
or :doc:`compare alternatives <project/alternatives>`.
