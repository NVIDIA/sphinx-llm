"""
Tests for the sphinx_llm.txt module.
"""

import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Generator, Tuple
import pytest
from sphinx.application import Sphinx
from sphinx_llm.txt import MarkdownGenerator, setup


@pytest.fixture
def sphinx_build() -> Generator[Tuple[Sphinx, str], None, None]:
    """
    Build Sphinx documentation into a temporary directory.
    
    Yields:
        Tuple of (Sphinx app, temporary build directory path)
    """
    # Get the docs source directory
    docs_source_dir = Path(__file__).parent.parent.parent.parent / "docs" / "source"
    
    # Create a temporary directory for the build
    with tempfile.TemporaryDirectory() as temp_dir:
        build_dir = os.path.join(temp_dir, "build")
        doctree_dir = os.path.join(temp_dir, "doctrees")
        
        # Create the Sphinx application
        app = Sphinx(
            srcdir=str(docs_source_dir),
            confdir=str(docs_source_dir),
            outdir=build_dir,
            doctreedir=doctree_dir,
            buildername="html",
            warningiserror=False,
            freshenv=True,
        )
        
        # Build the documentation
        app.build()
        
        yield app, build_dir


def test_sphinx_build_fixture(sphinx_build):
    """Test that the sphinx_build fixture works correctly."""
    app, build_dir = sphinx_build
    
    # Verify the app is a Sphinx application
    assert isinstance(app, Sphinx)
    
    # Verify the build directory exists and contains files
    assert os.path.exists(build_dir)
    assert os.path.isdir(build_dir)
    
    # Check that index.html exists in the build directory
    build_path = Path(build_dir)
    index_html = build_path / "index.html"
    assert index_html.exists(), f"{index_html} does not exist"

    
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
