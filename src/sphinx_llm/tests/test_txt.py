"""
Tests for the sphinx_llm.txt module.
"""

from typing import Any, Callable
import pytest
from sphinx.application import Sphinx
from sphinx_llm.txt import MarkdownGenerator, setup


class MockApp:
    """Simple mock for Sphinx app."""
    def __init__(self):
        self.connect_calls = []
    
    def connect(self, event: str, callback: Callable) -> None:
        self.connect_calls.append((event, callback))


def test_markdown_generator_init():
    """Test MarkdownGenerator initialization."""
    app: Any = MockApp()
    generator = MarkdownGenerator(app)
    
    assert generator.app == app
    assert generator.builder is None
    assert generator.generated_markdown_files == []


def test_html_to_markdown_basic_conversion():
    """Test basic HTML to markdown conversion."""
    app: Any = MockApp()
    generator = MarkdownGenerator(app)
    
    html_content = """
    <h1>Test Title</h1>
    <p>This is a paragraph.</p>
    <h2>Subtitle</h2>
    <p>Another paragraph.</p>
    """
    
    result = generator._html_to_markdown(html_content)
    
    assert "# Test Title" in result
    assert "This is a paragraph." in result
    assert "## Subtitle" in result
    assert "Another paragraph." in result


def test_html_to_markdown_links_and_formatting():
    """Test link and formatting conversion."""
    app: Any = MockApp()
    generator = MarkdownGenerator(app)
    
    html_content = """
    <a href="https://example.com">Example Link</a>
    <strong>Bold text</strong>
    <em>Italic text</em>
    <code>inline code</code>
    """
    
    result = generator._html_to_markdown(html_content)
    
    assert "[Example Link](https://example.com)" in result
    assert "**Bold text**" in result
    assert "*Italic text*" in result
    assert "`inline code`" in result


def test_html_to_markdown_remove_unwanted_elements():
    """Test that unwanted HTML elements are removed."""
    app: Any = MockApp()
    generator = MarkdownGenerator(app)
    
    html_content = """
    <script>alert('test');</script>
    <style>body { color: red; }</style>
    <nav>Navigation content</nav>
    <footer>Footer content</footer>
    <p>This should remain</p>
    """
    
    result = generator._html_to_markdown(html_content)
    
    assert "alert('test')" not in result
    assert "body { color: red; }" not in result
    assert "Navigation content" not in result
    assert "Footer content" not in result
    assert "This should remain" in result
