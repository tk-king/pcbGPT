from __future__ import annotations

import os

DEBUG_PROGRESS = os.getenv("DEBUG_PROGRESS", "1").strip() not in (
    "0",
    "false",
    "False",
    "",
)

OPENAI_REQUEST_TIMEOUT_S = float(
    os.getenv(
        "OPENROUTER_REQUEST_TIMEOUT",
        os.getenv("OPENAI_REQUEST_TIMEOUT", "1200"),
    )
)
