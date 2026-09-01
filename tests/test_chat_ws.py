"""Tests for the /chat websocket endpoint. The LLM runner is fully mocked."""

from __future__ import annotations

import asyncio

from backend.agent.tools.app_state import _SESSION_CONTEXTS, _SESSION_HISTORIES
from backend.agent.tools.session_store import load_session

from tests.conftest import (
    MOCK_MODEL_ID,
    MOCK_PROVIDER_NAME,
    FakeEventStream,
    FakeRunner,
    read_ws_until,
)


def _system_settings():
    return {
        "system_settings": {
            "generation_model": f"{MOCK_PROVIDER_NAME}.{MOCK_MODEL_ID}",
            "validation_enabled": False,
        }
    }


class HangingEventStream(FakeEventStream):
    """A stream that never finishes — used to test cancellation."""

    def __init__(self):
        super().__init__(
            [
                {"type": "start", "data": {}},
                {"type": "assistant_delta", "data": {"delta": "Partial answer"}},
                {"type": "assistant_message", "data": {"content": "Partial answer"}},
            ]
        )
        self.messages = [
            {"role": "assistant", "content": "Partial answer", "tool_calls": None}
        ]

    async def stream_events(self):
        for event in self._events:
            yield event
        await asyncio.Future()  # hang forever until cancelled


def test_chat_streams_events_and_persists_session(client, mock_provider, fake_runner):
    with client.websocket_connect("/chat") as ws:
        # Initial sessions snapshot is always sent.
        initial = ws.receive_json()
        assert initial["event"]["type"] == "sessions"
        assert isinstance(initial["event"]["sessions"], list)

        ws.send_json({"input": "Design an LED circuit", **_system_settings()})

        text_frame = read_ws_until(ws, "text")
        assert text_frame["event"]["delta"] == "Mock answer"

        tool_frame = read_ws_until(ws, "tool_call")
        assert tool_frame["event"]["name"] == "search_components"

        result_frame = read_ws_until(ws, "tool_result")
        assert result_frame["event"]["tool_call_id"] == "call_1"

        done_frame = read_ws_until(ws, "done")

    session_id = done_frame["session_id"]
    context, history = load_session(session_id)
    assert context is not None
    roles = [m["role"] for m in history]
    assert roles[0] == "user"
    assert "assistant" in roles
    assert "tool" in roles


def test_chat_rejects_message_without_input(client, mock_provider, fake_runner):
    with client.websocket_connect("/chat") as ws:
        ws.receive_json()  # initial sessions event
        ws.send_json(_system_settings())

        error = read_ws_until(ws, "error")
        assert error["event"]["message"] == "Missing 'input' in message payload."


def test_chat_accepts_plain_text_messages(client, mock_provider, fake_runner):
    with client.websocket_connect("/chat") as ws:
        ws.receive_json()  # initial sessions event
        ws.send_text("hello over plain text")

        done_frame = read_ws_until(ws, "done")
        session_id = done_frame["session_id"]
        context, history = load_session(session_id)
        assert history[0]["content"] == "hello over plain text"


def test_chat_without_generation_model_reports_error(client, fake_runner, monkeypatch):
    # Force "no model configured" regardless of settings persisted by other tests.
    import backend.agent.tools.utils as utils_module

    monkeypatch.setattr(
        utils_module,
        "_default_system_settings",
        lambda: {
            "generation_model": None,
            "validation_model": None,
            "validation_enabled": False,
        },
    )
    with client.websocket_connect("/chat") as ws:
        ws.receive_json()
        ws.send_json({"input": "hi"})

        error = read_ws_until(ws, "error")
        assert "No generation model" in error["event"]["message"]


def test_chat_cancel_stops_stream(client, mock_provider, monkeypatch):
    from backend.agent.tools.routers import chat as chat_router

    monkeypatch.setattr(
        chat_router,
        "_build_agent_with_generation_model",
        lambda base_agent, model_name: base_agent,
    )
    monkeypatch.setattr(chat_router, "Runner", HangingFakeRunner())

    with client.websocket_connect("/chat") as ws:
        ws.receive_json()
        ws.send_json({"input": "long running task", **_system_settings()})

        text_frame = read_ws_until(ws, "text")
        session_id = text_frame["session_id"]

        ws.send_json({"action": "cancel", "session_id": session_id})

        cancelled = read_ws_until(ws, "cancelled")
        assert cancelled["event"]["message"] == "Generation stopped."

    # The partial assistant answer was persisted.
    _, history = load_session(session_id)
    assistant_texts = [
        m.get("content") for m in history if m.get("role") == "assistant"
    ]
    assert "Partial answer" in assistant_texts


class HangingFakeRunner(FakeRunner):
    def run_streamed(self, agent, user_input, context=None, session=None, max_turns=None):
        return HangingEventStream()


def test_chat_second_input_while_running_is_rejected(client, mock_provider, monkeypatch):
    from backend.agent.tools.routers import chat as chat_router

    monkeypatch.setattr(
        chat_router,
        "_build_agent_with_generation_model",
        lambda base_agent, model_name: base_agent,
    )

    class SlowRunner(FakeRunner):
        def run_streamed(self, agent, user_input, context=None, session=None, max_turns=None):
            stream = FakeEventStream([])

            async def hang():
                await asyncio.sleep(3)
                yield {"type": "done", "data": {}}

            stream.stream_events = hang
            return stream

    monkeypatch.setattr(chat_router, "Runner", SlowRunner())

    with client.websocket_connect("/chat") as ws:
        ws.receive_json()
        ws.send_json({"input": "first", **_system_settings()})
        ws.send_json({"input": "second", **_system_settings()})

        error = read_ws_until(ws, "error")
        assert "already running" in error["event"]["message"]

        done_frame = read_ws_until(ws, "done")
        assert done_frame["event"]["type"] == "done"


def test_chat_resumes_existing_session(client, mock_provider, fake_runner, seeded_session):
    session_id = seeded_session["session_id"]
    with client.websocket_connect("/chat") as ws:
        ws.receive_json()
        ws.send_json(
            {"input": "follow-up", "session_id": session_id, **_system_settings()}
        )
        done_frame = read_ws_until(ws, "done")
        assert done_frame["session_id"] == session_id

    _, history = load_session(session_id)
    assert history[0]["content"] == "hello"  # seeded user message preserved
    assert any(m.get("role") == "user" and m.get("content") == "follow-up" for m in history)
