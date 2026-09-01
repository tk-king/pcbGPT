"""Shared test setup for the PCBGPT backend API tests.

All tests run fully offline:

- The whole runtime (SQLite databases, datasets, sync workspaces) is
  redirected into a temporary directory via ``PCBGPT_RUNTIME_ROOT``.
- Every code path that would talk to an LLM / model provider is mocked:
    * ``backend.config.fetch_provider_models``      (provider HTTP calls)
    * ``chat.Runner.run_streamed``              (agent LLM streaming)
    * embedding search / reindex internals      (part library)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

# Redirect the entire runtime into a temp dir *before* any backend import so the
# real sessions.db / settings.db in the repository are never touched.
_TMP_RUNTIME = Path(tempfile.mkdtemp(prefix="pcbgpt-api-tests-"))
import os

os.environ["PCBGPT_RUNTIME_ROOT"] = str(_TMP_RUNTIME)
os.environ["PCBGPT_DATASETS_DIR"] = str(_TMP_RUNTIME / "Datasets")
os.environ["PCBGPT_SETTINGS_DB_PATH"] = str(_TMP_RUNTIME / "settings.db")
os.environ["PCBGPT_SESSIONS_DB_PATH"] = str(_TMP_RUNTIME / "sessions.db")
os.environ["PCBGPT_CUSTOM_SESSIONS_DB_PATH"] = str(_TMP_RUNTIME / "custom_sessions.db")
os.environ["PCBGPT_SYNC_ROOT"] = str(_TMP_RUNTIME / "sync-workspaces")
os.environ["PCBGPT_TMP_DIR"] = str(_TMP_RUNTIME / "tmp")

from fastapi.testclient import TestClient  # noqa: E402

import backend.config as config_module  # noqa: E402
from backend.agent.tools.app_state import _SESSION_CONTEXTS, _SESSION_HISTORIES  # noqa: E402
from backend.agent.tools.routers import parts as parts_router  # noqa: E402
from backend.agent.tools.session_store import init_db, save_session  # noqa: E402

MOCK_PROVIDER_NAME = "mockprovider"
MOCK_BASE_URL = "https://mock.example/v1"
MOCK_API_KEY = "sk-test-key"
MOCK_MODEL_ID = "mock-model"


@pytest.fixture()
def client():
    from backend.agent.tools.fastapi_runner import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset in-memory caches around every test."""
    _SESSION_CONTEXTS.clear()
    _SESSION_HISTORIES.clear()
    parts_router._REINDEX_JOBS.clear()
    yield
    _SESSION_CONTEXTS.clear()
    _SESSION_HISTORIES.clear()
    parts_router._REINDEX_JOBS.clear()


@pytest.fixture()
def mock_provider():
    """Register a custom provider (sqlite only, no network)."""
    provider = config_module.save_custom_provider_settings(
        provider_name="MockProvider",
        base_url=MOCK_BASE_URL,
        api_key=MOCK_API_KEY,
        default_model=MOCK_MODEL_ID,
        models=[{"id": MOCK_MODEL_ID, "name": "Mock Model"}],
    )
    yield provider


@pytest.fixture()
def seeded_session(tmp_path):
    """A persisted session row plus a KiCad project folder on disk."""
    session_id = "sess-fixture-1234"

    project_dir = tmp_path / "my_project"
    project_dir.mkdir()
    (project_dir / "main.kicad_sch").write_text("(kicad_sch)")

    context = {
        "kicad_project_path": str(project_dir),
        "kicad_project_name": "my_project",
        "circuit": None,
    }
    history = [{"role": "user", "content": "hello"}]
    save_session(session_id, context, history)
    return {"session_id": session_id, "context": context, "project_dir": project_dir}


def _make_usage():
    class Usage:
        requests = 1
        input_tokens = 10
        output_tokens = 5
        total_tokens = 15
        max_total_tokens = 0
        input_tokens_details = {}
        output_tokens_details = {}

    return Usage()


class FakeEventStream:
    """Stand-in for the agent runner's streamed event stream (no LLM)."""

    def __init__(self, events):
        self._events = list(events)
        self.messages = [
            {"role": "assistant", "content": "Mock answer", "tool_calls": None}
        ]
        self.context_wrapper = type("CtxWrapper", (), {"usage": _make_usage()})()

    async def stream_events(self):
        for event in self._events:
            yield event

    async def aclose(self):
        pass


class FakeRunner:
    """Stand-in for backend.core.agents.Runner (never contacts a provider)."""

    def __init__(self, events=None):
        self._events = events or [
            {"type": "start", "data": {}},
            {
                "type": "assistant_delta",
                "data": {"delta": "Mock answer"},
            },
            {
                "type": "tool_call",
                "data": {
                    "id": "call_1",
                    "name": "search_components",
                    "args": {"query": "resistor"},
                },
            },
            {
                "type": "tool_result",
                "data": {
                    "id": "call_1",
                    "name": "search_components",
                    "output": "[]",
                },
            },
            {
                "type": "assistant_message",
                "data": {
                    "content": "Mock answer",
                    "tool_calls": [
                        {"id": "call_1", "name": "search_components", "args": {}}
                    ],
                },
            },
            {"type": "done", "data": {}},
        ]

    def run_streamed(
        self,
        agent,
        user_input,
        context=None,
        session=None,
        max_turns=None,
    ):
        return FakeEventStream(self._events)


@pytest.fixture()
def fake_runner(monkeypatch):
    """Patch the chat router's Runner so websocket chats never hit an LLM."""
    from backend.agent.tools.routers import chat as chat_router

    # Avoid constructing a real OpenAI client for the generation model.
    monkeypatch.setattr(
        chat_router,
        "_build_agent_with_generation_model",
        lambda base_agent, model_name: base_agent,
    )
    runner = FakeRunner()
    monkeypatch.setattr(chat_router, "Runner", runner)
    return runner


def read_ws_until(client_websocket, wanted_type: str, max_frames: int = 200) -> dict:
    """Read websocket frames until an event of ``wanted_type`` arrives."""
    for _ in range(max_frames):
        frame = client_websocket.receive_json()
        event = frame.get("event") or {}
        if event.get("type") == wanted_type:
            return frame
    raise AssertionError(f"Never received a {wanted_type!r} event")


init_db()
