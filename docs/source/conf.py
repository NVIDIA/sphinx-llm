# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Configuration for the primary project documentation."""

project = "sphinx-llm"
author = "NVIDIA Corporation"
copyright = "2026, NVIDIA Corporation"

extensions = ["sphinx_llm.txt", "sphinx_llm.docref"]
html_theme = "nvidia_sphinx_theme"
html_theme_options = {
    "public_docs_features": True,
    "show_nav_level": 2,
    "collapse_navigation": False,
    "navigation_depth": 3,
}

# Dogfood LLM-friendly output without requiring a provider or network access.
llms_txt_summary_enabled = False
llms_txt_description = "Sphinx extensions for LLM-friendly documentation and build-time content generation."
