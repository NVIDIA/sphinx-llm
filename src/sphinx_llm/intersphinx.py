# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Find published Markdown for resolved intersphinx HTML pages."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

_TIMEOUT = 2
_MARKDOWN_TYPES = {
    "text/markdown",
    "text/x-markdown",
    "text/plain",
    "application/octet-stream",
}


class _AlternateParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "link":
            return
        attributes = dict(attrs)
        if (
            "alternate" in (attributes.get("rel") or "").lower().split()
            and (attributes.get("type") or "").lower().split(";", 1)[0].strip()
            == "text/markdown"
            and attributes.get("href")
        ):
            self.links.append(attributes["href"])


def _get(url: str, limit: int) -> tuple[str, str, bytes] | None:
    try:
        with urlopen(
            Request(url, headers={"User-Agent": "sphinx-llm"}), timeout=_TIMEOUT
        ) as response:
            return (
                response.geturl(),
                response.headers.get_content_type(),
                response.read(limit),
            )
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return None


def _same_origin(left: str, right: str) -> bool:
    a, b = urlsplit(left), urlsplit(right)
    return (a.scheme.lower(), a.netloc.lower()) == (b.scheme.lower(), b.netloc.lower())


def _candidates(path: str) -> list[str]:
    if path.endswith(".html"):
        paths = [path + ".md", path[:-5] + ".md"]
        if path.endswith("/index.html"):
            paths.append(path[: -len("/index.html")] + ".md")
        return paths
    if path.endswith("/"):
        paths = [path + "index.html.md", path + "index.md"]
        if path != "/":
            paths.append(path[:-1] + ".md")
        return paths
    if "." not in path.rsplit("/", 1)[-1]:
        return [path + ".md", path + "/index.html.md", path + "/index.md"]
    return []


def _verified_markdown(
    url: str, original: str, *, advertised: bool = False
) -> str | None:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or (not advertised and not parsed.path.endswith(".md"))
        or not _same_origin(url, original)
    ):
        return None
    result = _get(url, 512)
    if result is None:
        return None
    final_url, content_type, body = result
    if (
        not _same_origin(final_url, original)
        or (not advertised and not urlsplit(final_url).path.endswith(".md"))
        or content_type not in _MARKDOWN_TYPES
        or (
            advertised
            and not parsed.path.endswith(".md")
            and content_type not in {"text/markdown", "text/x-markdown"}
        )
        or not body.strip()
        or body.lstrip().lower().startswith((b"<!doctype html", b"<html"))
        or body.strip().lower() in {b"not found", b"404 not found"}
    ):
        return None
    return final_url


def find_markdown_url(url: str) -> str:
    """Return a verified Markdown page, or the unchanged HTML URL."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not _candidates(parsed.path):
        return url
    html_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    page = _get(html_url, 65536)
    if page is not None and page[1] == "text/html":
        alternates = _AlternateParser()
        alternates.feed(page[2].decode("utf-8", errors="replace"))
        if len(alternates.links) == 1:
            candidate = urljoin(page[0], alternates.links[0])
            markdown = _verified_markdown(candidate, html_url, advertised=True)
            if markdown is not None:
                target = urlsplit(markdown)
                return urlunsplit(
                    (
                        target.scheme,
                        target.netloc,
                        target.path,
                        parsed.query or target.query,
                        parsed.fragment,
                    )
                )
        elif len(alternates.links) > 1:
            return url

    for path in _candidates(parsed.path):
        candidate = urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
        markdown = _verified_markdown(candidate, html_url)
        if markdown is not None:
            target = urlsplit(markdown)
            return urlunsplit(
                (
                    target.scheme,
                    target.netloc,
                    target.path,
                    parsed.query or target.query,
                    parsed.fragment,
                )
            )
    return url
