from __future__ import annotations

import json
from importlib.metadata import version
from pathlib import Path

import pytest

from cosk.cli import main as cli_main
from cosk.index_service import IndexSyncResult


def test_help_lists_new_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli_main(["--help"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    for command in ("index", "search", "neighbors", "expand", "find-usage", "watch", "serve", "registry"):
        assert command in out


def test_missing_required_args_returns_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli_main(["index"])
    assert exc_info.value.code != 0
    assert "usage" in capsys.readouterr().err.lower()


def test_search_invalid_top_k_prints_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    from importlib import import_module

    cli_module = import_module("cosk.cli.main")

    class _Context:
        class _Store:
            def search(self, query: str, top_k: int):  # noqa: ARG002
                return []

        vector_store = _Store()
        graph = None

    class _Manager:
        config = cli_module.get_cosk_config()

        def get_context(self, **kwargs):  # noqa: ANN003
            return _Context()

    monkeypatch.setattr(cli_module.server, "load_embedding_provider", lambda: object())
    monkeypatch.setattr(cli_module, "IndexManager", lambda **kwargs: _Manager())  # noqa: ARG005

    with pytest.raises(SystemExit) as exc:
        cli_main(["search", "hello", "--top-k", "0", "--db-dir", str(tmp_path / ".lancedb")])
    assert exc.value.code == 1
    assert "top_k" in capsys.readouterr().err


def test_registry_list_outputs_json(capsys: pytest.CaptureFixture[str]) -> None:
    cli_main(["registry", "list"])
    payload = json.loads(capsys.readouterr().out)
    assert "indexes" in payload


def test_index_success_prints_next_step_hint_for_standalone_index(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    cli_module = __import__("cosk.cli.main", fromlist=[""])
    target = tmp_path / "repo"
    target.mkdir()

    class _Manager:
        def sync(self, request, **_kwargs):  # noqa: ANN001
            return IndexSyncResult(
                mode="full",
                index_name="default",
                target_dir=request.target_dir.as_posix(),
                db_dir=(tmp_path / ".lancedb").as_posix(),
                added_files=1,
                updated_files=0,
                deleted_files=0,
                indexed_nodes=1,
                processed_files=1,
                skipped_files=0,
                elapsed_seconds=0.1,
            )

    monkeypatch.setattr(cli_module, "_make_manager", lambda *_args, **_kwargs: _Manager())
    monkeypatch.setattr(cli_module, "_is_interactive_terminal", lambda *_args, **_kwargs: True)

    cli_main(["index", "--target-dir", str(target)])
    assert "Next step: run `cosk serve` to start the MCP server." in capsys.readouterr().err


def test_version_flag_prints_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli_main(["--version"])
    assert exc_info.value.code == 0
    assert version("cosk") in capsys.readouterr().out


def test_help_shows_descriptions_for_all_subcommands_including_registry_children(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        cli_main(["--help"])
    root_help = capsys.readouterr().out
    command_help_pairs = {
        "index": "Build or update index",
        "search": "Search indexed skeleton nodes",
        "neighbors": "Get graph neighbors for a node",
        "expand": "Expand source lines",
        "find-usage": "Find symbol usage",
        "watch": "Watch filesystem and reindex incrementally",
        "serve": "Serve MCP or HTTP transport",
        "inspect": "Print local index and graph diagnostics",
        "registry": "Manage named index registry",
    }
    for command, help_text in command_help_pairs.items():
        assert command in root_help
        assert help_text in root_help

    with pytest.raises(SystemExit):
        cli_main(["registry", "--help"])
    registry_help = capsys.readouterr().out
    registry_pairs = {
        "list": "List named indexes in registry",
        "remove": "Remove an index from registry",
        "set-default": "Set registry default index",
    }
    for command, help_text in registry_pairs.items():
        assert command in registry_help
        assert help_text in registry_help


def test_root_help_contains_quick_start_examples(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli_main(["--help"])
    help_text = capsys.readouterr().out
    assert "Quick Start" in help_text
    assert "cosk index --target-dir" in help_text

