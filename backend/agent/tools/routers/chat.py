import asyncio
import contextlib
import json
import uuid
from dataclasses import asdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.agent.tools.app_state import _SESSION_CONTEXTS, _SESSION_HISTORIES
from backend.agent.tools.session_store import list_sessions, load_session, normalize_history, save_session
from backend.agent.tools.utils import (
    _apply_system_settings_to_context,
    _build_agent_with_generation_model,
    _build_sync_prefix,
    _configure_agent_for_interactive_request,
    _extract_system_settings,
    _filter_context_for_dataclass,
    _merge_context,
    _save_custom_provider_from_payload,
    _usage_metrics_payload,
)
import backend.runtime_paths
from backend.core.agents import Runner, SQLiteSession

router = APIRouter()


def process_event(event):
    if not isinstance(event, dict):
        return None
    etype = event.get("type")
    data = event.get("data") or {}
    if etype == "start":
        return None
    if etype == "assistant_delta":
        delta = data.get("delta")
        if not isinstance(delta, str) or not delta:
            return None
        return {"type": "text", "delta": delta}
    if etype == "assistant_message":
        return None
    if etype == "tool_call":
        tool_call_id = data.get("id") or ""
        return {
            "type": "tool_call",
            "id": tool_call_id,
            "tool_call_id": tool_call_id,
            "name": data.get("name"),
            "args": data.get("args"),
        }
    if etype == "tool_progress":
        tool_call_id = data.get("id") or ""
        return {
            "type": "tool_progress",
            "id": tool_call_id,
            "tool_call_id": tool_call_id,
            "name": data.get("name"),
            "message": data.get("message"),
        }
    if etype == "tool_result":
        tool_call_id = data.get("id") or ""
        return {
            "type": "tool_result",
            "id": tool_call_id,
            "tool_call_id": tool_call_id,
            "name": data.get("name"),
            "output": data.get("output"),
        }
    if etype == "error":
        return {"type": "error", "message": (data.get("error") or "unknown error")}
    if etype == "done":
        return {"type": "done"}
    return None


def _is_cancel_message(message: dict, session_id: str) -> bool:
    if not isinstance(message, dict):
        return False
    action = str(message.get("action") or message.get("type") or "").strip().lower()
    if action not in {"cancel", "stop"}:
        return False
    requested_session_id = message.get("session_id")
    return not requested_session_id or requested_session_id == session_id


def _summarize_runtime_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    lowered = message.lower()
    if "exceededbudget" in lowered or "over budget" in lowered:
        return (
            "The selected provider rejected the request because the account is over budget. "
            "Please check provider billing or switch to another provider/model."
        )
    if "invalid api key" in lowered or "incorrect api key" in lowered or "unauthorized" in lowered:
        return (
            "The selected provider rejected the request due to invalid credentials. "
            "Please update the provider API key in settings."
        )
    return f"Request failed: {message}"


@router.websocket("/chat")
async def chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connection accepted")
    session_id = uuid.uuid4().hex
    try:
        await websocket.send_json(
            {
                "event": {"type": "sessions", "sessions": list_sessions()},
                "session_id": session_id,
            }
        )
    except WebSocketDisconnect:
        return
    try:
        while True:
            try:
                raw_text = await websocket.receive_text()
            except WebSocketDisconnect:
                return
            try:
                message = json.loads(raw_text)
            except json.JSONDecodeError:
                message = {"input": raw_text}
            if not isinstance(message, dict):
                await websocket.send_json(
                    {
                        "event": {
                            "type": "error",
                            "message": "Invalid message format. Expected JSON object with 'input'.",
                        },
                        "session_id": session_id,
                    }
                )
                continue
            if "input" not in message:
                await websocket.send_json(
                    {
                        "event": {
                            "type": "error",
                            "message": "Missing 'input' in message payload.",
                        },
                        "session_id": session_id,
                    }
                )
                continue
            try:
                system_settings = _extract_system_settings(message)
            except ValueError as exc:
                await websocket.send_json(
                    {
                        "event": {
                            "type": "error",
                            "message": str(exc),
                        },
                        "session_id": session_id,
                    }
                )
                continue
            from backend.agent.Core.agent import (
                AgentContext as AgentContext,
                agent,
            )

            requested_session_id = message.get("session_id")
            if isinstance(requested_session_id, str) and requested_session_id:
                session_id = requested_session_id

            context = _SESSION_CONTEXTS.get(session_id)
            if context is None:
                db_context, db_history = load_session(session_id)
                if db_context is not None and db_history is not None:
                    context_obj = AgentContext(
                        **_filter_context_for_dataclass(db_context, AgentContext)
                    )
                    history = db_history
                    context = db_context
                else:
                    context_obj = AgentContext()
                    history = []
                    context = {}
                context_payload = _merge_context(context, asdict(context_obj))
                _SESSION_CONTEXTS[session_id] = context_payload
                _SESSION_HISTORIES[session_id] = history
            else:
                context_obj = AgentContext(
                    **_filter_context_for_dataclass(context, AgentContext)
                )
                history = _SESSION_HISTORIES.get(session_id, [])
            _apply_system_settings_to_context(context_obj, system_settings)
            context_payload = _merge_context(context, asdict(context_obj))
            _SESSION_CONTEXTS[session_id] = context_payload
            request_agent = _build_agent_with_generation_model(
                agent,
                system_settings["generation_model"],
            )

            user_input = message["input"]
            request_agent = _configure_agent_for_interactive_request(
                request_agent,
                user_input,
                context_payload,
            )
            prefix = _build_sync_prefix(context_payload)
            if prefix:
                user_input = prefix + user_input

            history.append({"role": "user", "content": message["input"]})
            session = SQLiteSession(
                session_id,
                db_path=str(backend.runtime_paths.custom_sessions_db_path()),
            )
            try:
                event_stream = Runner.run_streamed(
                    request_agent,
                    user_input,
                    context=context_obj,
                    session=session,
                    max_turns=15,
                )
                cancelled = False
                stream_iter = event_stream.stream_events()
                receive_task = asyncio.create_task(websocket.receive_json())
                event_task = asyncio.create_task(stream_iter.__anext__())
                try:
                    while True:
                        done, _pending = await asyncio.wait(
                            {receive_task, event_task},
                            return_when=asyncio.FIRST_COMPLETED,
                        )

                        if receive_task in done:
                            try:
                                control_message = receive_task.result()
                            except WebSocketDisconnect:
                                return
                            except json.JSONDecodeError:
                                receive_task = asyncio.create_task(websocket.receive_json())
                                continue

                            if _is_cancel_message(control_message, session_id):
                                cancelled = True
                                event_task.cancel()
                                with contextlib.suppress(asyncio.CancelledError):
                                    await event_task
                                await event_stream.aclose()

                                partial_message = None
                                stream_messages = getattr(event_stream, "messages", None) or []
                                if stream_messages:
                                    candidate = stream_messages[-1]
                                    if isinstance(candidate, dict) and candidate.get("role") == "assistant":
                                        partial_text = (candidate.get("content") or "").strip()
                                        if partial_text:
                                            partial_message = {
                                                "role": "assistant",
                                                "content": partial_text,
                                                "tool_calls": None,
                                            }
                                if partial_message is not None:
                                    history.append(partial_message)

                                history = normalize_history(history)
                                context_payload = _merge_context(
                                    _SESSION_CONTEXTS.get(session_id), asdict(context_obj)
                                )
                                metrics_payload = _usage_metrics_payload(
                                    getattr(event_stream, "context_wrapper", None),
                                    request_agent,
                                )
                                if metrics_payload is not None:
                                    context_payload["metrics"] = metrics_payload
                                _SESSION_CONTEXTS[session_id] = context_payload
                                _SESSION_HISTORIES[session_id] = history
                                save_session(session_id, context_payload, history)
                                try:
                                    await websocket.send_json(
                                        {
                                            "event": {
                                                "type": "cancelled",
                                                "message": "Generation stopped.",
                                            },
                                            "context": context_payload,
                                            "session_id": session_id,
                                        }
                                    )
                                    if metrics_payload is not None:
                                        await websocket.send_json(
                                            {
                                                "event": {
                                                    "type": "metrics",
                                                    "metrics": metrics_payload,
                                                },
                                                "session_id": session_id,
                                            }
                                        )
                                    await websocket.send_json(
                                        {
                                            "event": {
                                                "type": "sessions",
                                                "sessions": list_sessions(),
                                            },
                                            "session_id": session_id,
                                        }
                                    )
                                except WebSocketDisconnect:
                                    return
                                break

                            try:
                                await websocket.send_json(
                                    {
                                        "event": {
                                            "type": "error",
                                            "message": "A response is already running. Stop it before sending another message.",
                                        },
                                        "session_id": session_id,
                                    }
                                )
                            except WebSocketDisconnect:
                                return

                            receive_task = asyncio.create_task(websocket.receive_json())

                        if event_task in done:
                            try:
                                event = event_task.result()
                            except StopAsyncIteration:
                                break

                            event_out = process_event(event)
                            etype = (
                                (event or {}).get("type") if isinstance(event, dict) else None
                            )
                            data = (
                                (event or {}).get("data") if isinstance(event, dict) else None
                            )
                            if etype == "assistant_message" and isinstance(data, dict):
                                tool_calls = data.get("tool_calls")
                                content = (data.get("content") or "").strip()
                                if tool_calls:
                                    history.append(
                                        {
                                            "role": "assistant",
                                            "content": content or None,
                                            "tool_calls": tool_calls,
                                        }
                                    )
                                elif content:
                                    history.append(
                                        {
                                            "role": "assistant",
                                            "content": content,
                                            "tool_calls": None,
                                        }
                                    )
                            elif etype == "tool_result" and isinstance(data, dict):
                                history.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": data.get("id") or "",
                                        "content": data.get("output") or "",
                                    }
                                )

                            context_payload = _merge_context(
                                _SESSION_CONTEXTS.get(session_id), asdict(context_obj)
                            )
                            metrics_payload = _usage_metrics_payload(
                                getattr(event_stream, "context_wrapper", None),
                                request_agent,
                            )
                            if metrics_payload is not None:
                                context_payload["metrics"] = metrics_payload
                            _SESSION_CONTEXTS[session_id] = context_payload
                            _SESSION_HISTORIES[session_id] = history
                            save_session(session_id, context_payload, history)
                            if event_out is not None:
                                try:
                                    await websocket.send_json(
                                        {
                                            "event": event_out,
                                            "context": context_payload,
                                            "session_id": session_id,
                                        }
                                    )
                                    if metrics_payload is not None:
                                        await websocket.send_json(
                                            {
                                                "event": {
                                                    "type": "metrics",
                                                    "metrics": metrics_payload,
                                                },
                                                "session_id": session_id,
                                            }
                                        )
                                    await websocket.send_json(
                                        {
                                            "event": {
                                                "type": "sessions",
                                                "sessions": list_sessions(),
                                            },
                                            "session_id": session_id,
                                        }
                                    )
                                except WebSocketDisconnect:
                                    return
                            event_task = asyncio.create_task(stream_iter.__anext__())
                finally:
                    for task in (receive_task, event_task):
                        if task is not None and not task.done():
                            task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await task
                    if cancelled:
                        with contextlib.suppress(Exception):
                            await event_stream.aclose()
            except Exception as exc:
                error_message = _summarize_runtime_error(exc)
                context_payload = _merge_context(
                    _SESSION_CONTEXTS.get(session_id), asdict(context_obj)
                )
                _SESSION_CONTEXTS[session_id] = context_payload
                _SESSION_HISTORIES[session_id] = history
                save_session(session_id, context_payload, history)
                try:
                    await websocket.send_json(
                        {
                            "event": {"type": "error", "message": error_message},
                            "context": context_payload,
                            "session_id": session_id,
                        }
                    )
                    await websocket.send_json(
                        {
                            "event": {
                                "type": "sessions",
                                "sessions": list_sessions(),
                            },
                            "session_id": session_id,
                        }
                    )
                except WebSocketDisconnect:
                    return
                continue

            if cancelled:
                print("=== Run cancelled ===")
                continue

            history = normalize_history(history)
            context_payload = _merge_context(
                _SESSION_CONTEXTS.get(session_id), asdict(context_obj)
            )
            metrics_payload = _usage_metrics_payload(
                getattr(event_stream, "context_wrapper", None),
                request_agent,
            )
            if metrics_payload is not None:
                context_payload["metrics"] = metrics_payload
            _SESSION_CONTEXTS[session_id] = context_payload
            _SESSION_HISTORIES[session_id] = history
            save_session(session_id, context_payload, history)
            try:
                await websocket.send_json(
                    {
                        "event": {"type": "done"},
                        "context": context_payload,
                        "session_id": session_id,
                    }
                )
                if metrics_payload is not None:
                    await websocket.send_json(
                        {
                            "event": {
                                "type": "metrics",
                                "metrics": metrics_payload,
                            },
                            "session_id": session_id,
                        }
                    )
                await websocket.send_json(
                    {
                        "event": {
                            "type": "sessions",
                            "sessions": list_sessions(),
                        },
                        "session_id": session_id,
                    }
                )
            except WebSocketDisconnect:
                return
            print("=== Run complete ===")
    except WebSocketDisconnect:
        print("WebSocket disconnected; ending session loop")
