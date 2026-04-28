from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cosk.extraction.models import SkeletonNode
from cosk.indexing.embedding import GeminiEmbeddingProvider, build_node_embedding_text


def test_build_node_embedding_text_concatenates_signature_and_docstring_exactly() -> None:
    node = SkeletonNode("a.py", 1, 2, "sig", "doc")
    assert build_node_embedding_text(node) == "sig\ndoc"


def test_build_node_embedding_text_keeps_newline_when_docstring_empty() -> None:
    node = SkeletonNode("a.py", 1, 2, "sig", "")
    assert build_node_embedding_text(node) == "sig\n"


def test_gemini_resolve_key_prefers_env_api_key_over_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / ".geminikey"
    key_file.write_text("file-key", encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    monkeypatch.delenv("GEMINI_KEY_PATH", raising=False)
    assert GeminiEmbeddingProvider._resolve_key(str(key_file)) == "env-key"


def test_gemini_resolve_key_uses_gemini_key_path_when_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / "custom-key"
    key_file.write_text("path-key", encoding="utf-8")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_KEY_PATH", str(key_file))
    assert GeminiEmbeddingProvider._resolve_key("unused") == "path-key"


def test_gemini_resolve_key_uses_passed_key_file_when_env_not_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / "passed-key"
    key_file.write_text("file-key", encoding="utf-8")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_KEY_PATH", raising=False)
    assert GeminiEmbeddingProvider._resolve_key(str(key_file)) == "file-key"


def test_gemini_resolve_key_raises_when_no_env_and_file_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_KEY_PATH", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY not set and key file not found"):
        GeminiEmbeddingProvider._resolve_key(str(tmp_path / "missing"))


def _install_fake_google_genai(monkeypatch: pytest.MonkeyPatch, *, client: object) -> None:
    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.genai")
    genai_module.Client = MagicMock(return_value=client)
    google_module.genai = genai_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)


def test_gemini_embed_calls_google_genai_client_with_api_key_and_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / ".geminikey"
    key_file.write_text("file-key", encoding="utf-8")
    embedding = types.SimpleNamespace(values=[1.0, 2.0])
    response = types.SimpleNamespace(embeddings=[embedding])
    client = types.SimpleNamespace(models=types.SimpleNamespace(embed_content=MagicMock(return_value=response)))
    _install_fake_google_genai(monkeypatch, client=client)
    provider = GeminiEmbeddingProvider(key_file=str(key_file), model_name="model-x")

    vector = provider.embed("hello")

    assert vector == [1.0, 2.0]
    google_module = sys.modules["google"]
    google_module.genai.Client.assert_called_once_with(api_key="file-key")
    client.models.embed_content.assert_called_once_with(model="model-x", contents="hello")


def test_gemini_embed_returns_float_list(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / ".geminikey"
    key_file.write_text("file-key", encoding="utf-8")
    embedding = types.SimpleNamespace(values=[1, "2", 3.5])
    response = types.SimpleNamespace(embeddings=[embedding])
    client = types.SimpleNamespace(models=types.SimpleNamespace(embed_content=MagicMock(return_value=response)))
    _install_fake_google_genai(monkeypatch, client=client)
    provider = GeminiEmbeddingProvider(key_file=str(key_file))
    assert provider.embed("hello") == [1.0, 2.0, 3.5]


def test_gemini_embed_raises_on_empty_embedding_response(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / ".geminikey"
    key_file.write_text("file-key", encoding="utf-8")
    response = types.SimpleNamespace(embeddings=[])
    client = types.SimpleNamespace(models=types.SimpleNamespace(embed_content=MagicMock(return_value=response)))
    _install_fake_google_genai(monkeypatch, client=client)
    provider = GeminiEmbeddingProvider(key_file=str(key_file))
    with pytest.raises(ValueError, match="empty vector"):
        provider.embed("hello")


def test_gemini_embed_rejects_none_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / ".geminikey"
    key_file.write_text("file-key", encoding="utf-8")
    client = types.SimpleNamespace(models=types.SimpleNamespace(embed_content=MagicMock()))
    _install_fake_google_genai(monkeypatch, client=client)
    provider = GeminiEmbeddingProvider(key_file=str(key_file))
    with pytest.raises(ValueError, match="must not be None"):
        provider.embed(None)  # type: ignore[arg-type]


def test_gemini_provider_retries_and_succeeds_before_max_attempts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / ".geminikey"
    key_file.write_text("file-key", encoding="utf-8")
    embedding = types.SimpleNamespace(values=[1.0])
    response = types.SimpleNamespace(embeddings=[embedding])
    embed_content = MagicMock(side_effect=[RuntimeError("x"), RuntimeError("y"), response])
    client = types.SimpleNamespace(models=types.SimpleNamespace(embed_content=embed_content))
    _install_fake_google_genai(monkeypatch, client=client)
    monkeypatch.setattr("cosk.indexing.embedding.time.sleep", lambda _: None)
    provider = GeminiEmbeddingProvider(key_file=str(key_file), retry_max_attempts=3, retry_base_delay=0.0, retry_max_delay=0.0)
    assert provider.embed("hello") == [1.0]
    assert embed_content.call_count == 3


def test_gemini_provider_raises_after_retry_exhausted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / ".geminikey"
    key_file.write_text("file-key", encoding="utf-8")
    embed_content = MagicMock(side_effect=RuntimeError("fail"))
    client = types.SimpleNamespace(models=types.SimpleNamespace(embed_content=embed_content))
    _install_fake_google_genai(monkeypatch, client=client)
    monkeypatch.setattr("cosk.indexing.embedding.time.sleep", lambda _: None)
    provider = GeminiEmbeddingProvider(key_file=str(key_file), retry_max_attempts=2, retry_base_delay=0.0, retry_max_delay=0.0)
    with pytest.raises(RuntimeError, match="fail"):
        provider.embed("hello")
    assert embed_content.call_count == 2


@pytest.mark.integration
def test_gemini_embedding_provider_real_api_if_key_present() -> None:
    if "GEMINI_API_KEY" not in os.environ:  # type: ignore[name-defined]
        pytest.skip("GEMINI_API_KEY not set")
    provider = GeminiEmbeddingProvider()
    vector = provider.embed("hello")
    assert vector
    assert all(isinstance(value, float) for value in vector)


def test_gemini_embed_reuses_client_across_calls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / ".geminikey"
    key_file.write_text("file-key", encoding="utf-8")
    embedding = types.SimpleNamespace(values=[1.0])
    response = types.SimpleNamespace(embeddings=[embedding])
    client = types.SimpleNamespace(models=types.SimpleNamespace(embed_content=MagicMock(return_value=response)))
    _install_fake_google_genai(monkeypatch, client=client)
    provider = GeminiEmbeddingProvider(key_file=str(key_file))
    provider.embed("a")
    provider.embed("b")
    google_module = sys.modules["google"]
    google_module.genai.Client.assert_called_once_with(api_key="file-key")


def test_gemini_embed_batch_returns_vector_per_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / ".geminikey"
    key_file.write_text("file-key", encoding="utf-8")
    emb1 = types.SimpleNamespace(values=[1.0, 2.0])
    emb2 = types.SimpleNamespace(values=[3.0, 4.0])
    response = types.SimpleNamespace(embeddings=[emb1, emb2])
    client = types.SimpleNamespace(models=types.SimpleNamespace(embed_content=MagicMock(return_value=response)))
    _install_fake_google_genai(monkeypatch, client=client)
    provider = GeminiEmbeddingProvider(key_file=str(key_file), model_name="model-x")

    result = provider.embed_batch(["hello", "world"])

    assert result == [[1.0, 2.0], [3.0, 4.0]]
    client.models.embed_content.assert_called_once_with(model="model-x", contents=["hello", "world"])


def test_gemini_embed_batch_empty_input_returns_empty_list(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / ".geminikey"
    key_file.write_text("file-key", encoding="utf-8")
    client = types.SimpleNamespace(models=types.SimpleNamespace(embed_content=MagicMock()))
    _install_fake_google_genai(monkeypatch, client=client)
    provider = GeminiEmbeddingProvider(key_file=str(key_file))

    assert provider.embed_batch([]) == []
    client.models.embed_content.assert_not_called()


def test_gemini_embed_batch_raises_when_too_many_texts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / ".geminikey"
    key_file.write_text("file-key", encoding="utf-8")
    client = types.SimpleNamespace(models=types.SimpleNamespace(embed_content=MagicMock()))
    _install_fake_google_genai(monkeypatch, client=client)
    provider = GeminiEmbeddingProvider(key_file=str(key_file))

    with pytest.raises(ValueError, match="max 100 texts"):
        provider.embed_batch(["x"] * 101)


def test_gemini_embed_batch_raises_on_response_count_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key_file = tmp_path / ".geminikey"
    key_file.write_text("file-key", encoding="utf-8")
    response = types.SimpleNamespace(embeddings=[types.SimpleNamespace(values=[1.0])])
    client = types.SimpleNamespace(models=types.SimpleNamespace(embed_content=MagicMock(return_value=response)))
    _install_fake_google_genai(monkeypatch, client=client)
    provider = GeminiEmbeddingProvider(key_file=str(key_file))

    with pytest.raises(ValueError, match="1 vectors for 3 inputs"):
        provider.embed_batch(["a", "b", "c"])

