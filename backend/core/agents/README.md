# `backend.core.agents`

This is a small, repo-local agent runtime that supports:

- OpenAI tool calling (`function_tool`, `Agent.tools`)
- SQLite session persistence (`SQLiteSession`, default DB `sessions.db`)
- Streaming state/events while running (`Runner.run_streamed(...).stream_events()`)

## Minimal usage

```py
from backend.core.agents import Agent, Runner, SQLiteSession, function_tool
from backend.core.agents.model_openai import OpenAIChatModel
from openai import AsyncOpenAI

@function_tool
def add(a: int, b: int) -> int:
    "Add two integers."
    return a + b

client = AsyncOpenAI()
model = OpenAIChatModel(client, "gpt-4.1-mini")
agent = Agent(name="demo", instructions="Use tools when helpful.", model=model, tools=[add])

session = SQLiteSession("demo-session", db_path="custom_sessions.db")
result = Runner.run_sync(agent, "What is 2+3?", session=session)
print(result.final_output)
```

## Streaming events

```py
stream = Runner.run_streamed(agent, "What is 2+3?", session=session)
async for ev in stream.stream_events():
    if ev["type"] == "assistant_delta":
        print(ev["data"]["delta"], end="", flush=True)  # token-ish streaming
    else:
        print("\n", ev["type"], ev.get("data"))
```

Event `type` values include: `start`, `llm_request`, `assistant_delta`, `assistant_message`, `tool_call`, `tool_result`, `error`, `done`.
