#
# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "ProxyPatternPool"
copyright = "2022-2025, Calvin"
author = "Calvin"

from importlib.metadata import version as pkg_version
release = pkg_version("ProxyPatternPool")

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

source_suffix = [".md", ".rst"]

extensions = ["myst_parser", "autoapi.extension"]

autoapi_dirs = [".."]
autoapi_ignore = ["*/venv/*", "*/test/*"]
autoapi_options = ["members", "show-inheritance", "show-module-summary", "special-members", "imported-members"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
