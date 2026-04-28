from __future__ import annotations

import pytest

from cosk.repo_registry import RegistryError, get_registry_path, load_registry, resolve_index, set_default_index, upsert_index


def test_registry_save_and_resolve(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    upsert_index("default", tmp_path, tmp_path / ".lancedb")
    name, entry = resolve_index()
    assert name == "default"
    assert entry.db_dir.endswith(".lancedb")


def test_registry_set_default_unknown_raises(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RegistryError):
        set_default_index("missing")


def test_registry_corrupt_fails_closed(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    reg = tmp_path / ".cosk" / "registry.yaml"
    reg.parent.mkdir()
    reg.write_text(": bad", encoding="utf-8")
    with pytest.raises(RegistryError):
        load_registry()


def test_registry_path_prefers_env_override_over_cwd_default(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    override = tmp_path / "custom" / "registry.yaml"
    monkeypatch.setenv("COSK_REGISTRY_PATH", str(override))
    resolved = get_registry_path(tmp_path)
    assert resolved == override

