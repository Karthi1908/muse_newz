from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional
from zoneinfo import ZoneInfo
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
except ImportError:
    AsyncIOScheduler = None  # type: ignore
from config.settings import settings
from app.models.schemas import CadenceType, ScheduleState, WeekdayType
from app.services.runner import EditionPipelineRunner
from app.services.storage import StorageService


WEEKDAY_MAP: Dict[str, int] = {
    "MON": 0,
    "TUE": 1,
    "WED": 2,
    "THU": 3,
    "FRI": 4,
    "SAT": 5,
    "SUN": 6,
}

CADENCE_HOURS_MAP: Dict[str, int] = {
    "every_4h": 4,
    "every_8h": 8,
    "every_12h": 12,
    "daily": 24,
    "weekly": 168,
}


class NewspaperSchedulerService:
    """
    Deterministic Scheduling Service backed by APScheduler + SQLite
    (Constitution Principle 2 & 8; Spec FR-004..FR-013, FR-038, Story 3, SC-004, SC-005, SC-012).
    Features:
      - Injectable `clock_fn` for deterministic fake-clock unit tests (Principle 8).
      - DST-aware local clock time calculation using `zoneinfo.ZoneInfo`.
      - Single-build concurrency lock (`FR-008`): skips overlapping due times and logs notice.
      - Post-downtime recovery (`FR-009`): triggers at most ONE catch-up edition.
      - Daily build cap (`FR-012`, default 6): blocks scheduled & manual runs once reached.
      - Compressed 2-minute Demo Mode (`FR-038`, `SC-012`).
    """

    def __init__(
        self,
        storage: StorageService | None = None,
        runner: EditionPipelineRunner | None = None,
        clock_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.storage = storage or StorageService()
        self.runner = runner or EditionPipelineRunner(storage=self.storage)
        self.clock_fn: Callable[[], datetime] = clock_fn or (lambda: datetime.now(timezone.utc))
        self._build_lock = asyncio.Lock()
        self._apscheduler: Optional[Any] = None
        self._bg_task: Optional[asyncio.Task] = None
        self.last_skip_notice: Optional[str] = None

    def now(self) -> datetime:
        dt = self.clock_fn()
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def compute_next_due_time(
        self,
        cadence: CadenceType,
        start_time_local: str,
        time_zone_str: str = "UTC",
        weekly_weekday: WeekdayType | None = "SUN",
        demo_mode: bool = False,
        reference_time: datetime | None = None,
    ) -> datetime:
        """
        Computes the next planned edition due time anchored to the reader's local wall clock
        across Daylight Saving Time transitions (Spec FR-005 & §9 Edge Case).
        """
        ref_utc = reference_time or self.now()
        if demo_mode:
            return ref_utc + timedelta(seconds=settings.DEMO_INTERVAL_SECONDS)

        try:
            tz = ZoneInfo(time_zone_str)
        except Exception:
            tz = ZoneInfo("UTC")

        ref_local = ref_utc.astimezone(tz)
        hh, mm = [int(x) for x in start_time_local.split(":")]

        if cadence == "weekly":
            target_wd = WEEKDAY_MAP.get(weekly_weekday or "SUN", 6)
            days_ahead = (target_wd - ref_local.weekday()) % 7
            candidate_local = ref_local.replace(hour=hh, minute=mm, second=0, microsecond=0) + timedelta(days=days_ahead)
            if candidate_local <= ref_local:
                candidate_local += timedelta(days=7)
            return candidate_local.astimezone(timezone.utc)

        if cadence == "daily":
            candidate_local = ref_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if candidate_local <= ref_local:
                # Add 1 calendar day in local timezone so wall-clock hour stays identical across DST shifts
                next_day = ref_local.date() + timedelta(days=1)
                candidate_local = datetime(
                    next_day.year, next_day.month, next_day.day, hh, mm, 0, tzinfo=tz
                )
            return candidate_local.astimezone(timezone.utc)

        # Sub-daily cadences: every_4h, every_8h, every_12h anchored to start_time_local grid
        step_hours = CADENCE_HOURS_MAP[cadence]
        anchor_local = ref_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
        while anchor_local > ref_local:
            anchor_local -= timedelta(hours=step_hours)
        while anchor_local <= ref_local:
            anchor_local += timedelta(hours=step_hours)
        # Re-localize wall-clock hour in case a DST boundary was crossed
        localized = datetime(
            anchor_local.year,
            anchor_local.month,
            anchor_local.day,
            anchor_local.hour,
            anchor_local.minute,
            0,
            tzinfo=tz,
        )
        if localized <= ref_local:
            localized += timedelta(hours=step_hours)
        return localized.astimezone(timezone.utc)

    def configure_schedule(
        self,
        cadence: CadenceType,
        start_time_local: str = "07:00",
        time_zone: str = "UTC",
        weekly_weekday: WeekdayType | None = "SUN",
        paused: bool = False,
        demo_mode: bool = False,
        daily_cap: int | None = None,
    ) -> ScheduleState:
        current_now = self.now()
        next_due = self.compute_next_due_time(
            cadence=cadence,
            start_time_local=start_time_local,
            time_zone_str=time_zone,
            weekly_weekday=weekly_weekday,
            demo_mode=demo_mode,
            reference_time=current_now,
        )
        updates: Dict[str, Any] = {
            "cadence": cadence,
            "start_time_local": start_time_local,
            "time_zone": time_zone,
            "weekly_weekday": weekly_weekday or "SUN",
            "paused": paused,
            "demo_mode": demo_mode,
            "next_due_at": next_due,
        }
        if daily_cap is not None:
            updates["daily_cap"] = daily_cap
        # Also keep reader_profile.time_zone synchronized
        profile = self.storage.get_reader_profile()
        if profile.time_zone != time_zone:
            profile.time_zone = time_zone
            self.storage.save_reader_profile(profile)

        return self.storage.update_schedule_state(**updates)

    async def check_and_run_due(self) -> dict[str, Any]:
        """
        Evaluates whether a scheduled or catch-up build is due at `self.now()`.
        Enforces:
          - Paused check (FR-007)
          - At-most-one catch-up edition across multiple missed intervals (FR-009)
          - Single-build concurrency lock (FR-008)
          - Daily build cap (FR-012)
        """
        current_now = self.now()
        state = self.storage.get_schedule_state(now=current_now)

        if state.paused or state.next_due_at is None:
            return {"action": "idle", "reason": "Schedule is paused or unset."}

        if current_now < state.next_due_at:
            return {"action": "idle", "next_due_at": state.next_due_at.isoformat()}

        # Determine if multiple intervals were missed during downtime (FR-009: at most ONE catch-up edition)
        step_sec = (
            settings.DEMO_INTERVAL_SECONDS
            if state.demo_mode
            else CADENCE_HOURS_MAP[state.cadence] * 3600
        )
        overdue_seconds = (current_now - state.next_due_at).total_seconds()
        trigger_kind = "catch_up" if overdue_seconds >= step_sec else "scheduled"

        # Advance next_due_at to the first slot strictly in the future so missed slots are coalesced into 1 run
        next_future_due = self.compute_next_due_time(
            cadence=state.cadence,
            start_time_local=state.start_time_local,
            time_zone_str=state.time_zone,
            weekly_weekday=state.weekly_weekday,
            demo_mode=state.demo_mode,
            reference_time=current_now,
        )
        self.storage.update_schedule_state(next_due_at=next_future_due)

        return await self.trigger_build(trigger_type=trigger_kind)

    async def trigger_build(
        self,
        trigger_type: str = "manual",
        simulated_stage_failure: Callable[[int], None] | None = None,
    ) -> dict[str, Any]:
        """
        Triggers either a 'scheduled', 'catch_up', or 'manual' ("Generate now") build.
        Never alters the next scheduled time on manual runs (Story 3).
        """
        current_now = self.now()
        state = self.storage.get_schedule_state(now=current_now)
        fmt_name = self.runner.format_resolver.cadence_to_format_name(state.cadence)

        # FR-008: Never run two builds for the same reader at the same time
        if self._build_lock.locked() or self.storage.has_running_build():
            skip_msg = "Skipped build trigger because an edition build is already in progress."
            self.last_skip_notice = skip_msg
            self.storage.create_build_run(
                run_id=f"skip_overlap_{int(current_now.timestamp())}",
                trigger_type=trigger_type,
                format_name=fmt_name,
                status="skipped",
                started_at=current_now,
                failure_reason=skip_msg,
            )
            return {"action": "skipped", "reason": skip_msg}

        # FR-012 & §9 Edge Case: Enforce daily build cap on both scheduled and manual builds
        if state.builds_today_count >= state.daily_cap:
            cap_msg = (
                f"Daily build cap reached ({state.builds_today_count}/{state.daily_cap} editions built today). "
                "Remaining builds today are paused until tomorrow."
            )
            self.last_skip_notice = cap_msg
            self.storage.create_build_run(
                run_id=f"skip_cap_{int(current_now.timestamp())}",
                trigger_type=trigger_type,
                format_name=fmt_name,
                status="skipped",
                started_at=current_now,
                failure_reason=cap_msg,
            )
            self.storage.update_schedule_state(last_run_status="skipped", last_failure_reason=cap_msg)
            return {"action": "capped", "reason": cap_msg}

        async with self._build_lock:
            try:
                edition = await self.runner.execute_edition_build(
                    trigger_type=trigger_type,
                    override_cadence=state.cadence,
                    now=current_now,
                    simulated_stage_failure=simulated_stage_failure,
                )
                return {
                    "action": "completed",
                    "trigger_type": trigger_type,
                    "edition_id": edition.edition_id,
                    "edition_number": edition.edition_number,
                    "format_name": edition.format_name,
                    "total_pages": edition.total_pages,
                }
            except Exception as exc:
                return {
                    "action": "failed",
                    "trigger_type": trigger_type,
                    "reason": str(exc),
                }

    def start_background_scheduler(self) -> None:
        if AsyncIOScheduler is not None:
            if self._apscheduler is not None and self._apscheduler.running:
                return
            self._apscheduler = AsyncIOScheduler()
            self._apscheduler.add_job(
                self.check_and_run_due,
                "interval",
                seconds=5,
                id="daily_muse_due_watcher",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )
            self._apscheduler.start()
            return

        if self._bg_task is None or self._bg_task.done():
            async def _loop() -> None:
                while True:
                    await asyncio.sleep(5)
                    await self.check_and_run_due()

            try:
                loop = asyncio.get_running_loop()
                self._bg_task = loop.create_task(_loop())
            except RuntimeError:
                pass

    def stop_background_scheduler(self) -> None:
        if self._apscheduler is not None and getattr(self._apscheduler, "running", False):
            self._apscheduler.shutdown(wait=False)
            self._apscheduler = None
        if self._bg_task is not None and not self._bg_task.done():
            self._bg_task.cancel()
            self._bg_task = None
