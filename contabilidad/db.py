from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from contabilidad.config import DEFAULT_DB_PATH


class LocalDatabase:
    """Simple SQLite-based repository for the early-stage local prototype."""

    def __init__(self, database_path: str | Path = DEFAULT_DB_PATH):
        self.database_path = Path(database_path) if not isinstance(database_path, str) or database_path != ":memory:" else database_path
        if isinstance(self.database_path, Path):
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row
        self.initialize_schema()

    def initialize_schema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                employee_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                source TEXT NOT NULL,
                file_name TEXT,
                raw_text TEXT,
                status TEXT NOT NULL,
                extracted_fields TEXT,
                validation_notes TEXT,
                created_at TEXT NOT NULL,
                processed_at TEXT
            )
            """
        )
        self.connection.commit()

    def create_user(self, user_id: str, name: str, phone: str, employee_id: str, created_at: str) -> Dict[str, Any]:
        self.connection.execute(
            "INSERT INTO users (user_id, name, phone, employee_id, created_at, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (user_id, name, phone, employee_id, created_at),
        )
        self.connection.commit()
        return self.get_user_by_phone(phone)

    def get_user_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        row = self.connection.execute(
            "SELECT * FROM users WHERE phone = ?",
            (phone,),
        ).fetchone()
        return dict(row) if row else None

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        row = self.connection.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None

    def create_document(
        self,
        document_id: str,
        user_id: str,
        source: str,
        file_name: str,
        raw_text: str,
        status: str,
        extracted_fields: Dict[str, Any],
        validation_notes: Iterable[str],
        created_at: str,
        processed_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.connection.execute(
            """
            INSERT INTO documents (
                document_id, user_id, source, file_name, raw_text, status,
                extracted_fields, validation_notes, created_at, processed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                user_id,
                source,
                file_name,
                raw_text,
                status,
                json.dumps(extracted_fields, ensure_ascii=False),
                json.dumps(list(validation_notes), ensure_ascii=False),
                created_at,
                processed_at,
            ),
        )
        self.connection.commit()
        return self.get_document(document_id)

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        row = self.connection.execute(
            "SELECT * FROM documents WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["extracted_fields"] = json.loads(payload["extracted_fields"] or "{}")
        payload["validation_notes"] = json.loads(payload["validation_notes"] or "[]")
        return payload

    def list_users(self) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM users ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def list_documents(self, user_id: Optional[str] = None) -> list[dict]:
        if user_id:
            rows = self.connection.execute(
                "SELECT * FROM documents WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM documents ORDER BY created_at DESC"
            ).fetchall()
        items = []
        for row in rows:
            payload = dict(row)
            payload["extracted_fields"] = json.loads(payload["extracted_fields"] or "{}")
            payload["validation_notes"] = json.loads(payload["validation_notes"] or "[]")
            items.append(payload)
        return items

    def close(self) -> None:
        self.connection.close()
