from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from autopaper.utils import ensure_directory, stable_fingerprint


class StateStore:
    def __init__(self, state_dir: str) -> None:
        self.state_dir = ensure_directory(state_dir)
        self.db_path = Path(self.state_dir) / "state.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT,
                added_count INTEGER DEFAULT 0,
                skipped_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                report_md_path TEXT,
                report_json_path TEXT,
                scheduler_context TEXT
            );
            CREATE TABLE IF NOT EXISTS seen_papers (
                profile_name TEXT NOT NULL,
                paper_fingerprint TEXT NOT NULL,
                source TEXT,
                source_id TEXT,
                doi TEXT,
                title_norm TEXT,
                first_seen_at TEXT,
                last_seen_at TEXT,
                zotero_key TEXT,
                last_outcome TEXT,
                PRIMARY KEY (profile_name, paper_fingerprint)
            );
            CREATE TABLE IF NOT EXISTS run_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                event_at TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                payload TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(id)
            );
            CREATE TABLE IF NOT EXISTS config_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_name TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                config_json TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def capture_config_snapshot(self, profile_name: str, captured_at: str, config_json: str) -> None:
        self.conn.execute(
            "INSERT INTO config_snapshots (profile_name, captured_at, config_json) VALUES (?, ?, ?)",
            (profile_name, captured_at, config_json),
        )
        self.conn.commit()

    def start_run(self, profile_name: str, started_at: str, scheduler_context: Dict[str, Any]) -> int:
        cur = self.conn.execute(
            "INSERT INTO runs (profile_name, started_at, scheduler_context) VALUES (?, ?, ?)",
            (profile_name, started_at, json.dumps(scheduler_context)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(
        self,
        run_id: int,
        finished_at: str,
        status: str,
        added_count: int,
        skipped_count: int,
        failure_count: int,
        report_md_path: str,
        report_json_path: str,
    ) -> None:
        self.conn.execute(
            """
            UPDATE runs
            SET finished_at = ?, status = ?, added_count = ?, skipped_count = ?, failure_count = ?,
                report_md_path = ?, report_json_path = ?
            WHERE id = ?
            """,
            (finished_at, status, added_count, skipped_count, failure_count, report_md_path, report_json_path, run_id),
        )
        self.conn.commit()

    def record_event(self, run_id: int, event_at: str, level: str, message: str, payload: Optional[Dict[str, Any]] = None) -> None:
        self.conn.execute(
            "INSERT INTO run_events (run_id, event_at, level, message, payload) VALUES (?, ?, ?, ?, ?)",
            (run_id, event_at, level, message, json.dumps(payload) if payload else None),
        )
        self.conn.commit()

    def remember_paper(
        self,
        profile_name: str,
        source: str,
        source_id: str,
        doi: Optional[str],
        title_norm: str,
        seen_at: str,
        zotero_key: Optional[str],
        last_outcome: str,
    ) -> None:
        fingerprint = stable_fingerprint(doi or "", source_id or "", title_norm)
        self.conn.execute(
            """
            INSERT INTO seen_papers (
                profile_name, paper_fingerprint, source, source_id, doi, title_norm,
                first_seen_at, last_seen_at, zotero_key, last_outcome
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(profile_name, paper_fingerprint) DO UPDATE SET
                last_seen_at=excluded.last_seen_at,
                zotero_key=excluded.zotero_key,
                last_outcome=excluded.last_outcome
            """,
            (
                profile_name,
                fingerprint,
                source,
                source_id,
                doi,
                title_norm,
                seen_at,
                seen_at,
                zotero_key,
                last_outcome,
            ),
        )
        self.conn.commit()
