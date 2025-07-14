"""
Tests for the sphinx_llm.txt module.
"""

import tempfile
from pathlib import Path
from typing import Generator, Tuple
import pytest
from sphinx.application import Sphinx
from sphinx_llm.txt import MarkdownGenerator


@pytest.fixture
def sphinx_build() -> Generator[Tuple[Sphinx, Path, Path], None, None]:
    """
    Build Sphinx documentation into a temporary directory.
    
    Yields:
        Tuple of (Sphinx app, temporary build directory path, source directory path)
    """
    # Get the docs source directory
    docs_source_dir = Path(__file__).parent.parent.parent.parent / "docs" / "source"
    
    # Create a temporary directory for the build
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        build_dir = temp_path / "build"
        doctree_dir = temp_path / "doctrees"
        
        # Create the Sphinx application
        app = Sphinx(
            srcdir=str(docs_source_dir),
            confdir=str(docs_source_dir),
            outdir=str(build_dir),
            doctreedir=str(doctree_dir),
            buildername="html",
            warningiserror=False,
            freshenv=True,
        )
        
        # Build the documentation
        app.build()
        
        yield app, build_dir, docs_source_dir


def test_sphinx_build_fixture(sphinx_build):
    """Test that the sphinx_build fixture works correctly."""
    app, build_dir, source_dir = sphinx_build
    
    # Verify the app is a Sphinx application
    assert isinstance(app, Sphinx)
    
    # Verify the build directory exists and contains files
    assert build_dir.exists()
    assert build_dir.is_dir()
    
    # Verify the source directory exists
    assert source_dir.exists()
    assert source_dir.is_dir()
    
    # Check that index.html exists in the build directory
    index_html = build_dir / "index.html"
    assert index_html.exists(), f"{index_html} does not exist"


def test_markdown_generator_init(sphinx_build):
    """Test MarkdownGenerator initialization."""
    app, _, _ = sphinx_build
    generator = MarkdownGenerator(app)
    
    assert generator.app == app
    assert generator.builder is None
    assert generator.generated_markdown_files == []


def test_markdown_generator_setup(sphinx_build):
    """Test that setup connects to the correct events."""
    app, _, _ = sphinx_build
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
    app, _, _ = sphinx_build
    generator = MarkdownGenerator(app)
    
    generator.builder_inited(app)
    
    assert generator.builder == app.builder


def test_generate_markdown_files_with_exception(sphinx_build):
    """Test generate_markdown_files when an exception occurs."""
    app, _, _ = sphinx_build
    generator = MarkdownGenerator(app)
    
    # Test with exception
    exception = Exception("Build failed")
    generator.generate_markdown_files(app, exception)
    
    # Should not process files when exception occurs
    assert generator.generated_markdown_files == []
