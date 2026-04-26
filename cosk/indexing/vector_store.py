from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

import lancedb
import pyarrow as pa

from cosk.extraction.models import SkeletonNode
from cosk.indexing.embedding import EmbeddingProvider, GeminiEmbeddingProvider, build_node_embedding_text


class SkeletonNodeSearchResult(TypedDict):
    node_id: str
    file_path: str
    start_line: int
    end_line: int
    raw_signature: str
    summary: str


class SkeletonNodeVectorStore:
    def __init__(
        self,
        *,
        db_dir: Path | str | None = None,
        table_name: str = "skeleton_nodes",
        embedding_provider: EmbeddingProvider | None = None,
        model_name: str = "gemini-embedding-001",
        key_file: str = ".geminikey",
    ) -> None:
        self._db_dir = Path(db_dir) if db_dir is not None else Path(__file__).resolve().parent.parent / ".lancedb"
        self._table_name = table_name
        self._embedding_provider = embedding_provider or GeminiEmbeddingProvider(model_name=model_name, key_file=key_file)
        self._vector_dim: int | None = None

    @staticmethod
    def compute_node_id(node: SkeletonNode) -> str:
        digest = hashlib.sha256(f"{node.file_path}:{node.start_line}".encode("utf-8"))
        return digest.hexdigest()

    @staticmethod
    def _schema(vector_dim: int) -> pa.Schema:
        return pa.schema(
            [
                pa.field("node_id", pa.string()),
                pa.field("file_path", pa.string()),
                pa.field("start_line", pa.int64()),
                pa.field("end_line", pa.int64()),
                pa.field("raw_signature", pa.string()),
                pa.field("summary", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), vector_dim)),
            ]
        )

    def _connect(self):
        self._db_dir.mkdir(parents=True, exist_ok=True)
        return lancedb.connect(str(self._db_dir))

    def _open_table_if_exists(self, db):
        try:
            return db.open_table(self._table_name)
        except Exception:  # noqa: BLE001
            return None

    def _ensure_vector_dim_from_table(self, table) -> None:
        if self._vector_dim is not None:
            return
        try:
            vector_field = table.schema.field("vector")
            list_size = getattr(vector_field.type, "list_size", None)
            if isinstance(list_size, int) and list_size > 0:
                self._vector_dim = list_size
        except Exception:  # noqa: BLE001
            return

    def upsert_nodes(self, nodes: Sequence[SkeletonNode]) -> int:
        if not nodes:
            return 0

        rows: list[dict[str, object]] = []
        first_vector_dim: int | None = None
        for node in nodes:
            vector = self._embedding_provider.embed(build_node_embedding_text(node))
            if first_vector_dim is None:
                first_vector_dim = len(vector)
                if first_vector_dim == 0:
                    raise ValueError("embedding vector must not be empty")
            if len(vector) != first_vector_dim:
                raise ValueError("embedding vector dimension mismatch across nodes")
            rows.append(
                {
                    "node_id": self.compute_node_id(node),
                    "file_path": node.file_path,
                    "start_line": node.start_line,
                    "end_line": node.end_line,
                    "raw_signature": node.raw_signature,
                    "summary": node.docstring,
                    "vector": [float(value) for value in vector],
                }
            )

        if self._vector_dim is None and first_vector_dim is not None:
            self._vector_dim = first_vector_dim
        if first_vector_dim is not None and self._vector_dim != first_vector_dim:
            raise ValueError("embedding vector dimension mismatch with existing index")

        db = self._connect()
        table = self._open_table_if_exists(db)
        if table is None:
            if self._vector_dim is None:
                raise ValueError("vector dimension is not initialized")
            table = db.create_table(self._table_name, schema=self._schema(self._vector_dim))
        else:
            self._ensure_vector_dim_from_table(table)

        (
            table.merge_insert("node_id")
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute(rows)
        )
        return len(nodes)

    def search(self, query: str, top_k: int = 5) -> list[SkeletonNodeSearchResult]:
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be > 0")

        db = self._connect()
        table = self._open_table_if_exists(db)
        if table is None:
            return []

        self._ensure_vector_dim_from_table(table)
        query_vector = self._embedding_provider.embed(query)
        if not query_vector:
            raise ValueError("query embedding vector must not be empty")
        if self._vector_dim is not None and len(query_vector) != self._vector_dim:
            raise ValueError("query embedding vector dimension mismatch")

        rows = table.search([float(value) for value in query_vector]).limit(top_k).to_list()
        results: list[SkeletonNodeSearchResult] = []
        for row in rows:
            cleaned = {
                "node_id": row["node_id"],
                "file_path": row["file_path"],
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "raw_signature": row["raw_signature"],
                "summary": row["summary"],
            }
            results.append(cleaned)
        return results
