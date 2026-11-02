from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional
from app.agents.editor import EditorInChiefAgent
from app.agents.reporters import ParallelNewsroomReporters
from app.agents.whitespace_agent import WhitespaceCreativeAgent
from app.models.schemas import CadenceType, PublishedEdition, ReaderProfile, WhitespaceFillerItem
from app.services.dedup import DeduplicationService
from app.services.format_resolver import FormatResolver
from app.services.formatter import NewspaperFormatterService
from app.services.gatekeeper import VerificationGatekeeper
from app.services.illustrator import IllustratorService
from app.services.sam_layout_analyzer import SamLayoutAnalyzer
from app.services.storage import StorageService


class EditionPipelineRunner:
    """
    Orchestrates the 5 Newsroom Stages with:
    - Snapshot isolation of reader profile & cadence at build start (FR-011)
    - Live progress updates (FR-036)
    - Automatic retry-once on failure (FR-010)
    - Graceful degradation when a topic or image step fails (FR-037, SC-011)
    """

    def __init__(
        self,
        storage: StorageService | None = None,
        format_resolver: FormatResolver | None = None,
    ) -> None:
        self.storage = storage or StorageService()
        self.format_resolver = format_resolver or FormatResolver()
        self.reporters = ParallelNewsroomReporters()
        self.dedup = DeduplicationService()
        self.editor = EditorInChiefAgent(format_resolver=self.format_resolver)
        self.gatekeeper = VerificationGatekeeper(format_resolver=self.format_resolver)
        self.illustrator = IllustratorService()
        self.sam_analyzer = SamLayoutAnalyzer()
        self.whitespace_agent = WhitespaceCreativeAgent()
        self.formatter = NewspaperFormatterService()

    async def execute_edition_build(
        self,
        trigger_type: str = "manual",
        override_cadence: CadenceType | None = None,
        override_reader: ReaderProfile | None = None,
        now: datetime | None = None,
        simulated_stage_failure: Callable[[int], None] | None = None,
    ) -> PublishedEdition:
        ref_now = now or datetime.now(timezone.utc)
        # Snapshot reader & schedule at the start of the build so mid-build edits don't alter it (FR-011)
        reader_snapshot = (override_reader or self.storage.get_reader_profile()).model_copy(deep=True)
        sched_snapshot = self.storage.get_schedule_state(now=ref_now)
        cadence: CadenceType = override_cadence or sched_snapshot.cadence
        format_name = self.format_resolver.cadence_to_format_name(cadence)

        run_id = f"run_{uuid.uuid4().hex[:10]}"
        self.storage.create_build_run(
            run_id=run_id,
            trigger_type=trigger_type,
            format_name=format_name,
            status="running",
            attempt=1,
            started_at=ref_now,
        )
        self.storage.update_schedule_state(last_run_at=ref_now, last_run_status="running")

        last_exc: Optional[Exception] = None
        for attempt in (1, 2):  # FR-010: A failed build MUST be retried once
            try:
                if simulated_stage_failure is not None:
                    simulated_stage_failure(attempt)

                edition = await self._run_pipeline_attempt(
                    run_id=run_id,
                    attempt=attempt,
                    reader_snapshot=reader_snapshot,
                    cadence=cadence,
                    format_name=format_name,
                    ref_now=ref_now,
                )
                self.storage.finish_build_run(
                    run_id=run_id,
                    status="completed",
                    edition_id=edition.edition_id,
                    finished_at=ref_now,
                )
                self.storage.update_schedule_state(
                    last_run_at=ref_now,
                    last_run_status="completed",
                    last_failure_reason=None,
                    new_edition_available=True,
                )
                return edition
            except Exception as exc:
                last_exc = exc
                if attempt == 1:
                    self.storage.update_build_progress(
                        run_id=run_id,
                        stage="retrying",
                        progress_pct=15,
                        message=f"Attempt 1 encountered an error ({exc}); automatically retrying build (Attempt 2 of 2)...",
                        attempt=2,
                    )

        reason = f"Edition build failed after 2 attempts: {last_exc}"
        self.storage.finish_build_run(
            run_id=run_id,
            status="failed",
            failure_reason=reason,
            finished_at=ref_now,
        )
        self.storage.update_schedule_state(
            last_run_at=ref_now,
            last_run_status="failed",
            last_failure_reason=reason,
        )
        raise RuntimeError(reason)

    async def _run_pipeline_attempt(
        self,
        run_id: str,
        attempt: int,
        reader_snapshot: ReaderProfile,
        cadence: CadenceType,
        format_name: str,
        ref_now: datetime,
    ) -> PublishedEdition:
        fmt_spec = self.format_resolver.get_format_spec(format_name)  # type: ignore[arg-type]
        last_ed_at = self.storage.get_last_edition_time(format_name=format_name)
        win_start, win_end = self.format_resolver.compute_story_window(
            cadence=cadence,
            last_edition_at=last_ed_at,
            now=ref_now,
        )

        # Stage 1: Parallel Beat Reporting
        print("STAGE 1: reporting...", flush=True)
        self.storage.update_build_progress(
            run_id=run_id,
            stage="reporting",
            progress_pct=20,
            message=f"Stage 1/5: Parallel Beat Reporters researching {len(reader_snapshot.topics)} topic(s)...",
            attempt=attempt,
        )
        raw_pool = await self.reporters.gather_candidate_pool(
            topics=reader_snapshot.topics,
            format_name=format_name,  # type: ignore[arg-type]
            window_start=win_start,
            window_end=win_end,
            max_per_topic=3,
            geographic_preference=reader_snapshot.geographic_preference,
        )

        # Stage 1.5: Deterministic De-duplication & No-Repeat Filter
        print("STAGE 1.5: dedup...", flush=True)
        self.storage.update_build_progress(
            run_id=run_id,
            stage="dedup",
            progress_pct=35,
            message="Stage 2/5: Deduplicating stories & checking recent edition archive...",
            attempt=attempt,
        )
        lookback_days = int(fmt_spec.get("no_repeat_lookback_days", 7))
        allow_followups = bool(fmt_spec.get("allow_follow_ups", False))
        recent_records = self.storage.get_recent_story_records(lookback_days=lookback_days, now=ref_now)
        filtered_pool, _ = self.dedup.filter_candidate_pool(
            pool=raw_pool,
            recent_records=recent_records,
            allow_weekly_follow_ups=allow_followups,
        )

        # Stage 2: Editorial Ranking & Slot Manifest
        print("STAGE 2: editing...", flush=True)
        self.storage.update_build_progress(
            run_id=run_id,
            stage="editing",
            progress_pct=50,
            message=f"Stage 3/5: Editor-in-Chief assembling {fmt_spec['label']} page manifest...",
            attempt=attempt,
        )
        ed_num = self.storage.next_edition_number()
        manifest = await self.editor.build_edition_manifest(
            edition_number=ed_num,
            reader=reader_snapshot,
            pool=filtered_pool,
        )

        # Stage 3: Adversarial Writer + Fact-Checker Loops & Gatekeeper
        print("STAGE 3: verifying...", flush=True)
        self.storage.update_build_progress(
            run_id=run_id,
            stage="verifying",
            progress_pct=70,
            message=f"Stage 4/5: Writer & Fact-Checker verifying claims across {len(manifest.slot_assignments)} articles...",
            attempt=attempt,
        )
        verified_articles, corrections_box, gate_notices = await self.gatekeeper.verify_all_slots_parallel(manifest)

        # Stage 4: House Style Illustrations
        print("STAGE 4: illustrating...", flush=True)
        self.storage.update_build_progress(
            run_id=run_id,
            stage="illustrating",
            progress_pct=85,
            message="Stage 5/5: Generating house-style illustrations & typesetting broadsheet pages...",
            attempt=attempt,
        )
        illustrated_articles, illus_notices = await self.illustrator.illustrate_edition_articles(
            manifest=manifest,
            articles=verified_articles,
        )

        # Stage 4b: SAM-3 Layout Blank-Space Segmentation & Creative Fillers (FR-039..FR-044, Story 11)
        print("STAGE 4b: analyzing whitespace with SAM-3...", flush=True)
        self.storage.update_build_progress(
            run_id=run_id,
            stage="layout_segmentation",
            progress_pct=92,
            message="Stage 5/5: Analyzing layout whitespace via SAM-3 & crafting satirical broadsheet fillers...",
            attempt=attempt,
        )
        fillers_by_page: dict[int, list[WhitespaceFillerItem]] = {}
        used_variant_keys: set[str] = set()

        page_articles_count: dict[int, int] = {}
        page_templates: dict[int, str] = {}
        for slot in manifest.slot_assignments:
            page_articles_count[slot.page_number] = page_articles_count.get(slot.page_number, 0) + 1
            page_templates[slot.page_number] = slot.page_template

        for p_num, tmpl in page_templates.items():
            count = page_articles_count.get(p_num, 0)
            regions = await self.sam_analyzer.analyze_page_whitespace(
                page_number=p_num,
                template=tmpl,
                format_name=format_name,
                articles_count=count,
            )
            if regions:
                page_fillers = await self.whitespace_agent.create_fillers_for_page(
                    page_number=p_num,
                    page_template=tmpl,
                    regions=regions,
                    edition_topics=reader_snapshot.topics,
                    used_variant_keys=used_variant_keys,
                )
                if page_fillers:
                    fillers_by_page[p_num] = page_fillers

        # Stage 5: Multi-Page Formatting & Persistence
        print("STAGE 5: formatting...", flush=True)
        all_notices = gate_notices + illus_notices
        edition, standalone_html = self.formatter.assemble_and_render_edition(
            manifest=manifest,
            articles=illustrated_articles,
            corrections_box=corrections_box,
            notices=all_notices,
            whitespace_fillers_by_page=fillers_by_page,
            published_at=ref_now,
        )
        save_res = self.storage.save_published_edition(edition=edition, standalone_html=standalone_html)
        if save_res.get("pruned_count", 0) > 0:
            edition.notices.append(
                f"Archive retention limit ({save_res['retention_limit']} editions) reached; removed {save_res['pruned_count']} oldest edition(s)."
            )
        return edition
