# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Intersphinx links to independently published Markdown pages."""

from __future__ import annotations

import zlib
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from sphinx.application import Sphinx

from sphinx_llm.intersphinx import find_markdown_url


class _Handler(SimpleHTTPRequestHandler):
    requests: dict[str, int] = {}
    required_query: str | None = None

    def guess_type(self, path):
        if path.endswith(".markdown"):
            return "text/markdown"
        return super().guess_type(path)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        self.requests[path] = self.requests.get(path, 0) + 1
        if (
            path.endswith("/api.md")
            and self.required_query
            and query != self.required_query
        ):
            self.send_error(403)
            return
        super().do_GET()

    def log_message(self, *args):
        pass


def _build(source: Path, output: Path, builder: str = "html") -> None:
    app = Sphinx(
        srcdir=str(source),
        confdir=str(source),
        outdir=str(output),
        doctreedir=str(output.parent / f"{output.name}-doctrees"),
        buildername=builder,
        freshenv=True,
        warningiserror=False,
    )
    app.build()
    assert app.statuscode == 0


@pytest.mark.parametrize("builder", ["html", "dirhtml"])
@pytest.mark.parametrize(
    ("alternate", "published", "expected", "content"),
    [
        ("api.html.md", "api.html.md", "api.html.md", "# API\n"),
        ("api.md", "api.md", "api.md", "# API\n"),
        ("api.md?token=required", "api.md", "api.md?token=required", "# API\n"),
        ("api.markdown", "api.markdown", "api.markdown", "# API\n"),
        ("", "api.md", "api.md", "# API\n"),
        ("missing.md", "", "api.html", ""),
        ("https://elsewhere.test/api.md", "", "api.html", ""),
        ("api.md", "api.md", "api.html", "<html>Not found</html>"),
    ],
)
def test_intersphinx_uses_available_markdown(
    tmp_path: Path,
    builder: str,
    alternate: str,
    published: str,
    expected: str,
    content: str,
) -> None:
    destination_source = tmp_path / "destination-source"
    destination_output = tmp_path / "site" / "docs"
    destination_source.mkdir()
    (destination_source / "conf.py").write_text('project = "Destination"\n')
    (destination_source / "index.rst").write_text(
        "Destination\n===========\n\n.. toctree::\n\n   api\n"
    )
    (destination_source / "api.rst").write_text(
        "API\n===\n\n.. _api-anchor:\n\nAnchor\n------\n"
    )
    _build(destination_source, destination_output)
    if published:
        (destination_output / published).write_text(content)
    if alternate:
        html_path = destination_output / "api.html"
        html_path.write_text(
            html_path.read_text().replace(
                "</head>",
                f'<link rel="alternate" type="text/markdown" href="{alternate}"></head>',
            )
        )

    _Handler.requests = {}
    _Handler.required_query = (
        "token=required" if "?token=required" in alternate else None
    )
    handler = partial(_Handler, directory=str(tmp_path / "site"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}/docs"
        source = tmp_path / "source"
        source.mkdir()
        (source / "conf.py").write_text(
            'project = "Source"\n'
            'extensions = ["sphinx.ext.intersphinx", "sphinx_llm.txt"]\n'
            f'intersphinx_mapping = {{"destination": ("{base}/", "{destination_output / "objects.inv"}")}}\n'
            "llms_txt_build_parallel = False\n"
            "llms_txt_full_build = True\n"
        )
        (source / "index.rst").write_text(
            "Source\n======\n\n"
            "See :external+destination:doc:`API <api>` and "
            ":external+destination:doc:`API again <api>` and "
            ":external+destination:ref:`anchor <api-anchor>`.\n\n"
            "`Ordinary external link <https://elsewhere.test/api.html>`_.\n"
        )
        output = tmp_path / "output"
        _build(source, output, builder)
        html = (output / "index.html").read_text()
        markdown = (output / "index.html.md").read_text()
        full = (output / "llms-full.txt").read_text()
        assert f"{base}/api.html" in html
        assert f"[API]({base}/{expected})" in markdown
        assert f"[API]({base}/{expected})" in full
        assert f"[anchor]({base}/{expected}#api-anchor)" in markdown
        assert "https://elsewhere.test/api.html" in markdown
        assert _Handler.requests.get("/docs/api.html", 0) <= 1
    finally:
        _Handler.required_query = None
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize(
    ("published", "expected", "explicit_index"),
    [
        ("guide/page/index.html.md", "guide/page/index.html.md", False),
        ("guide/page/index.md", "guide/page/index.md", False),
        ("guide/page.md", "guide/page.md", False),
        ("guide/page.md", "guide/page.md", True),
        ("", "guide/page/", False),
    ],
)
def test_intersphinx_dirhtml_destination(
    tmp_path: Path, published: str, expected: str, explicit_index: bool
) -> None:
    destination_source = tmp_path / "destination-source"
    destination_output = tmp_path / "site" / "v2" / "docs"
    (destination_source / "guide").mkdir(parents=True)
    (destination_source / "conf.py").write_text('project = "Destination"\n')
    (destination_source / "index.rst").write_text(
        "Destination\n===========\n\n.. toctree::\n\n   guide/page\n"
    )
    (destination_source / "guide" / "page.rst").write_text("Page\n====\n")
    _build(destination_source, destination_output, "dirhtml")
    if explicit_index:
        inventory = (
            b"# Sphinx inventory version 2\n"
            b"# Project: Destination\n"
            b"# Version: 1\n"
            b"# The remainder of this file is compressed using zlib.\n"
        )
        inventory += zlib.compress(
            b"guide/page std:doc 1 guide/page/index.html -\n"
            b"page-anchor std:label 1 guide/page/index.html#page-anchor Anchor\n"
        )
        (destination_output / "objects.inv").write_bytes(inventory)
    if published:
        target = destination_output / published
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# Page\n")

    _Handler.requests = {}
    _Handler.required_query = None
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(_Handler, directory=str(tmp_path / "site"))
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}/v2/docs"
        source = tmp_path / "source"
        source.mkdir()
        (source / "conf.py").write_text(
            'project = "Source"\n'
            'extensions = ["sphinx.ext.intersphinx", "sphinx_llm.txt"]\n'
            f'intersphinx_mapping = {{"destination": ("{base}/", "{destination_output / "objects.inv"}")}}\n'
            "llms_txt_build_parallel = False\n"
        )
        reference = ":external+destination:doc:`Page <guide/page>`"
        if explicit_index:
            reference += " and :external+destination:ref:`anchor <page-anchor>`"
        (source / "index.rst").write_text(f"Source\n======\n\n{reference}.\n")
        output = tmp_path / "output"
        _build(source, output)
        markdown = (output / "index.html.md").read_text()
        assert f"[Page]({base}/{expected})" in markdown
        html_path = "guide/page/index.html" if explicit_index else "guide/page/"
        assert f"{base}/{html_path}" in (output / "index.html").read_text()
        if explicit_index:
            assert f"[anchor]({base}/{expected}#page-anchor)" in markdown
        assert _Handler.requests.get(f"/v2/docs/{html_path}", 0) <= 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_discovery_keeps_encoded_paths_query_and_fragment(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.html").write_text("<html><head></head></html>")
    (docs / "index.md").write_text("# Home\n")
    (docs / "api v2.html").write_text("<html><head></head></html>")
    (docs / "api v2.md").write_text("# API\n")
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(_Handler, directory=str(tmp_path))
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}/docs"
        assert find_markdown_url(f"{base}/") == f"{base}/index.md"
        assert (
            find_markdown_url(f"{base}/api%20v2.html?view=wide#section")
            == f"{base}/api%20v2.md?view=wide#section"
        )
        assert find_markdown_url(f"{base}/api.json") == f"{base}/api.json"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
