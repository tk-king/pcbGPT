from __future__ import annotations

import json
from typing import Any


def web_search_tool(query: str, max_results: int = 5, region: str = "us-en") -> str:
    """Search the public web and return top results (title, url, snippet) as JSON."""
    try:
        max_results = int(max_results)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_results must be a whole number.") from exc
    if max_results < 1:
        raise ValueError("max_results must be at least 1.")

    try:
        from ddgs import DDGS
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("ddgs is required for web_search_tool") from exc

    results: list[dict[str, Any]] = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results, region=region, backend="duckduckgo"):
            results.append(
                {
                    "title": r.get("title"),
                    "url": r.get("href"),
                    "snippet": r.get("body"),
                }
            )
    return json.dumps(results, indent=2)
