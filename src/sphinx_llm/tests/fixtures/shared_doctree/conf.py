# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

extensions = ["sphinx_llm.txt", "poc_probe"]
project = "Shared doctree POC"
master_doc = "index"
exclude_patterns = []
html_theme = "alabaster"
llms_txt_full_build = True
llms_txt_experimental_shared_doctrees = True
