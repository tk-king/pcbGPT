import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from backend.agent.tools.fastapi_runner import app


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid {name}={raw!r}. Expected a number.") from exc


def main() -> None:
    """Run the PCBGPT FastAPI server."""
    ws_ping_interval = _env_float("PCBGPT_WS_PING_INTERVAL_S", 60.0)
    ws_ping_timeout = _env_float("PCBGPT_WS_PING_TIMEOUT_S", 300.0)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        ws_ping_interval=ws_ping_interval,
        ws_ping_timeout=ws_ping_timeout,
    )

if __name__ == "__main__":
    main()
