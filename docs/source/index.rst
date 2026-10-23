sphinx-llm
==========

Sphinx extensions for LLM-friendly documentation and static, build-time content.
Choose either extension independently, or use them together.

.. toctree::
   :maxdepth: 2
   :hidden:

   txt/index
   docref/index

* :doc:`txt/index` publishes an **llms.txt index and per-page Markdown**
  alongside HTML, without a model or API key.
* :doc:`docref/index` renders **linked page summaries** from authored text
  or an explicitly enabled model.

Install with ``pip install sphinx-llm``, then follow the relevant tutorial.
Generation additionally needs ``sphinx-llm[gen]``; installing it does not
enable provider requests.

Project links
-------------

* `Source and README <https://github.com/NVIDIA/sphinx-llm>`_
* `Issues <https://github.com/NVIDIA/sphinx-llm/issues>`_
* :doc:`project/contributing`
* :doc:`project/alternatives`
* :doc:`project/releasing`
