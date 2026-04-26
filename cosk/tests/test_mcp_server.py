from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from cosk.mcp.server import McpError, create_mcp_server


def _tool_fn(search_results: list[dict[str, object]] | None = None):
    store = Mock()
    store.search.return_value = [] if search_results is None else search_results
    mcp = create_mcp_server(store)
    tool = mcp._tool_manager.get_tool("cosk_semantic_search")  # noqa: SLF001
    return tool.fn, store


def test_server_module_docstring_contains_cli_usage_args_and_error_behavior() -> None:
    import cosk.mcp.server as server_module

    doc = server_module.__doc__ or ""
    assert "python -m cosk.mcp.server" in doc
    assert "--target-dir" in doc
    assert "--db-dir" in doc
    assert "Startup" in doc
    assert "Tool" in doc


@pytest.mark.parametrize("query", ["", "   "])
def test_cosk_semantic_search_rejects_blank_query_as_mcp_tool_error(query: str) -> None:
    tool_fn, _ = _tool_fn()
    with pytest.raises(McpError):
        tool_fn(query)


def test_cosk_semantic_search_serializes_results_as_json_text_array() -> None:
    results = [
        {
            "node_id": "1",
            "file_path": "a.py",
            "start_line": 1,
            "end_line": 2,
            "raw_signature": "def a()",
            "summary": "A",
        },
        {
            "node_id": "2",
            "file_path": "b.py",
            "start_line": 3,
            "end_line": 4,
            "raw_signature": "def b()",
            "summary": "B",
        },
    ]
    tool_fn, _ = _tool_fn(results)
    serialized = tool_fn("query")
    parsed = json.loads(serialized)
    assert isinstance(parsed, list)
    assert parsed == results


def test_cosk_semantic_search_limits_top_k_to_5() -> None:
    tool_fn, store = _tool_fn()
    tool_fn("find me")
    store.search.assert_called_once_with("find me", top_k=5)


def test_cosk_semantic_search_returns_empty_array_for_empty_index() -> None:
    tool_fn, _ = _tool_fn([])
    assert json.loads(tool_fn("query")) == []
