"""
Seeds the archive with 3 ready-made sample editions (1 Bulletin, 1 Daily, 1 Weekly)
so Your Daily Muse ships with a complete sample archive out of the box (FR-038, SC-003, SC-007).
"""
from __future__ import annotations
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.runner import EditionPipelineRunner
from app.services.storage import StorageService
from config.settings import settings


async def ensure_sample_archive_seeded(storage: StorageService | None = None, force_reseed: bool = False) -> int:
    store = storage or StorageService()
    existing = store.list_editions()
    if len(existing) >= 3 and not force_reseed:
        return 0

    # 1. Fast Path (FR-038): Load pre-rendered sample archive if present (<50ms, zero network calls)
    sample_seed_dir = settings.BASE_DIR / "data" / "sample_seed"
    if sample_seed_dir.exists() and not force_reseed:
        import json
        from app.models.schemas import PublishedEdition
        from app.services.formatter import NewspaperFormatterService
        fmt = NewspaperFormatterService()
        loaded = 0
        for sub in sorted(sample_seed_dir.iterdir()):
            j_file = sub / "edition.json"
            if j_file.exists():
                try:
                    ed_dict = json.loads(j_file.read_text(encoding="utf-8"))
                    edition = PublishedEdition.model_validate(ed_dict)
                    html_file = next(sub.glob("*_standalone.html"), None)
                    if html_file and html_file.exists():
                        html_str = html_file.read_text(encoding="utf-8")
                    else:
                        html_str = fmt.render_standalone_html(edition)
                    store.save_published_edition(edition=edition, standalone_html=html_str, is_sample=True)
                    loaded += 1
                except Exception:
                    pass
        if loaded >= 3:
            return loaded

    if force_reseed:
        with store._connect() as conn:
            conn.execute("DELETE FROM editions")
            conn.execute("DELETE FROM published_story_records")
            conn.execute("DELETE FROM build_runs")

    runner = EditionPipelineRunner(storage=store)
    base_time = datetime.now(timezone.utc) - timedelta(days=3)

    # Seed 1: Bulletin (every_4h -> 1 page, 3 articles)
    await runner.execute_edition_build(
        trigger_type="scheduled",
        override_cadence="every_4h",
        now=base_time,
    )
    # Clear story records between initial sample seeds so all 3 formats showcase full topic coverage
    with store._connect() as conn:
        conn.execute("DELETE FROM published_story_records")
        conn.execute("DELETE FROM build_runs")

    # Seed 2: Daily (daily -> 2 pages, 8 articles, 1 outside-topics)
    await runner.execute_edition_build(
        trigger_type="scheduled",
        override_cadence="daily",
        now=base_time + timedelta(days=1),
    )
    with store._connect() as conn:
        conn.execute("DELETE FROM published_story_records")
        conn.execute("DELETE FROM build_runs")

    # Seed 3: Weekly (weekly -> 7 pages for 5 topics, up to 16 articles, 1 outside-topics feature)
    await runner.execute_edition_build(
        trigger_type="scheduled",
        override_cadence="weekly",
        now=base_time + timedelta(days=2),
    )
    with store._connect() as conn:
        conn.execute("DELETE FROM build_runs")
        conn.execute("UPDATE editions SET is_sample = 1")
        conn.execute("UPDATE schedule_config SET new_edition_available = 0 WHERE id = 1")

    return 3


if __name__ == "__main__":
    count = asyncio.run(ensure_sample_archive_seeded(force_reseed=True))
    print(f"Seeded {count} sample editions into archive with real illustrations.")
