from __future__ import annotations

import builtins

import pytest

from cosk.token_estimation import estimate_with_warnings


def test_empty_text_is_zero_tokens() -> None:
    count, warnings = estimate_with_warnings("")
    assert count in (0, None)
    assert isinstance(warnings, list)


def test_nonfatal_when_dependency_missing() -> None:
    count, warnings = estimate_with_warnings("hello world")
    assert count is None or count >= 0
    assert isinstance(warnings, list)


def test_missing_tiktoken_returns_none_without_user_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def _fail_import(name, *args, **kwargs):  # noqa: ANN001
        if name == "tiktoken":
            raise ImportError("no tiktoken")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fail_import)
    count, warnings = estimate_with_warnings("hello world")
    assert count is None
    assert warnings == []

