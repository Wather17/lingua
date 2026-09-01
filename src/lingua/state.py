from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

from .models import Clipping, TranslationItem


SCHEMA = """
CREATE TABLE IF NOT EXISTS clippings (
    fingerprint TEXT PRIMARY KEY,
    book_key TEXT NOT NULL,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    location TEXT NOT NULL,
    english TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'discovered',
    portuguese TEXT,
    vocabulary TEXT,
    grammar TEXT,
    model TEXT,
    prompt_version TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_clippings_book_status ON clippings(book_key, status);
"""


class StateStore:
    def __init__(self, workspace: Path):
        self.path = workspace / "lingua.db"
        workspace.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def statuses(self, fingerprints: list[str]) -> dict[str, str]:
        if not fingerprints:
            return {}
        result: dict[str, str] = {}
        with self.connect() as connection:
            for start in range(0, len(fingerprints), 500):
                batch = fingerprints[start : start + 500]
                placeholders = ",".join("?" for _ in batch)
                rows = connection.execute(
                    f"SELECT fingerprint, status FROM clippings WHERE fingerprint IN ({placeholders})", batch
                )
                result.update({row["fingerprint"]: row["status"] for row in rows})
        return result

    def discover(self, clippings: list[Clipping]) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO clippings(fingerprint, book_key, title, author, location, english)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(fingerprint) DO NOTHING
                """,
                [
                    (
                        item.fingerprint,
                        item.book_key,
                        item.title,
                        item.author,
                        item.location,
                        item.text,
                    )
                    for item in clippings
                ],
            )

    def untranslated(self, fingerprints: list[str]) -> set[str]:
        if not fingerprints:
            return set()
        result: set[str] = set()
        with self.connect() as connection:
            for start in range(0, len(fingerprints), 500):
                batch = fingerprints[start : start + 500]
                placeholders = ",".join("?" for _ in batch)
                rows = connection.execute(
                    f"SELECT fingerprint FROM clippings WHERE fingerprint IN ({placeholders}) AND portuguese IS NULL",
                    batch,
                )
                result.update(row["fingerprint"] for row in rows)
        return result

    def save_translations(
        self, translations: list[TranslationItem], model: str, prompt_version: str
    ) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                UPDATE clippings
                SET portuguese = ?, vocabulary = ?, grammar = ?, model = ?, prompt_version = ?,
                    status = 'drafted', updated_at = CURRENT_TIMESTAMP
                WHERE fingerprint = ?
                """,
                [
                    (
                        item.portuguese,
                        "\n".join(item.vocabulary),
                        item.grammar,
                        model,
                        prompt_version,
                        item.id,
                    )
                    for item in translations
                ],
            )

    def rows(self, fingerprints: list[str]) -> list[sqlite3.Row]:
        if not fingerprints:
            return []
        order = {fingerprint: index for index, fingerprint in enumerate(fingerprints)}
        collected: list[sqlite3.Row] = []
        with self.connect() as connection:
            for start in range(0, len(fingerprints), 500):
                batch = fingerprints[start : start + 500]
                placeholders = ",".join("?" for _ in batch)
                collected.extend(
                    connection.execute(
                        f"SELECT * FROM clippings WHERE fingerprint IN ({placeholders})", batch
                    ).fetchall()
                )
        return sorted(collected, key=lambda row: order[row["fingerprint"]])

    def mark_many(self, fingerprints: list[str], status: str) -> None:
        if status not in {"exported", "rejected"}:
            raise ValueError(f"estado final inválido: {status}")
        with self.connect() as connection:
            connection.executemany(
                "UPDATE clippings SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE fingerprint = ?",
                [(status, fingerprint) for fingerprint in fingerprints],
            )

