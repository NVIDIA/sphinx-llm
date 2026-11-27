# SPDX-FileCopyrightText: Copyright (c) 0000, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Literal, Optional

# Handle when there's no openapi library.
try:
    from openai.types import ReasoningEffort
except ImportError:
    ReasoningEffort = Optional[Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]]
