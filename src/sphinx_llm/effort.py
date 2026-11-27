from typing import Literal, Optional

# Handle when there's no openapi library.
try:
    from openai.types import ReasoningEffort
except ImportError:
    ReasoningEffort = Optional[Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]]
