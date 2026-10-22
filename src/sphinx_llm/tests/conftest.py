# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Shared test setup; behavior-specific inputs and assertions stay in test modules.

Fixtures named ``readonly_*`` share one completed build per configuration within a
test module. Consumers may inspect the app and artifacts, but must not mutate the
app, environment, sources or output, rebuild, or attach observers. Use the
function-scoped ``sphinx_build`` or a build factory for those scenarios; copy the
integration sources before editing them.

The module-scoped factories below do not cache apps or builds. Every call
constructs a new app; incremental tests can still explicitly reuse output paths.
Example builds use fresh ``tmp_path_factory`` directories for output and doctrees,
with cleanup and failure-artifact retention managed by pytest.
"""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sphinx.application import Sphinx

from sphinx_llm.txt import MarkdownGenerator


@pytest.fixture(scope="module")
def docs_source_dir() -> Path:
    """Unthemed integration documentation corpus (treat as read-only)."""
    return Path(__file__).parent / "fixtures" / "integration_docs"


@pytest.fixture
def make_sphinx_project(tmp_path):
    """Write a minimal project, with explicit config and document contents."""

    def make(*, config: str, documents: dict[str, str], root: Path | None = None):
        source_dir = (root if root is not None else tmp_path) / "source"
        source_dir.mkdir(parents=True)
        (source_dir / "conf.py").write_text(config, encoding="utf-8")
        for name, contents in documents.items():
            path = source_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding="utf-8")
        return source_dir

    return make


@pytest.fixture(scope="module")
def make_sphinx_app():
    """Construct a Sphinx app; callers can connect observers before building.

    Explicit paths and freshenv are honored so repeated calls can share the
    exact same output/doctree cache. ``parallel`` is Sphinx's reader worker
    count, distinct from the ``llms_txt_build_parallel`` config setting.
    """

    def make(*, srcdir, **kwargs):
        source_dir = Path(srcdir)
        defaults = {
            "confdir": str(source_dir),
            "outdir": str(source_dir.parent / "build"),
            "doctreedir": str(source_dir.parent / "doctrees"),
            "buildername": "html",
            "freshenv": True,
            "warningiserror": False,
            "status": StringIO(),
            "warning": StringIO(),
        }
        defaults.update(kwargs)
        return Sphinx(srcdir=str(source_dir), **defaults)

    return make


@pytest.fixture(scope="module")
def build_sphinx_app(make_sphinx_app):
    """Build in-process, retaining output/doctree paths for incremental calls."""

    def build(
        source_dir: Path,
        *,
        builder: str = "html",
        freshenv: bool = True,
        confoverrides: dict | None = None,
        parallel: int = 0,
        root: Path | None = None,
    ):
        root = root if root is not None else source_dir.parent
        warning = StringIO()
        app = make_sphinx_app(
            srcdir=source_dir,
            outdir=str(root / "build"),
            doctreedir=str(root / "doctrees"),
            buildername=builder,
            confoverrides=confoverrides or {},
            warning=warning,
            freshenv=freshenv,
            parallel=parallel,
        )
        app.build()
        assert app.statuscode == 0, warning.getvalue()
        return app, root / "build", warning

    return build


@pytest.fixture(scope="module")
def build_example_docs(docs_source_dir, tmp_path_factory, build_sphinx_app):
    """Build examples in a fixture-managed directory, fresh for each factory call."""

    def build(builder: str, confoverrides: dict | None = None):
        overrides = {"llms_txt_build_parallel": True, **(confoverrides or {})}
        app, output, _ = build_sphinx_app(
            docs_source_dir,
            builder=builder,
            confoverrides=overrides,
            root=tmp_path_factory.mktemp("example-build"),
        )
        return app, output, docs_source_dir

    return build


@pytest.fixture
def make_markdown_generator(tmp_path):
    """Construct an unbuilt generator with just the application state a unit needs."""

    def make(*, root: Path | None = None, builder: str = "html", config=None, env=None):
        root = root if root is not None else tmp_path
        app = SimpleNamespace(
            config=config if config is not None else SimpleNamespace(),
            env=env
            if env is not None
            else SimpleNamespace(
                get_doctree=lambda _: SimpleNamespace(traverse=lambda _: [])
            ),
            builder=SimpleNamespace(name=builder),
            outdir=root,
            doctreedir=root / "doctrees",
            confdir=root,
            connect=MagicMock(),
        )
        return MarkdownGenerator(app)

    return make


@pytest.fixture(
    params=[("html", True), ("dirhtml", True), ("html", False), ("dirhtml", False)]
)
def markdown_app(request, make_markdown_generator):
    """Unbuilt app for constructor/event/process units, retaining the mode matrix."""
    builder, parallel = request.param
    config = SimpleNamespace(llms_txt_build_parallel=parallel)
    app = make_markdown_generator(builder=builder, config=config).app
    return app


@pytest.fixture
def clear_summary_environment(monkeypatch):
    """Opt-in isolation: run before tests set their own summary/provider values."""
    for name in list(os.environ):
        if name.startswith(("SPHINX_LLM_SUMMARY_", "OPENAI_")):
            monkeypatch.delenv(name)


@pytest.fixture
def openai_response():
    """Factory for valid compatible-endpoint responses; malformed cases stay explicit."""

    def make(content="Summary."):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    return make


_DEFAULT_BUILD_MODES = [
    ("html", True),
    ("dirhtml", True),
    ("html", False),
    ("dirhtml", False),
]


@pytest.fixture(params=_DEFAULT_BUILD_MODES)
def sphinx_build(
    build_example_docs, request
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Fresh function-scoped build for tests that mutate application state."""
    builder, parallel = request.param
    yield build_example_docs(builder, {"llms_txt_build_parallel": parallel})


@pytest.fixture(scope="module", params=_DEFAULT_BUILD_MODES)
def readonly_sphinx_build(
    build_example_docs, request
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Read-only default output in each builder/parallel mode; never rebuild."""
    builder, parallel = request.param
    yield build_example_docs(builder, {"llms_txt_build_parallel": parallel})


@pytest.fixture
def sphinx_build_preserving_unknown_nodes(
    build_example_docs,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Build the example docs with default unknown-node preservation."""
    yield build_example_docs(
        "html",
        {
            "llms_txt_build_parallel": False,
        },
    )


@pytest.fixture(
    params=[
        (builder, parallel, full_setting)
        for builder in ("html", "dirhtml")
        for parallel in (True, False)
        for full_setting in (None, False, True)
    ]
)
def sphinx_build_llms_full_matrix(
    build_example_docs,
    request,
) -> Generator[tuple[Sphinx, Path, Path, bool | None], None, None]:
    """Build every supported llms-full setting and build-mode combination."""
    builder, parallel, full_setting = request.param
    overrides = {"llms_txt_build_parallel": parallel}
    if full_setting is not None:
        overrides["llms_txt_full_build"] = full_setting
    app, build_dir, source_dir = build_example_docs(builder, overrides)
    yield app, build_dir, source_dir, full_setting


@pytest.fixture
def sphinx_build_with_suffix_mode_config(
    build_example_docs,
    request,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Build Sphinx docs with specific llms_txt_suffix_mode configuration."""
    builder, suffix_mode = request.param
    yield build_example_docs(builder, {"llms_txt_suffix_mode": suffix_mode})


@pytest.fixture
def llms_txt_override_build(
    build_example_docs,
    builder: str,
    parallel: bool,
    override_source: str,
    suffix_mode: str | None,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Build docs with a custom llms.txt source and explicit build settings."""
    overrides = {
        "llms_txt_build_parallel": parallel,
        "llms_txt_full_build": True,
        "llms_txt_override_source": override_source,
    }
    if suffix_mode is not None:
        overrides["llms_txt_suffix_mode"] = suffix_mode
    yield build_example_docs(builder, overrides)


@pytest.fixture(params=[None, False], ids=["default", "disabled"])
def llms_txt_override_build_without_full(
    build_example_docs,
    request,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Build overridden llms.txt with default or disabled full output."""
    overrides = {
        "llms_txt_build_parallel": False,
        "llms_txt_override_source": "index.rst",
    }
    if request.param is not None:
        overrides["llms_txt_full_build"] = request.param
    yield build_example_docs(
        "html",
        overrides,
    )


@pytest.fixture(
    params=[
        ("html", "https://example.com/docs/", "append"),
        ("html", "https://example.com/docs/", "replace"),
        ("dirhtml", "https://example.com/docs/", "auto"),
        ("dirhtml", "https://example.com/docs/", "replace"),
        # A trailing slash on the base is optional.
        ("dirhtml", "https://example.com/docs", "url-suffix"),
    ]
)
def sphinx_build_with_http_base(
    build_example_docs,
    request,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Build Sphinx docs with markdown_http_base set."""
    builder, http_base, suffix_mode = request.param
    yield build_example_docs(
        builder,
        {
            "markdown_http_base": http_base,
            "llms_txt_suffix_mode": suffix_mode,
            "llms_txt_full_build": True,
        },
    )


@pytest.fixture(scope="module")
def readonly_sphinx_build_no_llms_full(
    build_example_docs,
    request,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Read-only output with full generation disabled; never modify artifacts."""
    builder = request.param
    yield build_example_docs(builder, {"llms_txt_full_build": False})


@pytest.fixture(
    scope="module",
    params=[("html", True), ("html", False), ("dirhtml", True), ("dirhtml", False)],
)
def readonly_sphinx_build_with_exclude(
    build_example_docs,
    request,
) -> Generator[tuple[Sphinx, Path, Path], None, None]:
    """Read-only excluded output, omitting unrelated unknown-node preservation."""
    builder, parallel = request.param
    yield build_example_docs(
        builder,
        {
            "llms_txt_build_parallel": parallel,
            "llms_txt_exclude": ["apples", "nested/**"],
            "llms_txt_full_build": True,
            # The non-excluded test page contains a docref to the excluded apples
            # page. Keep these tests focused on excluding page artifacts rather
            # than the separately tested preservation of that generated node.
            "llms_txt_preserve_unknown_nodes": False,
        },
    )


@pytest.fixture
def summary_server():
    """Serve deterministic chat completions to parent and subprocess builds."""
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers["Content-Length"])
            requests.append(json.loads(self.rfile.read(content_length)))
            response = json.dumps(
                {
                    "id": "test-completion",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "test-model",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": (
                                    "Generated summary with "
                                    "[Callback API](python_api.html.md#callback-api)."
                                ),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


@pytest.fixture
def summary_generator(make_markdown_generator):
    """Build the page-summary unit stub with stable cache paths and defaults."""

    def make(tmp_path: Path, **config_values) -> tuple[MarkdownGenerator, Path]:
        tmp_path.mkdir(parents=True, exist_ok=True)
        defaults = {
            "llms_txt_summary_enabled": True,
            "llms_txt_summary_provider": "openai-compatible",
            "llms_txt_summary_model": "test-model",
            "llms_txt_summary_base_url": "https://example.com/v1",
            "llms_txt_summary_api_key_env": "TEST_API_KEY",
            "llms_txt_summary_allow_insecure_auth": False,
            "llms_txt_summary_max_input_chars": 12_000,
            "llms_txt_summary_timeout": 60,
            "llms_txt_summary_cache_path": "",
        }
        defaults.update(config_values)
        config = SimpleNamespace(**defaults, overrides={})
        generator = make_markdown_generator(root=tmp_path, config=config)
        markdown_file = tmp_path / "page.html.md"
        markdown_file.write_text(
            "# Page\n\nComplete **Markdown** contents.", encoding="utf-8"
        )
        generator._docname_by_output_file[markdown_file] = "page"
        return generator, markdown_file

    return make


@pytest.fixture
def sitemap_generator(make_markdown_generator):
    """Build the serialization stub without page-summary configuration."""

    def make(tmp_path: Path, http_base: str = "") -> MarkdownGenerator:
        config = SimpleNamespace(
            _raw_config={"markdown_http_base": http_base},
            copyright="",
            llms_txt_exclude=[],
            markdown_http_base=http_base,
            project="Serialization test",
        )
        generator = make_markdown_generator(root=tmp_path, config=config)
        generator.outdir = tmp_path
        generator.suffix_mode = "auto"
        return generator

    return make


@pytest.fixture
def docref_project(make_sphinx_project):
    """Docref's minimal authored project, including its target and hidden toctree."""

    def make(
        tmp_path: Path,
        *,
        index: str,
        target: str = "Target\n======\n\nThe first target paragraph.\n",
        extra_documents: dict[str, str] | None = None,
    ):
        return make_sphinx_project(
            root=tmp_path,
            config='project = "docref tests"\nextensions = ["sphinx_llm.docref"]\nmaster_doc = "index"\nnitpicky = True\n',
            documents={
                "index.rst": index,
                "target.rst": target,
                **{
                    f"{name}.rst": content
                    for name, content in (extra_documents or {}).items()
                },
            },
        )

    return make


@pytest.fixture
def fake_summary_generator():
    """Return a recording docref provider; tests own calls and expected summaries."""

    def make(calls: list, prefix: str = "Generated summary"):
        def generate(settings, contents: str) -> str:
            calls.append((settings, contents))
            return f"{prefix} {len(calls)}."

        return generate

    return make


@pytest.fixture
def build_versioned_markdown(make_sphinx_app, make_sphinx_project):
    """Build a versioned project with explicit authored metadata."""

    def build(tmp_path: Path, confoverrides: dict | None = None) -> str:
        source_dir = make_sphinx_project(
            root=tmp_path,
            config='extensions = ["sphinx_llm.txt"]\n'
            'project = "Example project"\n'
            'version = "1.2.3"\n'
            'release = "1.2.3.post1"\n',
            documents={
                "index.rst": "Example project\n===============\n\nProject content.\n"
            },
        )
        build_dir = tmp_path / "build"
        doctree_dir = tmp_path / "doctrees"

        app = make_sphinx_app(
            srcdir=str(source_dir),
            confdir=str(source_dir),
            outdir=str(build_dir),
            doctreedir=str(doctree_dir),
            buildername="html",
            warningiserror=False,
            freshenv=True,
            confoverrides={
                "llms_txt_build_parallel": False,
                **(confoverrides or {}),
            },
        )
        app.build()

        return (build_dir / "index.html.md").read_text(encoding="utf-8")

    return build
