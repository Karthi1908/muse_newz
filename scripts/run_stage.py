"""
CLI runner to execute any individual stage against mock data (Constitution Principle 8: Small and testable).
Usage:
  python scripts/run_stage.py --stage format_resolver --cadence weekly
"""
from __future__ import annotations
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.format_resolver import FormatResolver
from app.services.storage import DEFAULT_TOPICS


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single Your Daily Muse stage in isolation.")
    parser.add_argument(
        "--stage",
        choices=["format_resolver", "report", "full_edition"],
        default="format_resolver",
    )
    parser.add_argument("--cadence", default="daily")
    args = parser.parse_args()

    resolver = FormatResolver()
    if args.stage == "format_resolver":
        fmt = resolver.cadence_to_format_name(args.cadence)  # type: ignore[arg-type]
        pages, notices = resolver.build_page_and_slot_blueprint(fmt, DEFAULT_TOPICS)
        print(json.dumps({"format": fmt, "total_pages": len(pages), "pages": pages, "notices": notices}, indent=2))
    elif args.stage == "report":
        from datetime import datetime, timedelta, timezone
        from app.agents.reporters import ParallelNewsroomReporters

        rep = ParallelNewsroomReporters()
        now = datetime.now(timezone.utc)
        pool = await rep.gather_candidate_pool(DEFAULT_TOPICS[:3], "daily", now - timedelta(hours=26), now)
        print(pool.model_dump_json(indent=2))
    elif args.stage == "full_edition":
        from app.services.runner import EditionPipelineRunner

        runner = EditionPipelineRunner()
        ed = await runner.execute_edition_build(trigger_type="manual", override_cadence=args.cadence)  # type: ignore[arg-type]
        print(json.dumps({"edition_id": ed.edition_id, "pages": ed.total_pages, "claims_verified": ed.total_claims_verified}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
