"""
Sphinx extension to generate markdown files alongside HTML files.

This extension hooks into the Sphinx build process to create markdown versions
of all documents using the sphinx_markdown_builder.
"""

import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, metadata
from pathlib import Path
from typing import Any, Union

from sphinx.application import Sphinx
from sphinx.util import logging

from .version import __version__

logger = logging.getLogger(__name__)


class MarkdownGenerator:
    """Generates markdown files using sphinx_markdown_builder."""

    def __init__(self, app: Sphinx):
        self.app = app
        self.generated_markdown_files = []  # Track generated markdown files
        self.outdir = None
        self.md_build_dir = None
        self.md_build_process = None
        self.md_build_logfile = tempfile.NamedTemporaryFile(
            mode="w", delete=False, prefix="sphinx_llm_output_", suffix=".log"
        )

    def setup(self):
        """Set up the extension."""
        self.app.connect("builder-inited", self.build_llms_txt)

    def build_llms_txt(self, app: Sphinx):
        """Generate markdown files using sphinx_markdown_builder and concatenate them into llms.txt."""
        self.outdir = Path(app.builder.outdir)
        self.md_build_dir = self.outdir / "_markdown_build"

        if app.builder and app.builder.name == "markdown":
            return

        if not app.builder or app.builder.name not in ["html", "dirhtml"]:
            logger.info(
                "llms.txt generation only works with HTML builders (html or dirhtml), skipping..."
            )
            return

        # Start the markdown builder subproces in the background
        self.build_markdown_files()
        # Once the primary build is finished, combine the markdown files
        self.app.connect("build-finished", self.combine_builds)

    def combine_builds(self, app: Sphinx, exception: Union[Exception, None]):
        """Combine the markdown files into llms-full.txt and llms.txt and merge the build outputs together."""
        if exception:
            logger.warning("Skipping build combination due to build error")
            return

        if not self.md_build_process:
            logger.warning(
                "Markdown build process not found, skipping build combination"
            )
            return

        if self.md_build_process.poll() is None:
            logger.info("Waiting for markdown build subprocess to finish...")
            self.md_build_process.wait()
            logger.info("Markdown build subprocess finished")

        if self.md_build_process.returncode != 0:
            logger.error(
                f"Markdown build subprocess failed with return code {self.md_build_process.returncode},"
                f" see {self.md_build_logfile.name} for details"
            )
            return

        try:
            # Copy markdown files to the main output directory
            self.copy_markdown_files()

            # Concatenate all markdown files into llms-full.txt
            self.build_llms_full_txt()

            # Create sitemap in llms.txt
            self.create_sitemap()
        finally:
            # Clean up temporary build directory
            if self.md_build_dir.exists():
                shutil.rmtree(self.md_build_dir)

    def build_markdown_files(self):
        # Create temporary markdown build directory
        self.md_build_dir.mkdir(exist_ok=True)
        try:
            # Build markdown files using sphinx-markdown-builder
            sphinx_build_cmd = [
                sys.executable,
                "-m",
                "sphinx",
                "-b",
                "markdown",
                str(self.app.srcdir),
                str(self.md_build_dir),
            ]

            logger.info(
                f"Spawning additional sphinx subprocess to build markdown files for llms.txt: {' '.join(sphinx_build_cmd)}"
            )
            try:
                logger.info(
                    f"Subprocess output available at: {self.md_build_logfile.name}"
                )

                with self.md_build_logfile:
                    self.md_build_process = subprocess.Popen(
                        sphinx_build_cmd,
                        stdout=self.md_build_logfile,
                        stderr=self.md_build_logfile,
                    )
            except Exception as exc:
                logger.error(f"Failed to run sphinx-build subprocess: {exc}")
        except Exception as e:
            logger.error(f"Failed to generate markdown files: {e}")

    def copy_markdown_files(self):
        # Find all markdown files in the build directory
        md_files = list(self.md_build_dir.rglob("*.md"))
        self.generated_markdown_files = []

        # Copy markdown files to the main output directory with renamed format
        for md_file in md_files:
            # Get relative path from build directory
            rel_path = md_file.relative_to(self.md_build_dir)

            # Rename to follow the format: filename.html.md
            # Remove the .md extension and add .html.md
            base_name = rel_path.stem
            new_name = f"{base_name}.html.md"

            # Determine target file location based on builder and file type
            if self.app.builder and self.app.builder.name == "dirhtml":
                target_file = (
                    self.outdir / new_name
                    if base_name == "index"
                    else self.outdir / rel_path.with_suffix("") / "index.html.md"
                )
            else:
                target_file = (
                    self.outdir / rel_path.parent / new_name
                    if rel_path.parent != Path(".")
                    else self.outdir / new_name
                )

            # Ensure target directory exists
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy the file with the new name
            shutil.copy2(md_file, target_file)
            self.generated_markdown_files.append(target_file)

        logger.info(f"Generated {len(self.generated_markdown_files)} context files")

    def build_llms_full_txt(self):
        # Concatenate all markdown files into llms-full.txt
        llms_txt_path = self.outdir / "llms-full.txt"
        with open(llms_txt_path, "w", encoding="utf-8") as llms_txt:
            # Sort files to ensure index.html.md comes first
            sorted_files = sorted(
                self.generated_markdown_files,
                key=lambda x: (x.name != "index.html.md", x.name),
            )

            for md_file in sorted_files:
                with open(md_file, encoding="utf-8") as f:
                    llms_txt.write(f"# {md_file.name}\n\n")
                    llms_txt.write(f.read())
                    llms_txt.write("\n\n")
        logger.info(f"Concatenated full context into: {llms_txt_path}")

    def get_project_description(self) -> str:
        """Get the description of the project."""
        project_title = getattr(self.app.config, "project", "Documentation")
        if (
            hasattr(self.app.config, "llms_txt_description")
            and self.app.config.llms_txt_description
        ):
            return self.app.config.llms_txt_description

        try:
            meta_description = metadata(project_title).get("Description")
            if meta_description:
                return meta_description
        except PackageNotFoundError:
            pass

        if hasattr(self.app.config, "html_title") and self.app.config.html_title:
            return self.app.config.html_title

        return f"Documentation for {project_title}"

    def create_sitemap(self):
        """Create a markdown sitemap in llms.txt."""
        llms_txt_path = self.outdir / "llms.txt"

        with open(llms_txt_path, "w", encoding="utf-8") as sitemap:
            # Write the title
            project_title = getattr(self.app.config, "project", "Documentation")
            sitemap.write(f"# {project_title}\n\n")

            # Add description
            for line in self.get_project_description().strip().split("\n"):
                sitemap.write(f"> {line}\n")
            sitemap.write("\n\n")

            # Add project details if available
            if hasattr(self.app.config, "copyright") and self.app.config.copyright:
                sitemap.write(f"{self.app.config.copyright}\n\n")

            # Write the main content section
            sitemap.write("## Pages\n\n")

            # Sort files to ensure index.html.md comes first
            sorted_files = sorted(
                self.generated_markdown_files,
                key=lambda x: (x.name != "index.html.md", x.name),
            )

            for md_file in sorted_files:
                # Extract title from the markdown file
                title = self.extract_title_from_markdown(md_file)

                # Create the URL based on the relative path from output directory
                rel_path = md_file.relative_to(self.outdir)
                url = str(rel_path)

                # Write the link
                sitemap.write(
                    f"- [{title}]({url}): {self.get_page_description(md_file)}\n"
                )

            logger.info(f"Created llms.txt sitemap: {llms_txt_path}")

    def extract_title_from_markdown(self, md_file: Path) -> str:
        """Extract the title from a markdown file."""
        try:
            with open(md_file, encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")

                # Look for the first heading (starts with #)
                for line in lines:
                    line = line.strip()
                    if line.startswith("#"):
                        title = line.lstrip("#").strip()
                        return title

                # If no heading found, try to get title from filename
                base_name = md_file.stem.replace(".html", "")
                if base_name == "index":
                    return "Home"
                return base_name.replace("_", " ").title()
        except Exception:
            # Fallback to filename without extension
            base_name = md_file.stem.replace(".html", "")
            if base_name == "index":
                return "Home"
            return base_name.replace("_", " ").title()

    def get_page_description(self, md_file: Path) -> str:
        """Get a brief description of the page content."""
        try:
            with open(md_file, encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")

                # Skip HTML comments and look for the first meaningful paragraph
                for line in lines:
                    line = line.strip()
                    # Skip empty lines, headings, and HTML comments
                    if (
                        line
                        and not line.startswith("#")
                        and not line.startswith("<!--")
                        and not line.startswith("-->")
                        and not line.startswith("..")
                        and len(line) > 10
                    ):  # Ensure it's substantial content
                        return line[:100] + "..." if len(line) > 100 else line

                # Fallback descriptions based on filename
                base_name = md_file.stem.replace(".html", "")
                if base_name == "index":
                    return "Main documentation page"
                elif base_name == "test":
                    return "Testing and example page"
                else:
                    return "Page content"
        except Exception:
            # Fallback descriptions based on filename
            base_name = md_file.stem.replace(".html", "")
            if base_name == "index":
                return "Main documentation page"
            elif base_name == "test":
                return "Testing and example page"
            else:
                return "Page content"


def setup(app: Sphinx) -> dict[str, Any]:
    """Set up the Sphinx extension."""
    app.add_config_value("llms_txt_description", "", "env")
    generator = MarkdownGenerator(app)
    generator.setup()

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
