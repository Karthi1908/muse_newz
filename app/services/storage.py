from __future__ import annotations
import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional
from config.settings import settings
from app.models.schemas import (
    PublishedEdition,
    ReaderProfile,
    ScheduleState,
)


DEFAULT_TOPICS = [
    "Frontier AI & Agentic Systems",
    "Grid-Scale Clean Energy & Batteries",
    "Global Semiconductor Supply Chain",
    "Biotech & Longevity Clinical Trials",
    "Space Launch & Orbital Infrastructure",
]


class StorageService:
    """
    Deterministic SQLite + Disk persistence service (Constitution §2 & Plan §5).
    Manages reader profile, schedule state, build runs, archive retention (60 max),
    and published story records for no-repeat enforcement.
    """

    def __init__(self, db_path: Path | None = None, editions_dir: Path | None = None) -> None:
        self.db_path = db_path or settings.DB_PATH
        self.editions_dir = editions_dir or settings.EDITIONS_DIR
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.editions_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS reader_profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    reader_name TEXT NOT NULL DEFAULT 'Alex Rivera',
                    time_zone TEXT NOT NULL DEFAULT 'UTC',
                    geographic_preference TEXT NOT NULL DEFAULT 'Global',
                    topics_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS schedule_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    cadence TEXT NOT NULL DEFAULT 'daily',
                    start_time_local TEXT NOT NULL DEFAULT '07:00',
                    weekly_weekday TEXT DEFAULT 'SUN',
                    time_zone TEXT NOT NULL DEFAULT 'UTC',
                    paused INTEGER NOT NULL DEFAULT 0,
                    next_due_at TEXT,
                    last_run_at TEXT,
                    last_run_status TEXT,
                    last_failure_reason TEXT,
                    daily_cap INTEGER NOT NULL DEFAULT 6,
                    demo_mode INTEGER NOT NULL DEFAULT 0,
                    new_edition_available INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS build_runs (
                    run_id TEXT PRIMARY KEY,
                    trigger_type TEXT NOT NULL,
                    format_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt INTEGER NOT NULL DEFAULT 1,
                    current_stage TEXT,
                    progress_pct INTEGER NOT NULL DEFAULT 0,
                    progress_message TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    failure_reason TEXT,
                    edition_id TEXT
                );

                CREATE TABLE IF NOT EXISTS editions (
                    edition_id TEXT PRIMARY KEY,
                    edition_number INTEGER NOT NULL UNIQUE,
                    format_name TEXT NOT NULL,
                    format_label TEXT NOT NULL,
                    reader_name TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    design_version TEXT NOT NULL,
                    total_pages INTEGER NOT NULL,
                    total_articles INTEGER NOT NULL,
                    claims_checked INTEGER NOT NULL,
                    claims_verified INTEGER NOT NULL,
                    corrections_count INTEGER NOT NULL,
                    json_path TEXT NOT NULL,
                    html_path TEXT NOT NULL,
                    is_sample INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS published_story_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    edition_number INTEGER NOT NULL,
                    format_name TEXT NOT NULL,
                    canonical_url TEXT NOT NULL,
                    story_fingerprint TEXT NOT NULL,
                    headline TEXT NOT NULL,
                    published_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_story_records_date ON published_story_records(published_at);
                CREATE INDEX IF NOT EXISTS idx_story_records_fp ON published_story_records(story_fingerprint);
                """
            )
            # Migrate existing reader_profile table if geographic_preference column is missing
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(reader_profile)").fetchall()]
            if "geographic_preference" not in cols:
                conn.execute("ALTER TABLE reader_profile ADD COLUMN geographic_preference TEXT NOT NULL DEFAULT 'Global'")

            # Ensure default reader profile row exists
            row = conn.execute("SELECT id FROM reader_profile WHERE id = 1").fetchone()
            if not row:
                conn.execute(
                    "INSERT INTO reader_profile (id, reader_name, time_zone, geographic_preference, topics_json, updated_at) VALUES (1, ?, ?, ?, ?, ?)",
                    ("Alex Rivera", "UTC", "Global", json.dumps(DEFAULT_TOPICS), datetime.now(timezone.utc).isoformat()),
                )
            # Ensure default schedule_config row exists
            srow = conn.execute("SELECT id FROM schedule_config WHERE id = 1").fetchone()
            if not srow:
                next_due = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
                conn.execute(
                    """INSERT INTO schedule_config
                    (id, cadence, start_time_local, weekly_weekday, time_zone, paused, next_due_at, daily_cap, demo_mode, new_edition_available)
                    VALUES (1, 'daily', '07:00', 'SUN', 'UTC', 0, ?, ?, 0, 0)""",
                    (next_due, settings.DAILY_BUILD_CAP),
                )

    # ---- Reader Profile ----
    def get_reader_profile(self) -> ReaderProfile:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM reader_profile WHERE id = 1").fetchone()
            geo = row["geographic_preference"] if "geographic_preference" in row.keys() and row["geographic_preference"] else "Global"
            return ReaderProfile(
                reader_name=row["reader_name"],
                time_zone=row["time_zone"],
                geographic_preference=geo,
                topics=json.loads(row["topics_json"]),
            )

    def save_reader_profile(self, profile: ReaderProfile) -> ReaderProfile:
        with self._connect() as conn:
            conn.execute(
                """UPDATE reader_profile
                   SET reader_name = ?, time_zone = ?, geographic_preference = ?, topics_json = ?, updated_at = ?
                   WHERE id = 1""",
                (
                    profile.reader_name,
                    profile.time_zone,
                    profile.geographic_preference,
                    json.dumps(profile.topics),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return profile

    # ---- Schedule State ----
    def get_schedule_state(self, now: datetime | None = None) -> ScheduleState:
        ref_now = now or datetime.now(timezone.utc)
        today_prefix = ref_now.strftime("%Y-%m-%d")
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM schedule_config WHERE id = 1").fetchone()
            builds_today = conn.execute(
                "SELECT COUNT(*) AS cnt FROM build_runs WHERE status = 'completed' AND started_at LIKE ?",
                (f"{today_prefix}%",),
            ).fetchone()["cnt"]
            return ScheduleState(
                cadence=row["cadence"],
                start_time_local=row["start_time_local"],
                weekly_weekday=row["weekly_weekday"],
                time_zone=row["time_zone"],
                paused=bool(row["paused"]),
                next_due_at=datetime.fromisoformat(row["next_due_at"]) if row["next_due_at"] else None,
                last_run_at=datetime.fromisoformat(row["last_run_at"]) if row["last_run_at"] else None,
                last_run_status=row["last_run_status"],
                last_failure_reason=row["last_failure_reason"],
                builds_today_count=int(builds_today),
                daily_cap=int(row["daily_cap"]),
                demo_mode=bool(row["demo_mode"]),
                new_edition_available=bool(row["new_edition_available"]),
            )

    def update_schedule_state(self, **kwargs: Any) -> ScheduleState:
        allowed = {
            "cadence",
            "start_time_local",
            "weekly_weekday",
            "time_zone",
            "paused",
            "next_due_at",
            "last_run_at",
            "last_run_status",
            "last_failure_reason",
            "daily_cap",
            "demo_mode",
            "new_edition_available",
        }
        updates = {}
        for k, v in kwargs.items():
            if k in allowed:
                if isinstance(v, datetime):
                    updates[k] = v.isoformat()
                elif isinstance(v, bool):
                    updates[k] = 1 if v else 0
                else:
                    updates[k] = v
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            with self._connect() as conn:
                conn.execute(f"UPDATE schedule_config SET {set_clause} WHERE id = 1", list(updates.values()))
        return self.get_schedule_state()

    # ---- Build Runs & Concurrency ----
    def has_running_build(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM build_runs WHERE status = 'running'").fetchone()
            return int(row["cnt"]) > 0

    def create_build_run(
        self,
        run_id: str,
        trigger_type: str,
        format_name: str,
        status: str = "running",
        attempt: int = 1,
        started_at: datetime | None = None,
        failure_reason: str | None = None,
    ) -> None:
        ts = (started_at or datetime.now(timezone.utc)).isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO build_runs
                   (run_id, trigger_type, format_name, status, attempt, current_stage, progress_pct, progress_message, started_at, failure_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, trigger_type, format_name, status, attempt, "initializing", 5, "Initializing newsroom...", ts, failure_reason),
            )

    def update_build_progress(
        self,
        run_id: str,
        stage: str,
        progress_pct: int,
        message: str,
        attempt: int | None = None,
    ) -> None:
        with self._connect() as conn:
            if attempt is not None:
                conn.execute(
                    "UPDATE build_runs SET current_stage = ?, progress_pct = ?, progress_message = ?, attempt = ? WHERE run_id = ?",
                    (stage, progress_pct, message, attempt, run_id),
                )
            else:
                conn.execute(
                    "UPDATE build_runs SET current_stage = ?, progress_pct = ?, progress_message = ? WHERE run_id = ?",
                    (stage, progress_pct, message, run_id),
                )

    def finish_build_run(
        self,
        run_id: str,
        status: str,
        edition_id: str | None = None,
        failure_reason: str | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        ts = (finished_at or datetime.now(timezone.utc)).isoformat()
        pct = 100 if status == "completed" else 0
        with self._connect() as conn:
            conn.execute(
                """UPDATE build_runs
                   SET status = ?, progress_pct = ?, finished_at = ?, edition_id = ?, failure_reason = ?
                   WHERE run_id = ?""",
                (status, pct, ts, edition_id, failure_reason, run_id),
            )

    def get_active_or_latest_run(self) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM build_runs ORDER BY started_at DESC LIMIT 1").fetchone()
            return dict(row) if row else None

    # ---- Edition Numbers & Archive ----
    def next_edition_number(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(edition_number) AS max_num FROM editions").fetchone()
            max_num = row["max_num"] if row and row["max_num"] is not None else 0
            return int(max_num) + 1

    def get_last_edition_time(self, format_name: str | None = None) -> Optional[datetime]:
        with self._connect() as conn:
            if format_name:
                row = conn.execute(
                    "SELECT published_at FROM editions WHERE format_name = ? ORDER BY edition_number DESC LIMIT 1",
                    (format_name,),
                ).fetchone()
            else:
                row = conn.execute("SELECT published_at FROM editions ORDER BY edition_number DESC LIMIT 1").fetchone()
            return datetime.fromisoformat(row["published_at"]) if row else None

    def save_published_edition(
        self,
        edition: PublishedEdition,
        standalone_html: str,
        is_sample: bool = False,
        retention_limit: int | None = None,
    ) -> dict[str, Any]:
        limit = retention_limit or settings.ARCHIVE_RETENTION_LIMIT
        folder = self.editions_dir / edition.edition_id
        folder.mkdir(parents=True, exist_ok=True)
        json_path = folder / "edition.json"
        html_path = folder / f"{edition.edition_id}_standalone.html"

        edition.single_file_html_path = str(html_path)
        json_path.write_text(edition.model_dump_json(indent=2), encoding="utf-8")
        html_path.write_text(standalone_html, encoding="utf-8")

        total_articles = sum(len(p.articles) for p in edition.pages)

        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO editions
                   (edition_id, edition_number, format_name, format_label, reader_name, published_at, design_version,
                    total_pages, total_articles, claims_checked, claims_verified, corrections_count, json_path, html_path, is_sample)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    edition.edition_id,
                    edition.edition_number,
                    edition.format_name,
                    edition.format_label,
                    edition.reader_name,
                    edition.published_at.isoformat(),
                    edition.design_version,
                    edition.total_pages,
                    total_articles,
                    edition.total_claims_checked,
                    edition.total_claims_verified,
                    len(edition.corrections_box),
                    str(json_path),
                    str(html_path),
                    1 if is_sample else 0,
                ),
            )
            # Record published stories for no-repeat checks (FR-021)
            for page in edition.pages:
                for art in page.articles:
                    for src in art.sources:
                        conn.execute(
                            """INSERT INTO published_story_records
                               (edition_number, format_name, canonical_url, story_fingerprint, headline, published_at)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (
                                edition.edition_number,
                                edition.format_name,
                                src.url.lower().rstrip("/"),
                                art.headline.lower()[:64],
                                art.headline,
                                edition.published_at.isoformat(),
                            ),
                        )

            # Enforce Archive Retention Limit (FR-035, Story 6)
            rows = conn.execute("SELECT edition_id, json_path FROM editions ORDER BY edition_number DESC").fetchall()
            pruned_count = 0
            if len(rows) > limit:
                to_remove = rows[limit:]
                for old_row in to_remove:
                    conn.execute("DELETE FROM editions WHERE edition_id = ?", (old_row["edition_id"],))
                    old_folder = Path(old_row["json_path"]).parent
                    if old_folder.exists() and old_folder != self.editions_dir:
                        shutil.rmtree(old_folder, ignore_errors=True)
                    pruned_count += 1

        return {"edition_id": edition.edition_id, "pruned_count": pruned_count, "retention_limit": limit}

    def list_editions(self, format_filter: str | None = None) -> List[dict[str, Any]]:
        with self._connect() as conn:
            if format_filter and format_filter in ("bulletin", "daily", "weekly"):
                rows = conn.execute(
                    "SELECT * FROM editions WHERE format_name = ? ORDER BY edition_number DESC",
                    (format_filter,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM editions ORDER BY edition_number DESC").fetchall()
            return [dict(r) for r in rows]

    def get_edition(self, edition_id: str) -> Optional[PublishedEdition]:
        with self._connect() as conn:
            row = conn.execute("SELECT json_path FROM editions WHERE edition_id = ?", (edition_id,)).fetchone()
            if not row:
                return None
            p = Path(row["json_path"])
            if not p.exists():
                p = self.editions_dir / edition_id / "edition.json"
            if not p.exists():
                p = settings.BASE_DIR / "data" / "sample_seed" / edition_id / "edition.json"
            if not p.exists():
                return None
            return PublishedEdition.model_validate_json(p.read_text(encoding="utf-8"))

    def get_latest_edition(self) -> Optional[PublishedEdition]:
        items = self.list_editions()
        if not items:
            return None
        return self.get_edition(items[0]["edition_id"])

    def get_recent_story_records(self, lookback_days: int, now: datetime | None = None) -> List[dict[str, Any]]:
        ref = now or datetime.now(timezone.utc)
        cutoff = (ref - timedelta(days=lookback_days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM published_story_records WHERE published_at >= ? ORDER BY published_at DESC",
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]

    def record_story_fingerprint(
        self,
        edition_number: int,
        format_name: str,
        canonical_url: str,
        story_fingerprint: str,
        headline: str,
        published_at: datetime | None = None,
    ) -> None:
        ts = (published_at or datetime.now(timezone.utc)).isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO published_story_records
                   (edition_number, format_name, canonical_url, story_fingerprint, headline, published_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (edition_number, format_name, canonical_url, story_fingerprint, headline, ts),
            )
