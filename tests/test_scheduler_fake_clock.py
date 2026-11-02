import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from app.agents.topic_agent import TopicEditorAgent
from app.models.schemas import ReaderProfile
from app.services.runner import EditionPipelineRunner
from app.services.scheduler import NewspaperSchedulerService
from app.services.storage import StorageService


class FakeClock:
    def __init__(self, initial: datetime) -> None:
        self.current = initial

    def __call__(self) -> datetime:
        return self.current

    def advance(self, **kwargs) -> datetime:
        self.current += timedelta(**kwargs)
        return self.current


@pytest.mark.asyncio
async def test_scheduler_fake_clock_due_run_and_downtime_single_catchup(tmp_path: Path):
    """
    Principle 8 (Fake clock testability), FR-006, FR-009:
    1. When due time arrives, edition builds automatically and sets new_edition_available=True.
    2. After downtime across several due times, builds at most ONE catch-up edition.
    """
    clock = FakeClock(datetime(2026, 10, 31, 6, 0, tzinfo=timezone.utc))
    store = StorageService(db_path=tmp_path / "sched.db", editions_dir=tmp_path / "editions")
    runner = EditionPipelineRunner(storage=store)
    sched = NewspaperSchedulerService(storage=store, runner=runner, clock_fn=clock)

    state = sched.configure_schedule(cadence="every_4h", start_time_local="08:00", time_zone="UTC")
    assert state.next_due_at == datetime(2026, 10, 31, 8, 0, tzinfo=timezone.utc)

    # Before due time -> idle
    res_early = await sched.check_and_run_due()
    assert res_early["action"] == "idle"

    # Simulate 14 hours of app downtime (3 missed 4-hour intervals: 08:00, 12:00, 16:00, 20:00)
    clock.advance(hours=14, minutes=5)
    res_catchup = await sched.check_and_run_due()
    assert res_catchup["action"] == "completed"
    assert res_catchup["trigger_type"] == "catch_up"

    # Immediately checking again must NOT run a second catch-up build (FR-009: at most ONE catch-up edition)
    res_second = await sched.check_and_run_due()
    assert res_second["action"] == "idle"
    assert len(store.list_editions()) == 1
    assert store.get_schedule_state(now=clock()).new_edition_available is True


@pytest.mark.asyncio
async def test_single_build_concurrency_lock_and_retry_once_and_daily_cap(tmp_path: Path):
    """
    FR-008 (No overlapping builds), FR-010 (Retry once on failure), FR-012 (Daily build cap = 6).
    """
    clock = FakeClock(datetime(2026, 10, 31, 9, 0, tzinfo=timezone.utc))
    store = StorageService(db_path=tmp_path / "lock.db", editions_dir=tmp_path / "editions")
    runner = EditionPipelineRunner(storage=store)
    sched = NewspaperSchedulerService(storage=store, runner=runner, clock_fn=clock)

    # 1. Test Retry-Once succeeds on Attempt 2 when Attempt 1 fails (FR-010)
    attempts_seen = []

    def fail_first_attempt(attempt: int) -> None:
        attempts_seen.append(attempt)
        if attempt == 1:
            raise RuntimeError("Transient network timeout in Stage 1")

    res_retry = await sched.trigger_build(trigger_type="manual", simulated_stage_failure=fail_first_attempt)
    assert res_retry["action"] == "completed"
    assert attempts_seen == [1, 2]

    # 2. Test Concurrency Lock (FR-008): when lock is held, overlapping trigger is skipped
    async with sched._build_lock:
        res_overlap = await sched.trigger_build(trigger_type="scheduled")
        assert res_overlap["action"] == "skipped"
        assert "already in progress" in res_overlap["reason"]

    # 3. Test Daily Cap enforcement (FR-012: default 6 builds/day; set cap=1 since 1 build already completed)
    sched.configure_schedule(cadence="daily", daily_cap=1)
    res_capped = await sched.trigger_build(trigger_type="manual")
    assert res_capped["action"] == "capped"
    assert "Daily build cap reached" in res_capped["reason"]


@pytest.mark.asyncio
async def test_dst_timezone_preservation_and_demo_mode_2_minutes(tmp_path: Path):
    """
    Spec §9 Edge Case (DST local clock time preserved) & FR-038 / SC-012 (2-minute Demo Mode).
    """
    # US Daylight Saving Time fallback weekend (Nov 1, 2026 in America/New_York)
    clock = FakeClock(datetime(2026, 10, 31, 15, 0, tzinfo=timezone.utc))
    store = StorageService(db_path=tmp_path / "dst.db", editions_dir=tmp_path / "editions")
    sched = NewspaperSchedulerService(storage=store, clock_fn=clock)

    state = sched.configure_schedule(
        cadence="daily",
        start_time_local="07:00",
        time_zone="America/New_York",
        demo_mode=False,
    )
    from zoneinfo import ZoneInfo

    ny_time = state.next_due_at.astimezone(ZoneInfo("America/New_York"))
    assert ny_time.hour == 7 and ny_time.minute == 0

    # Demo Mode sets next due time to +120 seconds (2 minutes, well within SC-012 5 minutes)
    demo_state = sched.configure_schedule(cadence="daily", demo_mode=True)
    assert (demo_state.next_due_at - clock()).total_seconds() == 120


@pytest.mark.asyncio
async def test_topic_editor_confirmation_and_no_silent_truncation_over_5():
    """
    FR-001..003 & Story 8:
    - Editing topics ("drop Space Launch, add Climate Tech") updates the proposed list.
    - Adding a 6th topic does NOT silently truncate; sets requires_replacement_choice=True.
    """
    agent = TopicEditorAgent()
    current = ["AI", "Clean Energy", "Semiconductors", "Biotech", "Space Launch"]

    # 1. Drop and add command
    prop1 = await agent.propose_topic_change(current, "drop Space Launch, add Climate Tech")
    assert prop1.requires_replacement_choice is False
    assert "Climate Tech" in prop1.proposed_topics
    assert len(prop1.proposed_topics) == 5

    # 2. Attempt to add a 6th topic -> asks which topic to replace
    prop_overflow = await agent.propose_topic_change(current, "add Quantum Cryptography")
    assert prop_overflow.requires_replacement_choice is True
    assert prop_overflow.overflow_topic_candidate == "Quantum Cryptography"
    assert len(prop_overflow.proposed_topics) == 5  # Unchanged until user picks replacement

    # 3. Supplying replacement choice completes the swap cleanly
    prop_resolved = await agent.propose_topic_change(
        current, "Quantum Cryptography", replace_target="Biotech"
    )
    assert prop_resolved.requires_replacement_choice is False
    assert "Quantum Cryptography" in prop_resolved.proposed_topics
    assert "Biotech" not in prop_resolved.proposed_topics

    # 4. Multi-drop: drop multiple topics simultaneously (can have any count between 1 and 5)
    prop_multi_drop = await agent.propose_topic_change(
        current, "drop Space Launch and Biotech"
    )
    assert prop_multi_drop.requires_replacement_choice is False
    assert len(prop_multi_drop.proposed_topics) == 3
    assert "Space Launch" not in prop_multi_drop.proposed_topics
    assert "Biotech" not in prop_multi_drop.proposed_topics

    # 5. Multi-add: add multiple topics simultaneously
    three_topics = ["AI", "Clean Energy", "Semiconductors"]
    prop_multi_add = await agent.propose_topic_change(
        three_topics, "add Quantum Cryptography, Robotics"
    )
    assert prop_multi_add.requires_replacement_choice is False
    assert len(prop_multi_add.proposed_topics) == 5
    assert "Quantum Cryptography" in prop_multi_add.proposed_topics
    assert "Robotics" in prop_multi_add.proposed_topics

    # 6. Multi-drop and Multi-add in single command
    prop_mixed = await agent.propose_topic_change(
        current, "drop Space Launch, Biotech; add Synthetic Biology, Nuclear Fusion"
    )
    assert prop_mixed.requires_replacement_choice is False
    assert len(prop_mixed.proposed_topics) == 5
    assert "Synthetic Biology" in prop_mixed.proposed_topics
    assert "Nuclear Fusion" in prop_mixed.proposed_topics
    assert "Space Launch" not in prop_mixed.proposed_topics
    assert "Biotech" not in prop_mixed.proposed_topics

    # 7. Complete reset / set command to any number <= 5
    prop_set = await agent.propose_topic_change(current, "set topics to AI, Robotics")
    assert prop_set.requires_replacement_choice is False
    assert len(prop_set.proposed_topics) == 2
    assert prop_set.proposed_topics == ["AI", "Robotics"]

    # 8. Protection against removing all topics (minimum 1 required)
    prop_drop_all = await agent.propose_topic_change(
        ["AI"], "drop AI"
    )
    assert "at least 1 topic" in prop_drop_all.assistant_message
    assert len(prop_drop_all.proposed_topics) == 1
