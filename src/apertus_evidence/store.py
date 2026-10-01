from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .chunking import Chunk


@dataclass(frozen=True)
class SearchHit:
    chunk_id: int
    source: str
    ordinal: int
    text: str
    sha256: str
    rank: float


class EvidenceStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "EvidenceStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL UNIQUE,
                content_sha256 TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                ordinal INTEGER NOT NULL,
                text TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                UNIQUE(document_id, ordinal)
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
            USING fts5(chunk_id UNINDEXED, text, tokenize='unicode61');
            """
        )
        self.conn.commit()

    def replace_document(self, source: str, content: str, chunks: list[Chunk]) -> int:
        content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with self.conn:
            existing = self.conn.execute(
                "SELECT id FROM documents WHERE source = ?", (source,)
            ).fetchone()
            if existing:
                doc_id = int(existing["id"])
                chunk_ids = [
                    int(r["id"])
                    for r in self.conn.execute(
                        "SELECT id FROM chunks WHERE document_id = ?", (doc_id,)
                    ).fetchall()
                ]
                if chunk_ids:
                    placeholders = ",".join("?" for _ in chunk_ids)
                    self.conn.execute(
                        f"DELETE FROM chunks_fts WHERE chunk_id IN ({placeholders})",
                        chunk_ids,
                    )
                self.conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

            cur = self.conn.execute(
                "INSERT INTO documents(source, content_sha256) VALUES (?, ?)",
                (source, content_sha),
            )
            doc_id = int(cur.lastrowid)

            for chunk in chunks:
                chunk_sha = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
                cur = self.conn.execute(
                    """
                    INSERT INTO chunks(
                        document_id, ordinal, text, sha256, start_offset, end_offset
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        chunk.ordinal,
                        chunk.text,
                        chunk_sha,
                        chunk.start_offset,
                        chunk.end_offset,
                    ),
                )
                chunk_id = int(cur.lastrowid)
                self.conn.execute(
                    "INSERT INTO chunks_fts(chunk_id, text) VALUES (?, ?)",
                    (chunk_id, chunk.text),
                )

        return doc_id

    @staticmethod
    def _fts_query(query: str) -> str:
        terms = re.findall(r"[\wÀ-ÿ]+", query, flags=re.UNICODE)
        if not terms:
            return ""
        unique = list(dict.fromkeys(term.casefold() for term in terms))
        return " OR ".join(f'"{term}"' for term in unique[:24])

    def search(self, query: str, *, limit: int = 6) -> list[SearchHit]:
        fts_query = self._fts_query(query)
        if not fts_query:
            return []

        rows = self.conn.execute(
            """
            SELECT
                c.id AS chunk_id,
                d.source AS source,
                c.ordinal AS ordinal,
                c.text AS text,
                c.sha256 AS sha256,
                bm25(chunks_fts) AS rank
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.chunk_id
            JOIN documents d ON d.id = c.document_id
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()

        return [
            SearchHit(
                chunk_id=int(r["chunk_id"]),
                source=str(r["source"]),
                ordinal=int(r["ordinal"]),
                text=str(r["text"]),
                sha256=str(r["sha256"]),
                rank=float(r["rank"]),
            )
            for r in rows
        ]
