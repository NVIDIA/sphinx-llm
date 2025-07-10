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


def test_setup_function():
    """Test the setup function returns correct configuration."""
    app: Any = MockApp()
    result = setup(app)
    
    assert result['version'] == '0.0.1'
    assert result['parallel_read_safe'] is True
    assert result['parallel_write_safe'] is True


def test_markdown_generator_setup():
    """Test that setup connects to the correct events."""
    app: Any = MockApp()
    generator = MarkdownGenerator(app)
    
    generator.setup()
    
    # Check that the correct events are connected
    events = [call[0] for call in app.connect_calls]
    assert 'builder-inited' in events
    assert 'build-finished' in events


def test_builder_inited():
    """Test builder_inited method."""
    app: Any = MockApp()
    generator = MarkdownGenerator(app)
    
    # Mock a builder
    mock_builder = type('MockBuilder', (), {})()
    app.builder = mock_builder
    
    generator.builder_inited(app)
    
    assert generator.builder == mock_builder


def test_generate_markdown_files_with_exception():
    """Test generate_markdown_files when an exception occurs."""
    app: Any = MockApp()
    generator = MarkdownGenerator(app)
    
    # Test with exception
    exception = Exception("Build failed")
    generator.generate_markdown_files(app, exception)
    
    # Should not process files when exception occurs
    assert generator.generated_markdown_files == []
