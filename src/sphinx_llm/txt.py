"""
Sphinx extension to generate markdown files alongside HTML files.

This extension hooks into the Sphinx build process to create markdown versions
of all documents using the sphinx_markdown_builder.
"""

import os
from pathlib import Path
from typing import Any, Dict

from sphinx.application import Sphinx
from sphinx.builders.html import StandaloneHTMLBuilder
from sphinx.util import logging

logger = logging.getLogger(__name__)


class MarkdownGenerator:
    """Generates markdown files using sphinx_markdown_builder."""
    
    def __init__(self, app: Sphinx):
        self.app = app
        self.builder = None
        self.generated_markdown_files = []  # Track generated markdown files
    
    def setup(self):
        """Set up the extension."""
        # Connect to the builder-inited event to get the builder instance
        self.app.connect('builder-inited', self.builder_inited)
        # Connect to the build-finished event to generate markdown files
        self.app.connect('build-finished', self.generate_markdown_files)
    
    def builder_inited(self, app: Sphinx):
        """Called when the builder is initialized."""
        self.builder = app.builder
    
    def generate_markdown_files(self, app: Sphinx, exception: Exception | None):
        """Generate markdown files using sphinx_markdown_builder and concatenate them into llms.txt."""
        if exception:
            logger.warning("Skipping markdown generation due to build error")
            return
        
        if not isinstance(self.builder, StandaloneHTMLBuilder):
            logger.info("Markdown generation only works with HTML builder")
            return
        
        outdir = Path(self.builder.outdir)
        logger.info("Generating markdown files using sphinx_markdown_builder...")
        
        # Create a temporary markdown build directory
        md_build_dir = outdir / "_markdown_build"
        md_build_dir.mkdir(exist_ok=True)
        
        try:
            # Build markdown files using sphinx_markdown_builder
            from sphinx_markdown_builder import MarkdownBuilder
            
            # Create a new app instance for markdown building
            md_app = Sphinx(
                srcdir=str(app.srcdir),
                confdir=str(app.confdir),
                outdir=str(md_build_dir),
                doctreedir=str(app.doctreedir),
                buildername='markdown',
                confoverrides=app.config.__dict__.copy(),
                status=None,
                warning=None,
                freshenv=False,
                warningiserror=False,
                tags=(),
                verbosity=0,
                parallel=0,
                keep_going=False,
                pdb=False
            )
            
            # Build the markdown files
            md_app.build()
            
            # Find all markdown files in the build directory
            md_files = list(md_build_dir.rglob("*.md"))
            self.generated_markdown_files = []
            
            # Copy markdown files to the main output directory with renamed format
            for md_file in md_files:
                # Get relative path from build directory
                rel_path = md_file.relative_to(md_build_dir)
                
                # Rename to follow the format: filename.html.md
                # Remove the .md extension and add .html.md
                base_name = rel_path.stem
                new_name = f"{base_name}.html.md"
                target_file = outdir / new_name
                
                # Ensure target directory exists
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy the file with the new name
                import shutil
                shutil.copy2(md_file, target_file)
                self.generated_markdown_files.append(target_file)
                logger.info(f"Generated: {target_file}")
            
            logger.info(f"Generated {len(self.generated_markdown_files)} markdown files")
            
            # Concatenate all markdown files into llms-full.txt
            llms_txt_path = outdir / "llms-full.txt"
            with open(llms_txt_path, 'w', encoding='utf-8') as llms_txt:
                # Sort files to ensure index.html.md comes first
                sorted_files = sorted(self.generated_markdown_files, key=lambda x: (x.name != 'index.html.md', x.name))
                
                for md_file in sorted_files:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        llms_txt.write(f"# {md_file.name}\n\n")
                        llms_txt.write(f.read())
                        llms_txt.write("\n\n")
            logger.info(f"Concatenated markdown files into: {llms_txt_path}")
            
        except Exception as e:
            logger.error(f"Failed to generate markdown files: {e}")
        finally:
            # Clean up temporary build directory
            if md_build_dir.exists():
                import shutil
                shutil.rmtree(md_build_dir)


def setup(app: Sphinx) -> Dict[str, Any]:
    """Set up the Sphinx extension."""
    generator = MarkdownGenerator(app)
    generator.setup()
    
    return {
        'version': '0.0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
