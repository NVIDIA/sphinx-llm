Configuration
=============

You can set these options in ``conf.py`` or override them for one build
with Sphinx's ``-D name=value`` option. The tables below define each
setting's behavior and default. If you're choosing a workflow rather than
looking up a value, start with the :doc:`how-to guides <how-to/index>`.

TXT settings
------------

.. list-table::
   :header-rows: 1
   :widths: 25 45 15 15

   * - Setting
     - Purpose and behavior
     - Type
     - Default
   * - ``llms_txt_enabled``
     - Enable or disable all llms.txt artifact generation without removing the extension from ``conf.py``; audience tags remain available. Use ``sphinx-build -D llms_txt_enabled=0`` to skip generation on a per-build basis.
     - ``bool``
     - ``True``
   * - ``llms_txt_nested_enabled``
     - Generate scoped nested ``llms.txt`` files and discover the most-specific index. Set to ``False`` for root-only generation and discovery.
     - ``bool``
     - ``True``
   * - ``llms_txt_description``
     - Project description in the generated index. When empty, tries installed distribution Description metadata named by Sphinx project, then html_title, then Documentation for <project>.
     - ``str``
     - ``""``
   * - ``llms_txt_build_parallel``
     - Build markdown files in parallel to the HTML files.
     - ``bool``
     - ``True``
   * - ``llms_txt_markdown_docinfo``
     - Include Sphinx project metadata, including the configured version, in generated Markdown. Set to ``True`` to opt in.
     - ``bool``
     - ``False``
   * - ``llms_txt_suffix_mode``
     - Markdown output mode. ``"append"`` publishes ``.html.md`` and, for non-root ``dirhtml`` pages, the no-trailing-slash ``.md`` form. ``"replace"`` replaces ``.html`` with ``.md``. ``"auto"`` publishes both and makes append canonical. Compatibility values remain supported: ``"both"`` equals ``"auto"``; ``"file-suffix"`` publishes only ``.html.md``; ``"url-suffix"`` publishes only the previous ``dirhtml`` no-trailing-slash form and behaves like ``"file-suffix"`` for ``html``.
     - ``str``
     - ``"auto"``
   * - ``llms_txt_full_build``
     - Generate the optional, non-standard ``llms-full.txt`` convenience file and list it in generated ``llms.txt`` output. Set to ``True`` to opt in.
     - ``bool``
     - ``False``
   * - ``llms_txt_exclude``
     - A list of Sphinx wildcard patterns matched against document names (not regular expressions or source paths) to exclude from ``llms.txt`` and ``llms-full.txt``. ``*`` does not cross ``/``, while ``**`` does; for example, ``"reference/generated/**"``. The individual markdown files for excluded documents are still generated.
     - ``list[str]``
     - ``[]``
   * - ``llms_txt_override_source``
     - Advanced option that overrides the automatically generated ``llms.txt`` sitemap with the rendered contents of a custom Sphinx source document. Specify a docname or source path relative to the source directory, such as ``"llms-txt"`` or ``"llms-txt.rst"``.
     - ``str``
     - ``""``
   * - ``llms_txt_suppress_unknown_node_warnings``
     - Suppress Markdown-builder warnings for all unknown node types (``True``) or for an exact, case-sensitive sequence of node class names such as ``["caption", "desc_inline"]``. This does not change whether unknown nodes are preserved.
     - ``bool or Sequence[str]``
     - ``False``
   * - ``llms_txt_preserve_unknown_nodes``
     - Include unknown nodes' source text in Markdown as inline code or fenced reStructuredText blocks instead of dropping them. Warnings remain enabled unless separately suppressed.
     - ``bool``
     - ``True``
   * - ``markdown_http_base``
     - Absolute base for generated Markdown links and index destinations. Relative URLs are used when empty; include any hosting subpath when set.
     - str
     - ``""``

Compatibility suffix values
---------------------------

``both``, ``file-suffix``, and ``url-suffix`` are deprecated but
supported. ``both`` is exactly ``auto``; the other legacy modes retain
their single-output behavior rather than expanding to all append paths.
See :doc:`output-reference` before migrating.

.. _shared-summary-settings:

Shared summary settings
-----------------------

Both TXT and docref use these settings, even though their names begin with
``llms_txt_summary_*``. You don't need to enable TXT to use them with
docref: each extension loads the shared configuration itself.

.. list-table::
   :header-rows: 1
   :widths: 25 45 15 15

   * - Setting
     - Purpose and behavior
     - Type
     - Default
   * - ``llms_txt_summary_enabled``
     - Generate one-sentence page descriptions with an OpenAI-compatible provider.
     - ``bool``
     - ``False``
   * - ``llms_txt_summary_provider``
     - Summary provider. The initial implementation supports ``"openai-compatible"``.
     - ``str``
     - ``"openai-compatible"``
   * - ``llms_txt_summary_model``
     - Model used for generated page descriptions. Required when generation is enabled.
     - ``str``
     - ``""``
   * - ``llms_txt_summary_base_url``
     - Base URL of the OpenAI-compatible endpoint. An empty value uses the OpenAI client default.
     - ``str``
     - ``""``
   * - ``llms_txt_summary_api_key_env``
     - Name of the environment variable containing the API key. Set to ``""`` only for an endpoint that deliberately requires no authentication.
     - ``str``
     - ``"OPENAI_API_KEY"``
   * - ``llms_txt_summary_allow_insecure_auth``
     - Allow an API key to be sent to a non-loopback endpoint over plain HTTP. Use only for a trusted network where HTTPS is unavailable.
     - ``bool``
     - ``False``
   * - ``llms_txt_summary_max_input_chars``
     - Maximum rendered input characters sent to the provider (Markdown for TXT, target doctree text for docref). The complete input is still hashed for cache invalidation.
     - ``int``
     - ``12000``
   * - ``llms_txt_summary_timeout``
     - Provider request timeout in seconds.
     - ``int``
     - ``60``
   * - ``llms_txt_summary_cache_path``
     - JSON cache path. Relative paths use the Sphinx configuration directory; an empty value stores the cache under ``app.doctreedir``.
     - ``str``
     - ``""``

Environment overrides
~~~~~~~~~~~~~~~~~~~~~

You can also configure summaries through the environment, which is useful
when local and CI builds use different providers. Each shared setting has
the environment variable shown below:

.. list-table::
   :header-rows: 1

   * - Sphinx setting
     - Environment variable
   * - ``llms_txt_summary_enabled``
     - ``SPHINX_LLM_SUMMARY_ENABLED``
   * - ``llms_txt_summary_provider``
     - ``SPHINX_LLM_SUMMARY_PROVIDER``
   * - ``llms_txt_summary_model``
     - ``SPHINX_LLM_SUMMARY_MODEL``
   * - ``llms_txt_summary_base_url``
     - ``SPHINX_LLM_SUMMARY_BASE_URL``
   * - ``llms_txt_summary_api_key_env``
     - ``SPHINX_LLM_SUMMARY_API_KEY_ENV``
   * - ``llms_txt_summary_allow_insecure_auth``
     - ``SPHINX_LLM_SUMMARY_ALLOW_INSECURE_AUTH``
   * - ``llms_txt_summary_max_input_chars``
     - ``SPHINX_LLM_SUMMARY_MAX_INPUT_CHARS``
   * - ``llms_txt_summary_timeout``
     - ``SPHINX_LLM_SUMMARY_TIMEOUT``
   * - ``llms_txt_summary_cache_path``
     - ``SPHINX_LLM_SUMMARY_CACHE_PATH``

Precedence is ``sphinx-build -D``, then the corresponding environment
variable, then ``conf.py``, then the built-in default. These environment
overrides apply only to shared summary settings, not arbitrary TXT options.
Booleans accept ``1/true/yes/on`` and ``0/false/no/off``
(case-insensitive; empty means false). Input limits and timeouts must be positive
integers. Only ``openai-compatible`` is supported as a provider.

``llms_txt_summary_api_key_env`` names the variable containing the
credential; it is not the credential itself. There is no API-key Sphinx setting.
Use your shell or CI secret store for the value. The extensions use these
explicit summary model settings, not ``OPENAI_MODEL``. An empty base URL
leaves endpoint selection to the OpenAI client, whose own environment defaults
can apply (including ``OPENAI_BASE_URL``).

For a worked provider configuration and its data-handling implications, see
:doc:`../docref/how-to/providers`. If you're planning repeated or offline
builds, :doc:`../docref/explanation` explains what the cache identifies.
