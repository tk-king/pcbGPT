from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import Any, Callable, get_args, get_origin, Annotated


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _json_type_for(annotation: Any) -> dict[str, Any]:
    if annotation is inspect._empty:
        return {"type": "string"}

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is Annotated and args:
        return _json_type_for(args[0])

    if origin is list and args:
        return {"type": "array", "items": _json_type_for(args[0])}

    if origin is dict:
        return {"type": "object"}

    if origin is tuple:
        return {"type": "array"}

    if origin is None:
        if annotation in (str,):
            return {"type": "string"}
        if annotation in (int,):
            return {"type": "integer"}
        if annotation in (float,):
            return {"type": "number"}
        if annotation in (bool,):
            return {"type": "boolean"}

    # Optional[T] / Union[T, None]
    if origin is type(None):
        return {"type": "null"}
    if origin is None and annotation is None:
        return {"type": "null"}
    if origin is None and getattr(annotation, "__name__", None) == "NoneType":
        return {"type": "null"}
    if origin is None:
        return {"type": "string"}
    if origin is Any:
        return {}

    if origin is not None and str(origin).endswith("typing.Union"):
        # best-effort: pick first non-null
        non_null = [a for a in args if a is not type(None)]  # noqa: E721
        if non_null:
            schema = _json_type_for(non_null[0])
            schema["nullable"] = True
            return schema
        return {"type": "string"}

    return {"type": "string"}


def _description_from_annotated(annotation: Any) -> str | None:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Annotated and len(args) >= 2:
        for meta in args[1:]:
            if isinstance(meta, str):
                return meta
    return None


def _infer_parameters_schema(func: Callable[..., Any]) -> dict[str, Any]:
    sig = inspect.signature(func)
    props: dict[str, Any] = {}
    required: list[str] = []

    parameters = list(sig.parameters.values())

    # Convention: tools may accept a first `wrapper` argument (RunContextWrapper).
    if parameters and parameters[0].name in {"wrapper", "context_wrapper"}:
        parameters = parameters[1:]

    for p in parameters:
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        ann = p.annotation
        schema = _json_type_for(ann)
        desc = _description_from_annotated(ann)
        if desc:
            schema = {**schema, "description": desc}
        props[p.name] = schema
        if p.default is inspect._empty:
            required.append(p.name)

    return {"type": "object", "properties": props, "required": required}


def _tool_name(func: Callable[..., Any]) -> str:
    return getattr(func, "__name__", "tool")


def function_tool(func: Callable[..., Any] | None = None, *, name: str | None = None, description: str | None = None):
    """Wrap a python function as a tool (OpenAI function-calling schema).

    Usable as a decorator (`@function_tool`) or as a wrapper (`function_tool(fn)`).
    """

    def _wrap(f: Callable[..., Any]) -> Tool:
        tool_desc = (description or (inspect.getdoc(f) or "")).strip()
        tool_desc = tool_desc.splitlines()[0] if tool_desc else f"Tool: {_tool_name(f)}"
        return Tool(
            name=(name or _tool_name(f)),
            description=tool_desc,
            parameters=_infer_parameters_schema(f),
            func=f,
        )

    if func is None:
        return _wrap
    return _wrap(func)


def parse_tool_arguments(arguments: str | dict[str, Any] | None) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return arguments
    try:
        parsed = json.loads(arguments)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}

