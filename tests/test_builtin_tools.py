import json
import sys
from types import SimpleNamespace

import pytest

from backend.core.agents.builtin_tools import web_search_tool


def test_web_search_coerces_string_max_results(monkeypatch):
    calls = []

    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def text(self, query, **kwargs):
            calls.append((query, kwargs))
            return [{"title": "Result", "href": "https://example.com", "body": "Snippet"}]

    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=FakeDDGS))

    result = json.loads(web_search_tool("voltage regulator", max_results="5"))

    assert calls == [
        (
            "voltage regulator",
            {"max_results": 5, "region": "us-en", "backend": "duckduckgo"},
        )
    ]
    assert result == [{"title": "Result", "url": "https://example.com", "snippet": "Snippet"}]


@pytest.mark.parametrize("value", ["invalid", 0, -1])
def test_web_search_rejects_invalid_max_results(value):
    with pytest.raises(ValueError, match="max_results"):
        web_search_tool("voltage regulator", max_results=value)
