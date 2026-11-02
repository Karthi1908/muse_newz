from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Dict, List
from app.models.schemas import CandidatePool, CandidateStory, FormatName
from app.services.search_web import WebResearchService


class ParallelNewsroomReporters:
    """
    Stage 1: Google ADK ParallelAgent Beat Reporters + Outside-Topics Scout
    (Constitution Principle 3; Spec FR-017, FR-019, Story 1, Story 9).
    Searches each reader topic concurrently over the format's story window.
    """

    def __init__(self, search_service: WebResearchService | None = None) -> None:
        self.search_service = search_service or WebResearchService()

    async def gather_candidate_pool(
        self,
        topics: List[str],
        format_name: FormatName,
        window_start: datetime,
        window_end: datetime,
        max_per_topic: int = 3,
        geographic_preference: str = "Global",
    ) -> CandidatePool:
        async def _report_single_topic(topic_name: str) -> tuple[str, List[CandidateStory]]:
            stories = await self.search_service.search_topic_candidates(
                topic=topic_name,
                window_start=window_start,
                window_end=window_end,
                max_results=max_per_topic,
                geographic_preference=geographic_preference,
            )
            return topic_name, stories

        topic_tasks = [_report_single_topic(t) for t in topics]
        include_outside = format_name in ("daily", "weekly")

        if include_outside:
            outside_task = asyncio.create_task(
                self.search_service.search_outside_topics_candidates(user_topics=topics)
            )
            topic_results = await asyncio.gather(*topic_tasks)
            outside_candidates = await outside_task
        else:
            topic_results = await asyncio.gather(*topic_tasks)
            outside_candidates = []

        candidates_by_topic: Dict[str, List[CandidateStory]] = {}
        empty_topics: List[str] = []
        for t_name, cands in topic_results:
            candidates_by_topic[t_name] = cands
            if not cands:
                empty_topics.append(t_name)

        return CandidatePool(
            format_name=format_name,
            story_window_start=window_start,
            story_window_end=window_end,
            candidates_by_topic=candidates_by_topic,
            outside_candidates=outside_candidates,
            empty_topics=empty_topics,
        )
