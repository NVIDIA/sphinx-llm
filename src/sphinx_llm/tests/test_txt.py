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


def test_markdown_generator_init(sphinx_build):
    """Test MarkdownGenerator initialization."""
    app, _ = sphinx_build
    generator = MarkdownGenerator(app)
    
    assert generator.app == app
    assert generator.builder is None
    assert generator.generated_markdown_files == []


def test_markdown_generator_setup(sphinx_build):
    """Test that setup connects to the correct events."""
    app, _ = sphinx_build
    generator = MarkdownGenerator(app)
    
    # Patch app.connect to record calls
    connect_calls = []
    original_connect = app.connect
    def record_connect(event, callback):
        connect_calls.append((event, callback))
        return original_connect(event, callback)
    app.connect = record_connect
    
    generator.setup()
    
    # Check that the correct events are connected
    events = [call[0] for call in connect_calls]
    assert 'builder-inited' in events
    assert 'build-finished' in events
    
    # Restore original connect
    app.connect = original_connect


def test_builder_inited(sphinx_build):
    """Test builder_inited method."""
    app, _ = sphinx_build
    generator = MarkdownGenerator(app)
    
    generator.builder_inited(app)
    
    assert generator.builder == app.builder


def test_generate_markdown_files_with_exception(sphinx_build):
    """Test generate_markdown_files when an exception occurs."""
    app, _ = sphinx_build
    generator = MarkdownGenerator(app)
    
    # Test with exception
    exception = Exception("Build failed")
    generator.generate_markdown_files(app, exception)
    
    # Should not process files when exception occurs
    assert generator.generated_markdown_files == []
