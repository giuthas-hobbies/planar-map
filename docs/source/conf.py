import os
import sys

# Point Sphinx to the parent directory where your code lives
sys.path.insert(0, os.path.abspath('../../src/'))

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'planar-map'
copyright = '2026, Pertti Palo'
author = 'Pertti Palo'
release = '0.1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# The key extensions required to parse NumPy style docstrings
extensions = [
    'sphinx.ext.autodoc',      # Core library to pull docstrings
    'sphinx.ext.napoleon',     # To parse NumPy/Google style docstrings
    'sphinx.ext.viewcode',     # To add links to source code in the docs
    'sphinx_autodoc_typehints',  # Optional: formats typehints beautifully
    "myst_parser",              # Parse markdown docs into sphinx html
]

# Tell Sphinx to treat .markdown and .md files as Markdown
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
    '.markdown': 'markdown',
}

# Napoleon settings
napoleon_google_docstring = False
napoleon_numpy_docstring = True

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# Uncomment this AND deal with the resulting errors before trying to run doc
# generation as a github action or similar.
# Add any libraries here that might crash in a headless Linux environment
autodoc_mock_imports = ["PyQt6", "yaml", "tkinter"]

autodoc_type_aliases = {
    'MainWindow': 'planar_map.main_window.MainWindow',
}

# 1. The core Sphinx setting to stop prefixing everything with the module name
add_module_names = False

# 2. Specifically tell autodoc to format type hints as short names
autodoc_typehints_format = "short"

# 3. If you are using sphinx_autodoc_typehints, this is the magic flag
typehints_fully_qualified = False

# 4. Tells Sphinx to try and simplify type names even if they are imported
python_use_unqualified_type_names = True

# 2. Removes the parent module path from the Sidebar/Table of Contents
toc_object_entries_show_parents = 'hide'

# 3. Ensures the class signature in the doc doesn't show the full path
autodoc_class_signature = "separated"

# Tells the index to ignore these prefixes when sorting
modindex_common_prefix = ["planar_map."]
