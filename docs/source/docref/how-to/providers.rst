Configure a summary provider
============================

These instructions also apply to TXT descriptions. They do not require both
extensions. The shared settings reference is :ref:`shared-summary-settings`.

Install and choose an endpoint
------------------------------

.. code-block:: console

   python -m pip install "sphinx-llm[gen]"

Choose an OpenAI-compatible Chat Completions endpoint and a model available
there. For a hosted provider, set these in ``conf.py``, replacing the
example endpoint and model with values from that provider:

.. code-block:: python

   llms_txt_summary_enabled = True
   llms_txt_summary_provider = "openai-compatible"
   llms_txt_summary_model = "your-provider-model"
   llms_txt_summary_base_url = "https://your-provider.example/v1"
   llms_txt_summary_api_key_env = "DOCS_SUMMARY_API_KEY"

Supply ``DOCS_SUMMARY_API_KEY`` through your shell or CI secret store,
not a committed file. It contains the key; the configuration contains only
its environment-variable name. Then run:

.. code-block:: console

   sphinx-build -W -b html source build/html

Use empty docrefs with no authored target metadata to exercise generation;
authored overrides intentionally avoid requests. The extension expects a
non-empty text response from Chat Completions, with temperature zero and
reasoning effort ``none``. Not every nominally compatible model accepts
these fields; check the provider's model support. There is no local-CLI
autodetection or implicit enablement.

Local unauthenticated endpoint
------------------------------

For an already-running local OpenAI-compatible server, configure its actual
model name and loopback base URL. For example, with an Ollama model you have
already installed and are serving:

.. code-block:: python

   llms_txt_summary_enabled = True
   llms_txt_summary_model = "llama3.2"
   llms_txt_summary_base_url = "http://localhost:11434/v1"
   llms_txt_summary_api_key_env = ""

An empty credential-variable name deliberately disables credential lookup;
it does not fall back to ``OPENAI_API_KEY``. The client uses a dummy
non-secret value because its API requires a non-empty key argument.
This example requires the server/model; it is not a network-free build.

Transport and data
------------------

Rendered target content is sent to the selected endpoint, up to the configured
input-character limit. Review its data-retention and privacy terms for your
documentation. Authored summaries avoid sending those targets.
Prefer HTTPS for remote providers. A configured key is rejected for plain HTTP
to a non-loopback endpoint unless you explicitly enable
``llms_txt_summary_allow_insecure_auth``; that exception sends the key
without transport encryption and is only for a trusted network where HTTPS
cannot be used. Loopback is allowed for local development.

Environment-only configuration is useful in CI:
``SPHINX_LLM_SUMMARY_ENABLED``, ``SPHINX_LLM_SUMMARY_MODEL``,
``SPHINX_LLM_SUMMARY_BASE_URL`` and
``SPHINX_LLM_SUMMARY_API_KEY_ENV`` override their ``conf.py`` values.
The API-key value still belongs in the named variable.
Keep trusted provider settings and secrets out of untrusted pull-request jobs.
