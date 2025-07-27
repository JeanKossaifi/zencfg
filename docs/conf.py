# Configuration file for the Sphinx documentation builder.
import os
import sys
sys.path.insert(0, os.path.abspath('../src'))

# Import version from package
from zencfg import __version__

# Project information
project = 'ZenCFG'
copyright = '2025, Jean Kossaifi'
author = 'Jean Kossaifi'

# Version info - dynamically imported from package
version = '.'.join(__version__.split('.')[:2])  # Short X.Y version 
release = __version__  # Full version including patch

# Extensions
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx_copybutton',
    'sphinx_design',
]

# Theme
html_theme = 'pydata_sphinx_theme'
html_title = "ZenCFG Documentation"
html_show_sourcelink = False

html_theme_options = {
    'show_prev_next': True,
    'icon_links': [
        {
            'name': 'GitHub',
            'url': 'https://github.com/jeankossaifi/zencfg',
            'icon': 'fab fa-github-square',
        },
    ],
}

html_sidebars = {
    "**": []
}

# Options
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# Intersphinx
intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
}

# Copy button
copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: "
copybutton_prompt_is_regexp = True
