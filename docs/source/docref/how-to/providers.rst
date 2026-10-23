Configure a summary provider
============================

If you want a model to write summaries, you can connect either extension to an
OpenAI-compatible Chat Completions endpoint. You don't need to enable both
extensions. The :ref:`shared-summary-settings` reference lists the settings
used by this guide.

Install and choose an endpoint
------------------------------

First, install the optional generation dependencies in your documentation
environment:

.. code-block:: console

   python -m pip install "sphinx-llm[gen]"

Choose an endpoint and a model available from that provider. For a hosted
service, add a configuration like this to ``conf.py``, replacing the
example model and URL with your provider's values:

.. code-block:: python

   llms_txt_summary_enabled = True
   llms_txt_summary_provider = "openai-compatible"
   llms_txt_summary_model = "your-provider-model"
   llms_txt_summary_base_url = "https://your-provider.example/v1"
   llms_txt_summary_api_key_env = "DOCS_SUMMARY_API_KEY"

Provide ``DOCS_SUMMARY_API_KEY`` through your shell or CI secret store,
not a committed file. The setting names the variable; the variable holds the
actual key. Once the endpoint is available, build your site:

.. code-block:: console

   sphinx-build -W -b html source build/html

To try generation with docref, use an empty directive and a target without an
authored metadata description. Otherwise, the authored text takes priority
and no request is needed.

The endpoint must return non-empty text from Chat Completions and accept the
request's temperature of zero and reasoning effort ``none``.
Check your provider's model support: a model described as OpenAI-compatible
may not accept every field. Installing the extra or a local CLI doesn't
enable generation automatically.

Local unauthenticated endpoint
------------------------------

You can also use a local server that implements the same API.
For example, if you already have Ollama serving ``llama3.2``, use:

.. code-block:: python

   llms_txt_summary_enabled = True
   llms_txt_summary_model = "llama3.2"
   llms_txt_summary_base_url = "http://localhost:11434/v1"
   llms_txt_summary_api_key_env = ""

Use the actual model name and base URL of your server. The empty
credential-variable name deliberately turns off credential lookup; it doesn't
fall back to ``OPENAI_API_KEY``. The client uses a dummy, non-secret
value because its API requires a non-empty key argument.

This still makes a request to a running server. It isn't the network-free
workflow used by the authored-summary tutorial.

Transport and data
------------------

For each required summary, the extension sends rendered target content to your
endpoint, up to the configured input-character limit. Before using a provider
with confidential documentation, check its privacy and data-retention terms.
An authored summary avoids that request for its target.

Use HTTPS for remote endpoints. The extension rejects a configured key over
plain HTTP to a non-loopback endpoint unless you explicitly enable
``llms_txt_summary_allow_insecure_auth``. That exception sends the
key without transport encryption, so it's only for a trusted network where
HTTPS isn't available. Loopback HTTP is allowed for local development.

In CI, you may find environment overrides more convenient than editing
``conf.py``. For example, ``SPHINX_LLM_SUMMARY_ENABLED``,
``SPHINX_LLM_SUMMARY_MODEL``, ``SPHINX_LLM_SUMMARY_BASE_URL``
and ``SPHINX_LLM_SUMMARY_API_KEY_ENV`` override their matching
configuration values. The key itself still belongs in the named variable.
Keep trusted provider settings and secrets out of untrusted pull-request jobs.
