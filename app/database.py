import sqlite3
from contextlib import contextmanager
from threading import Lock


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = Lock()

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self._lock, self.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    mac TEXT NOT NULL,
                    ip TEXT,
                    broadcasts TEXT NOT NULL,
                    shutdown_url TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id INTEGER NOT NULL,
                    cron_expr TEXT NOT NULL,
                    broadcasts TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(device_id) REFERENCES devices(id) ON DELETE CASCADE
                )
                """
            )

    def list_devices(self):
        with self._lock, self.connection() as conn:
            rows = conn.execute("SELECT * FROM devices ORDER BY id ASC").fetchall()
        return [dict(row) for row in rows]

    def get_device(self, device_id: int):
        with self._lock, self.connection() as conn:
            row = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        return dict(row) if row else None

    def add_device(self, name: str, mac: str, ip: str | None, broadcasts_json: str, shutdown_url: str | None, created_at: str):
        with self._lock, self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO devices (name, mac, ip, broadcasts, shutdown_url, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, mac, ip, broadcasts_json, shutdown_url, created_at),
            )
            device_id = cursor.lastrowid
        return device_id

    def delete_device(self, device_id: int) -> int:
        with self._lock, self.connection() as conn:
            conn.execute("DELETE FROM schedules WHERE device_id = ?", (device_id,))
            cursor = conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        return cursor.rowcount

    def list_schedules(self):
        with self._lock, self.connection() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.device_id, s.cron_expr, s.broadcasts, s.enabled, s.created_at, d.name as device_name
                FROM schedules s
                JOIN devices d ON d.id = s.device_id
                ORDER BY s.id ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def add_schedule(self, device_id: int, cron_expr: str, broadcasts_json: str | None, created_at: str) -> int:
        with self._lock, self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO schedules (device_id, cron_expr, broadcasts, enabled, created_at)
                VALUES (?, ?, ?, 1, ?)
                """,
                (device_id, cron_expr, broadcasts_json, created_at),
            )
            schedule_id = cursor.lastrowid
        return schedule_id

    def list_schedule_ids_for_device(self, device_id: int):
        with self._lock, self.connection() as conn:
            rows = conn.execute("SELECT id FROM schedules WHERE device_id = ?", (device_id,)).fetchall()
        return [int(row["id"]) for row in rows]

    def delete_schedule(self, schedule_id: int) -> int:
        with self._lock, self.connection() as conn:
            cursor = conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        return cursor.rowcount
