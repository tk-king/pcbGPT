from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import traceback
from dataclasses import dataclass
from typing import Any, AsyncIterator
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

from backend.utils.tool_progress import (
    reset_tool_progress_sink,
    set_tool_progress_sink,
)

from .agent import Agent, RunContextWrapper
from .errors import AgentsException, RunErrorDetails
from .session_sqlite import SQLiteSession
from .tools import Tool, parse_tool_arguments
from .types import AgentEvent


_CIRCUIT_WRITE_TOOL_NAME = "write_circuit_code"
_CIRCUIT_WRITE_SUCCESS_PREFIX = "circuit code executed successfully."
_CIRCUIT_WRITE_RETRY_REMINDER = {
    "role": "system",
    "content": (
        "The previous write_circuit_code call did not succeed. Continue using the "
        "available tools to verify and correct the candidate, then call "
        "write_circuit_code again. Do not stop with prose or ask for confirmation "
        "unless a genuinely missing user requirement makes a safe correction impossible."
    ),
}


def _circuit_write_succeeded(output: Any) -> bool:
    return isinstance(output, str) and output.strip().lower().startswith(
        _CIRCUIT_WRITE_SUCCESS_PREFIX
    )


def _tool_choice_for_turn(
    agent: Agent,
    *,
    turn: int,
    circuit_write_retry_required: bool,
) -> str | dict[str, Any] | None:
    if circuit_write_retry_required:
        return "required"
    if turn == 0:
        return agent.tool_choice_on_first_turn
    return None


@dataclass
class RunResult:
    final_output: Any | None
    messages: list[dict[str, Any]]
    context_wrapper: RunContextWrapper[Any]

    @property
    def context(self) -> Any:
        return self.context_wrapper.context


class RunStream:
    def __init__(
        self,
        agen: AsyncIterator[AgentEvent],
        context_wrapper: RunContextWrapper[Any],
        messages: list[dict[str, Any]],
    ):
        self._agen = agen
        self.context_wrapper = context_wrapper
        self.messages = messages

    @property
    def context(self) -> Any:
        return self.context_wrapper.context

    async def stream_events(self) -> AsyncIterator[AgentEvent]:
        async for ev in self._agen:
            yield ev

    async def aclose(self) -> None:
        aclose = getattr(self._agen, "aclose", None)
        if callable(aclose):
            await aclose()


def _pydantic_parse(output_type: type[BaseModel], text: str) -> BaseModel:
    # Expect JSON. Try raw first, then attempt to extract a JSON object.
    try:
        return output_type.model_validate_json(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return output_type.model_validate_json(text[start : end + 1])
        raise


class Runner:
    @staticmethod

    @staticmethod
    async def _complete_with_fallback(agent: Agent, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None, response_format: dict[str, Any] | None, tool_choice: str | dict[str, Any] | None = None):
        kwargs = {"messages": messages, "tools": tools, "response_format": response_format}
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        try:
            return await agent.model.complete(**kwargs)
        except Exception:
            if response_format is None:
                raise
            # Some backends/models don't support json mode; retry without it.
            kwargs["response_format"] = None
            return await agent.model.complete(**kwargs)

    @staticmethod
    async def _stream_with_fallback(
        agent: Agent,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        response_format: dict[str, Any] | None,
        tool_choice: str | dict[str, Any] | None = None,
    ):
        kwargs = {"messages": messages, "tools": tools, "response_format": response_format}
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        try:
            return await agent.model.stream(**kwargs)
        except Exception:
            if response_format is None:
                raise
            kwargs["response_format"] = None
            return await agent.model.stream(**kwargs)

    @staticmethod
    async def run(
        agent: Agent,
        input: str | list[dict[str, Any]],
        *,
        context: Any | None = None,
        session: SQLiteSession | None = None,
        max_turns: int = 15,
    ) -> RunResult:
        context_obj = context if context is not None else object()
        wrapper = RunContextWrapper(context=context_obj, session=session)
        loaded_messages: list[dict[str, Any]] = []
        if session is not None:
            try:
                loaded_messages = session.load_messages()
            except Exception:
                loaded_messages = []
        messages: list[dict[str, Any]] = list(loaded_messages)

        system_msg = {"role": "system", "content": agent.instructions}
        response_format = {"type": "json_object"} if agent.output_type is not None else None
        if not messages or messages[0].get("role") != "system":
            messages = [system_msg] + [m for m in messages if m.get("role") != "system"]
            if session is not None:
                session.append_message(system_msg)

        if isinstance(input, str):
            user_msg = {"role": "user", "content": input}
            messages.append(user_msg)
            if session is not None:
                session.append_message(user_msg)
        else:
            messages.extend(input)
            if session is not None:
                for m in input:
                    session.append_message(m)

        tools: list[Tool] = list(agent.tools or [])
        tool_by_name = {t.name: t for t in tools}
        openai_tools = [t.to_openai_tool() for t in tools] if tools else None

        new_items: list[dict[str, Any]] = []
        circuit_write_retry_required = False
        try:
            for turn in range(max_turns):
                resp = await Runner._complete_with_fallback(
                    agent,
                    messages=messages,
                    tools=openai_tools,
                    response_format=response_format,
                    tool_choice=_tool_choice_for_turn(
                        agent,
                        turn=turn,
                        circuit_write_retry_required=circuit_write_retry_required,
                    ),
                )
                wrapper.usage.add_openai_usage(getattr(resp, "usage", None))
                msg = resp.choices[0].message
                content = getattr(msg, "content", None)
                tool_calls = getattr(msg, "tool_calls", None)

                assistant_message: dict[str, Any] = {"role": "assistant", "content": content}
                if tool_calls:
                    assistant_message["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in tool_calls
                    ]
                messages.append(assistant_message)
                new_items.append(assistant_message)
                if session is not None:
                    session.append_message(assistant_message)

                if not tool_calls:
                    if circuit_write_retry_required:
                        retry_message = dict(_CIRCUIT_WRITE_RETRY_REMINDER)
                        messages.append(retry_message)
                        new_items.append(retry_message)
                        if session is not None:
                            session.append_message(retry_message)
                        continue
                    final_output: Any = content or ""
                    if agent.output_type is not None:
                        final_output = _pydantic_parse(agent.output_type, content or "")
                    return RunResult(final_output=final_output, messages=messages, context_wrapper=wrapper)

                # execute tool calls in order
                for tc in tool_calls:
                    name = tc.function.name
                    args = parse_tool_arguments(tc.function.arguments)
                    tool = tool_by_name.get(name)
                    if tool is None:
                        output = f"Tool not found: {name}"
                    else:
                        output = await _maybe_await_tool(tool, wrapper, args)
                    if name == _CIRCUIT_WRITE_TOOL_NAME:
                        circuit_write_retry_required = not _circuit_write_succeeded(output)
                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": output if isinstance(output, str) else json.dumps(output),
                    }
                    messages.append(tool_msg)
                    new_items.append(tool_msg)
                    if session is not None:
                        session.append_message(tool_msg)

            raise AgentsException(
                f"Exceeded max_turns={max_turns}",
                run_data=RunErrorDetails(input=input, new_items=new_items, context_wrapper=wrapper),
            )
        except AgentsException:
            raise
        except Exception as exc:
            raise AgentsException(
                f"Agent run failed: {type(exc).__name__}: {exc}",
                run_data=RunErrorDetails(input=input, new_items=new_items, context_wrapper=wrapper),
            ) from exc

    @staticmethod
    def run_sync(
        agent: Agent,
        input: str | list[dict[str, Any]],
        *,
        context: Any | None = None,
        session: SQLiteSession | None = None,
        max_turns: int = 15,
    ) -> RunResult:
        try:
            asyncio.get_running_loop()
            in_event_loop = True
        except RuntimeError:
            in_event_loop = False

        if not in_event_loop:
            return asyncio.run(Runner.run(agent, input, context=context, session=session, max_turns=max_turns))

        def _run() -> RunResult:
            return asyncio.run(Runner.run(agent, input, context=context, session=session, max_turns=max_turns))

        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(_run).result()

    @staticmethod
    def run_streamed(
        agent: Agent,
        input: str,
        *,
        context: Any | None = None,
        session: SQLiteSession | None = None,
        max_turns: int = 15,
    ) -> RunStream:
        print("Runing agent with model ", agent.name)
        context_obj = context if context is not None else object()
        wrapper = RunContextWrapper(context=context_obj, session=session)
        messages: list[dict[str, Any]] = []
        if session is not None:
            try:
                messages = session.load_messages()
            except Exception:
                messages = []

        system_msg = {"role": "system", "content": agent.instructions}
        if not messages or messages[0].get("role") != "system":
            messages[:] = [system_msg] + [m for m in messages if m.get("role") != "system"]
            if session is not None:
                session.append_message(system_msg)

        user_msg = {"role": "user", "content": input}
        messages.append(user_msg)
        if session is not None:
            session.append_message(user_msg)

        agen = Runner._run_stream(agent, wrapper=wrapper, session=session, max_turns=max_turns, messages=messages)
        return RunStream(agen, wrapper, messages)

    @staticmethod
    async def _run_stream(
        agent: Agent,
        *,
        wrapper: RunContextWrapper[Any],
        session: SQLiteSession | None,
        max_turns: int,
        messages: list[dict[str, Any]],
    ) -> AsyncIterator[AgentEvent]:
        response_format = {"type": "json_object"} if agent.output_type is not None else None

        tools: list[Tool] = list(agent.tools or [])
        tool_by_name = {t.name: t for t in tools}
        openai_tools = [t.to_openai_tool() for t in tools] if tools else None

        yield {"type": "start", "data": {"agent": agent.name}}
        circuit_write_retry_required = False
        for turn in range(max_turns):
            yield {"type": "llm_request", "turn": turn, "data": {"messages": messages[-8:], "tools": [t.name for t in tools]}}
            try:
                resp_stream = await Runner._stream_with_fallback(
                    agent,
                    messages=messages,
                    tools=openai_tools,
                    response_format=response_format,
                    tool_choice=_tool_choice_for_turn(
                        agent,
                        turn=turn,
                        circuit_write_retry_required=circuit_write_retry_required,
                    ),
                )
            except Exception as exc:
                if session is not None:
                    session.append_event("error", {"turn": turn, "error": str(exc)})
                yield {"type": "error", "turn": turn, "data": {"where": "llm", "error": str(exc)}}
                raise

            # Build the assistant message incrementally so callers can inspect `stream.messages`.
            assistant_message: dict[str, Any] = {"role": "assistant", "content": ""}
            messages.append(assistant_message)

            content_parts: list[str] = []
            # tool_calls are streamed as deltas; accumulate by index.
            tool_calls_acc: dict[int, dict[str, Any]] = {}

            async for chunk in resp_stream:
                wrapper.usage.add_openai_usage(getattr(chunk, "usage", None))
                choice = (getattr(chunk, "choices", None) or [None])[0]
                if choice is None:
                    continue
                delta = getattr(choice, "delta", None)
                if delta is None:
                    continue

                delta_content = getattr(delta, "content", None)
                if delta_content:
                    content_parts.append(delta_content)
                    assistant_message["content"] = "".join(content_parts)
                    yield {"type": "assistant_delta", "turn": turn, "data": {"delta": delta_content}}

                delta_tool_calls = getattr(delta, "tool_calls", None)
                if delta_tool_calls:
                    for tc in delta_tool_calls:
                        idx = getattr(tc, "index", 0) or 0
                        entry = tool_calls_acc.setdefault(
                            idx,
                            {"id": None, "type": "function", "function": {"name": None, "arguments": ""}},
                        )
                        tc_id = getattr(tc, "id", None)
                        if tc_id:
                            entry["id"] = tc_id
                        tc_type = getattr(tc, "type", None)
                        if tc_type:
                            entry["type"] = tc_type
                        fn = getattr(tc, "function", None)
                        if fn is not None:
                            fn_name = getattr(fn, "name", None)
                            fn_args = getattr(fn, "arguments", None)
                            if fn_name:
                                entry["function"]["name"] = fn_name
                            if fn_args:
                                entry["function"]["arguments"] = (entry["function"].get("arguments") or "") + fn_args
            content = "".join(content_parts)
            assistant_message["content"] = content
            if tool_calls_acc:
                # Normalize tool call entries (required keys for downstream consumers).
                normalized_calls: list[dict[str, Any]] = []
                for _, tc in sorted(tool_calls_acc.items()):
                    fn = tc.get("function") or {}
                    tool_call_id = str(tc.get("id") or "").strip()
                    name = str(fn.get("name") or "").strip()
                    if not tool_call_id or not name:
                        continue
                    normalized_calls.append(
                        {
                            "id": tool_call_id,
                            "type": tc.get("type") or "function",
                            "function": {
                                "name": name,
                                "arguments": fn.get("arguments") or "",
                            },
                        }
                    )
                if normalized_calls:
                    assistant_message["tool_calls"] = normalized_calls

            if session is not None:
                session.append_message(assistant_message)
                session.append_event(
                    "assistant_message",
                    {"turn": turn, "content": content, "tool_calls": bool(assistant_message.get("tool_calls"))},
                )

            yield {
                "type": "assistant_message",
                "turn": turn,
                "data": {"content": content, "tool_calls": assistant_message.get("tool_calls")},
            }

            tool_calls = assistant_message.get("tool_calls")
            if not tool_calls:
                if circuit_write_retry_required:
                    retry_message = dict(_CIRCUIT_WRITE_RETRY_REMINDER)
                    messages.append(retry_message)
                    if session is not None:
                        session.append_message(retry_message)
                        session.append_event(
                            "circuit_write_retry",
                            {"turn": turn, "reason": "assistant_stopped_after_failed_write"},
                        )
                    continue
                yield {"type": "done", "turn": turn, "data": {"final": content}}
                return

            for tc in tool_calls:
                name = (tc.get("function") or {}).get("name") or ""
                args = parse_tool_arguments((tc.get("function") or {}).get("arguments"))
                tool_call_id = tc.get("id") or ""
                yield {"type": "tool_call", "turn": turn, "data": {"id": tool_call_id, "name": name, "args": args}}
                if session is not None:
                    session.append_event("tool_call", {"turn": turn, "id": tool_call_id, "name": name, "args": args})

                tool = tool_by_name.get(name)
                if tool is None:
                    output = f"Tool not found: {name}"
                else:
                    try:
                        tool_out: dict[str, Any] = {}
                        async for progress_event in _execute_tool_with_progress(
                            tool,
                            wrapper,
                            args,
                            name=name,
                            turn=turn,
                            tool_call_id=tool_call_id,
                            out=tool_out,
                        ):
                            yield progress_event
                        output = tool_out.get("output")
                    except Exception:
                        output = "Tool execution failed:\n" + traceback.format_exc()
                if name == _CIRCUIT_WRITE_TOOL_NAME:
                    circuit_write_retry_required = not _circuit_write_succeeded(output)
                output_text = output if isinstance(output, str) else json.dumps(output)
                tool_msg = {"role": "tool", "tool_call_id": tool_call_id, "content": output_text}
                messages.append(tool_msg)
                if session is not None:
                    session.append_message(tool_msg)
                    session.append_event("tool_result", {"turn": turn, "id": tool_call_id, "name": name, "output": output_text})

                yield {"type": "tool_result", "turn": turn, "data": {"id": tool_call_id, "name": name, "output": output_text}}

        yield {"type": "error", "turn": max_turns, "data": {"where": "runner", "error": f"Exceeded max_turns={max_turns}"}}


async def _execute_tool_with_progress(
    tool: Tool,
    wrapper: RunContextWrapper[Any],
    args: dict[str, Any],
    *,
    name: str,
    turn: int,
    tool_call_id: str,
    out: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """Execute a tool while streaming its progress updates as events.

    Sync tools run in a worker thread (so the event loop stays responsive)
    with a progress sink wired to an asyncio queue; any progress messages the
    tool reports (e.g. datasheet processing steps) are yielded as
    ``tool_progress`` events while the tool is still running.
    """
    fn = tool.func
    try:
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
    except (TypeError, ValueError):
        params = []
    takes_wrapper = bool(params) and params[0].name in {"wrapper", "context_wrapper"}

    def _invoke() -> Any:
        if takes_wrapper:
            return fn(wrapper, **args)
        return fn(**args)

    if inspect.iscoroutinefunction(fn):
        out["output"] = await _invoke()
        return

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str] = asyncio.Queue()

    def _sink(message: str) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, str(message))

    token = set_tool_progress_sink(_sink)
    exec_task = asyncio.create_task(asyncio.to_thread(_invoke))
    get_task = asyncio.create_task(queue.get())
    try:
        while True:
            done, _pending = await asyncio.wait(
                {exec_task, get_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if get_task in done:
                message = get_task.result()
                yield {
                    "type": "tool_progress",
                    "turn": turn,
                    "data": {"id": tool_call_id, "name": name, "message": message},
                }
                get_task = asyncio.create_task(queue.get())
                continue
            break
    finally:
        reset_tool_progress_sink(token)
        get_task.cancel()

    out["output"] = await exec_task


async def _maybe_await_tool(tool: Tool, wrapper: RunContextWrapper[Any], args: dict[str, Any]) -> Any:
    fn = tool.func
    import inspect

    try:
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
    except (TypeError, ValueError):
        params = []

    if params and params[0].name in {"wrapper", "context_wrapper"}:
        res = fn(wrapper, **args)
    else:
        res = fn(**args)
    if asyncio.iscoroutine(res):
        return await res
    return res
