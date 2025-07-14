"""
Sphinx extension to generate markdown files alongside HTML files.

This extension hooks into the Sphinx build process to create markdown versions
of all documents using the sphinx_markdown_builder.
"""

import os
from pathlib import Path
from typing import Any, Dict, Union

from sphinx.application import Sphinx
from sphinx.builders.html import StandaloneHTMLBuilder
from sphinx.util import logging

from .version import __version__


logger = logging.getLogger(__name__)


class MarkdownGenerator:
    """Generates markdown files using sphinx_markdown_builder."""
    
    def __init__(self, app: Sphinx):
        self.app = app
        self.generated_markdown_files = []  # Track generated markdown files
    
    def setup(self):
        """Set up the extension."""
        # Connect to the build-finished event to generate markdown files
        self.app.connect('build-finished', self.generate_markdown_files)
    
    def generate_markdown_files(self, app: Sphinx, exception: Union[Exception, None]):
        """Generate markdown files using sphinx_markdown_builder and concatenate them into llms.txt."""
        if exception:
            logger.warning("Skipping markdown generation due to build error")
            return
        
        if not self.app.builder or self.app.builder.name not in ["html", "dirhtml"]:
            logger.info("Markdown generation only works with HTML builders (html or dirhtml)")
            return
        
        outdir = Path(self.app.builder.outdir)
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
                
                # Determine target file location based on builder and file type
                if self.app.builder and self.app.builder.name == "dirhtml":
                    target_file = outdir / new_name if base_name == "index" else outdir / rel_path.with_suffix("") / "index.html.md"
                else:
                    target_file = outdir / rel_path.parent / new_name if rel_path.parent != Path('.') else outdir / new_name
                logger.info(f"Copying markdown file to: {target_file}")
                
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
            
            # Create sitemap in llms.txt
            self.create_sitemap(outdir, app)
            
        except Exception as e:
            logger.error(f"Failed to generate markdown files: {e}")
        finally:
            # Clean up temporary build directory
            if md_build_dir.exists():
                import shutil
                shutil.rmtree(md_build_dir)
    
    def create_sitemap(self, outdir: Path, app: Sphinx):
        """Create a markdown sitemap in llms.txt."""
        llms_txt_path = outdir / "llms.txt"
        
        with open(llms_txt_path, 'w', encoding='utf-8') as sitemap:
            # Write the title and description
            project_title = getattr(app.config, 'project', 'Documentation')
            sitemap.write(f"# {project_title}\n\n")
            
            # Add optional description if available
            if hasattr(app.config, 'html_title') and app.config.html_title:
                sitemap.write(f"> {app.config.html_title}\n\n")
            
            # Add project details if available
            if hasattr(app.config, 'copyright') and app.config.copyright:
                sitemap.write(f"{app.config.copyright}\n\n")
            
            # Write the main content section
            sitemap.write("## Pages\n\n")
            
            # Sort files to ensure index.html.md comes first
            sorted_files = sorted(self.generated_markdown_files, key=lambda x: (x.name != 'index.html.md', x.name))
            
            for md_file in sorted_files:
                # Extract title from the markdown file
                title = self.extract_title_from_markdown(md_file)
                
                # Create the URL based on builder type
                base_name = md_file.stem.replace('.html', '')
                if base_name == 'index':
                    url = "index.html"
                elif self.app.builder and self.app.builder.name == "dirhtml":
                    # For dirhtml builder: apples/index.html.md -> apples/
                    url = f"{base_name}/"
                else:
                    # For html builder: apples.html.md -> apples.html
                    url = f"{base_name}.html"
                
                # Write the link
                sitemap.write(f"- [{title}]({url}): {self.get_page_description(md_file)}\n")
            
            logger.info(f"Created sitemap: {llms_txt_path}")
    
    def extract_title_from_markdown(self, md_file: Path) -> str:
        """Extract the title from a markdown file."""
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
                # Look for the first heading (starts with #)
                for line in lines:
                    line = line.strip()
                    if line.startswith('#'):
                        title = line.lstrip('#').strip()
                        return title
                
                # If no heading found, try to get title from filename
                base_name = md_file.stem.replace('.html', '')
                if base_name == 'index':
                    return "Home"
                return base_name.replace('_', ' ').title()
        except Exception:
            # Fallback to filename without extension
            base_name = md_file.stem.replace('.html', '')
            if base_name == 'index':
                return "Home"
            return base_name.replace('_', ' ').title()
    
    def get_page_description(self, md_file: Path) -> str:
        """Get a brief description of the page content."""
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
                # Skip HTML comments and look for the first meaningful paragraph
                for line in lines:
                    line = line.strip()
                    # Skip empty lines, headings, and HTML comments
                    if (line and 
                        not line.startswith('#') and 
                        not line.startswith('<!--') and 
                        not line.startswith('-->') and
                        not line.startswith('..') and
                        len(line) > 10):  # Ensure it's substantial content
                        return line[:100] + "..." if len(line) > 100 else line
                
                # Fallback descriptions based on filename
                base_name = md_file.stem.replace('.html', '')
                if base_name == 'index':
                    return "Main documentation page"
                elif base_name == 'test':
                    return "Testing and example page"
                else:
                    return "Page content"
        except Exception:
            # Fallback descriptions based on filename
            base_name = md_file.stem.replace('.html', '')
            if base_name == 'index':
                return "Main documentation page"
            elif base_name == 'test':
                return "Testing and example page"
            else:
                return "Page content"


def setup(app: Sphinx) -> Dict[str, Any]:
    """Set up the Sphinx extension."""
    generator = MarkdownGenerator(app)
    generator.setup()
    
    return {
        'version': __version__,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
