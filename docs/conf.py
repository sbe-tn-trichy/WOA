"""Sphinx configuration for zoho-sdk documentation."""
import os
import sys

# Add src to sys.path
sys.path.insert(0, os.path.abspath("../src"))

project = "zoho-sdk"
copyright = "2026, Zoho SDK Contributors"
author = "Zoho SDK Contributors"
release = "0.2.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
]

# Support Markdown parser if available
try:
    import myst_parser  # noqa: F401
    extensions.append("myst_parser")
    source_suffix = {
        ".rst": "restructuredtext",
        ".md": "markdown",
    }
except ImportError:
    source_suffix = [".rst", ".md"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "alabaster"
html_static_path = ["_static"]
