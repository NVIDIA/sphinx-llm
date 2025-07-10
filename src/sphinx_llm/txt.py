"""
Sphinx extension to generate markdown files alongside HTML files.

This extension hooks into the Sphinx build process to create markdown versions
of all HTML files that are generated during the build.
"""

import os
from pathlib import Path
from typing import Any, Dict

from sphinx.application import Sphinx
from sphinx.builders.html import StandaloneHTMLBuilder
from sphinx.util import logging

logger = logging.getLogger(__name__)


class MarkdownGenerator:
    """Generates markdown files alongside HTML files."""
    
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
        """Generate markdown files for all HTML files and concatenate them into llms.txt."""
        if exception:
            logger.warning("Skipping markdown generation due to build error")
            return
        
        if not isinstance(self.builder, StandaloneHTMLBuilder):
            logger.info("Markdown generation only works with HTML builder")
            return
        
        outdir = Path(self.builder.outdir)
        logger.info("Generating markdown files...")
        
        # Find all HTML files in the output directory
        html_files = list(outdir.rglob("*.html"))
        self.generated_markdown_files = []
        
        for html_file in html_files:
            md_file = self._convert_html_to_markdown(html_file)
            if md_file:
                self.generated_markdown_files.append(md_file)
        
        logger.info(f"Generated {len(self.generated_markdown_files)} markdown files")
        
        # Concatenate all markdown files into llms.txt
        llms_txt_path = outdir / "llms.txt"
        with open(llms_txt_path, 'w', encoding='utf-8') as llms_txt:
            for md_file in self.generated_markdown_files:
                with open(md_file, 'r', encoding='utf-8') as f:
                    llms_txt.write(f"# {md_file.name}\n\n")
                    llms_txt.write(f.read())
                    llms_txt.write("\n\n")
        logger.info(f"Concatenated markdown files into: {llms_txt_path}")
    
    def _convert_html_to_markdown(self, html_file: Path):
        """Convert a single HTML file to markdown. Returns the markdown file path or None on failure."""
        try:
            # Read the HTML content
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            # Convert HTML to markdown
            markdown_content = self._html_to_markdown(html_content)
            # Create markdown file path (append .md to the HTML filename)
            markdown_file = html_file.with_name(html_file.name + '.md')
            # Write markdown file
            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            logger.info(f"Generated: {markdown_file}")
            return markdown_file
        except Exception as e:
            logger.warning(f"Failed to convert {html_file}: {e}")
            return None
            
    def _html_to_markdown(self, html_content: str) -> str:
        """Convert HTML content to markdown format."""
        # This is a simple conversion - in a real implementation you might want
        # to use a library like html2text or beautifulsoup for better conversion
        
        # Remove HTML tags and convert basic elements
        import re
        
        # Remove script and style tags and their content
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
        
        # Remove navigation and footer elements
        html_content = re.sub(r'<nav[^>]*>.*?</nav>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<footer[^>]*>.*?</footer>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<div[^>]*class="[^"]*related[^"]*"[^>]*>.*?</div>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<div[^>]*class="[^"]*sphinxsidebar[^"]*"[^>]*>.*?</div>', '', html_content, flags=re.DOTALL)
        
        # Convert headers
        html_content = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<h4[^>]*>(.*?)</h4>', r'#### \1', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<h5[^>]*>(.*?)</h5>', r'##### \1', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<h6[^>]*>(.*?)</h6>', r'###### \1', html_content, flags=re.DOTALL)
        
        # Convert paragraphs
        html_content = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', html_content, flags=re.DOTALL)
        
        # Convert links
        html_content = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', html_content, flags=re.DOTALL)
        
        # Convert bold and italic
        html_content = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', html_content, flags=re.DOTALL)
        
        # Convert lists
        html_content = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1', html_content, flags=re.DOTALL)
        
        # Convert code blocks
        html_content = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', r'```\n\1\n```', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', html_content, flags=re.DOTALL)
        
        # Remove remaining HTML tags
        html_content = re.sub(r'<[^>]*>', '', html_content)
        
        # Decode HTML entities
        import html
        html_content = html.unescape(html_content)
        
        # Clean up whitespace and remove excessive newlines
        html_content = re.sub(r'\n\s*\n\s*\n', '\n\n', html_content)
        html_content = re.sub(r'[¶]', '', html_content)  # Remove paragraph symbols
        html_content = html_content.strip()
        
        return html_content


def setup(app: Sphinx) -> Dict[str, Any]:
    """Set up the Sphinx extension."""
    generator = MarkdownGenerator(app)
    generator.setup()
    
    return {
        'version': '0.0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
