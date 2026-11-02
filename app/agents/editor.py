from __future__ import annotations
from datetime import datetime
import re
from typing import Dict, List, Optional
from pydantic import BaseModel
from config.settings import settings
from app.agents.meta_model import get_muse_model
from app.models.schemas import (
    CandidatePool,
    CandidateStory,
    EditionManifest,
    ReaderProfile,
    SlotAssignment,
)
from app.services.format_resolver import FormatResolver


class EditorialLeadDecision(BaseModel):
    main_lead_candidate_id: str
    rationale: Optional[str] = None


def score_editorial_newsworthiness(
    story: CandidateStory,
    reference_date: str | None = None,
) -> float:
    """
    Evaluates real-world editorial magnitude, financial scale, breaking urgency,
    multi-source convergence, and recency so major breaking news (e.g. a $6.3B hack)
    always takes the Front-Page Centrepiece Lead slot over routine announcements.
    """
    score = float(story.relevance_score)
    text = f"{story.headline} {story.summary}".lower()

    # 1. Financial / Quantitative Scale (Multi-billion or trillion dollar impact)
    max_billion_impact = 0.0
    for match in re.finditer(r"\$?\s*(\d+(?:\.\d+)?)\s*(trillion|billion|million|t\b|b\b|m\b)", text):
        val = float(match.group(1))
        unit = match.group(2).lower()
        if unit.startswith("t"):
            billions = val * 1000.0
        elif unit.startswith("b"):
            billions = val
        else:
            billions = val / 1000.0
        if billions > max_billion_impact:
            max_billion_impact = billions

    if max_billion_impact >= 1.0:
        # A $1B+ event gets +3.5 up to +6.5 for $6B+ events
        score += 3.5 + min(3.0, max_billion_impact * 0.48)
    elif max_billion_impact >= 0.1:
        score += 1.2

    # 2. Breaking Crisis, Major Security Breach, Geopolitical or Historic Scale
    high_impact_terms = {
        "hack", "hackers", "hacked", "steal", "stolen", "theft", "heist",
        "suspends withdrawals", "breach", "emergency", "fbi", "north korea",
        "sanctions", "indictment", "supreme court", "central bank", "record",
        "historic", "largest", "unprecedented", "outage", "halt",
    }
    matched_high = sum(1 for term in high_impact_terms if term in text)
    if matched_high > 0:
        score += min(3.2, matched_high * 0.9)

    # 3. Landmark Scientific / Engineering Milestones
    milestone_terms = {
        "breakthrough", "phase ii", "phase iii", "terabit", "gigawatt",
        "surpass", "first-ever", "commercial service", "mandatory",
    }
    matched_milestone = sum(1 for term in milestone_terms if term in text)
    if matched_milestone > 0:
        score += min(1.5, matched_milestone * 0.5)

    # 4. Routine Product / Marketing Launch Dampener (unless accompanied by billion-dollar scale)
    routine_launch_terms = {"launches", "unveils", "introduces", "announces new", "product update"}
    if max_billion_impact < 1.0 and any(term in text for term in routine_launch_terms):
        score -= 0.8

    # 5. Most-Mentioned News & Multi-Source Convergence bonus (Decision #15)
    mention_count = max(int(getattr(story, "mention_count", 1)), len(story.sources))
    if mention_count > 1:
        score += min(4.8, (mention_count - 1) * 0.85)

    # 6. Recency check: penalize stale stories (>14 days older than the edition's newest story)
    if reference_date and story.sources:
        pub_str = (story.sources[0].published_date or "")[:10]
        try:
            ref_dt = datetime.strptime(reference_date[:10], "%Y-%m-%d")
            pub_dt = datetime.strptime(pub_str, "%Y-%m-%d")
            age_days = (ref_dt - pub_dt).days
            if age_days > 14:
                score -= min(4.5, 2.0 + (age_days / 15.0))
            elif age_days <= 1:
                score += 0.5
        except Exception:
            pass

    return round(score, 3)


class EditorInChiefAgent:
    """
    Stage 2: Editor Agent (ADK LlmAgent with Editorial Magnitude Ranking, Centrepiece Lead Selection,
    deterministic slot packing & reserve assignment)
    (Spec FR-016, FR-018, FR-019, FR-022).
    First determines which candidate story across all topics is the Main News Centrepiece,
    ranks deduplicated candidates across topics, fills the format's declarative page/slot manifest,
    guarantees exactly 1 outside-topics story on Daily & Weekly (0 on Bulletin),
    and attaches reserve candidates for fallback substitution.
    """

    def __init__(self, format_resolver: FormatResolver | None = None) -> None:
        self.format_resolver = format_resolver or FormatResolver()
        self.llm_client = get_muse_model(temperature=0.1)

    async def build_edition_manifest(
        self,
        edition_number: int,
        reader: ReaderProfile,
        pool: CandidatePool,
    ) -> EditionManifest:
        story_counts = {t: len(cands) for t, cands in pool.candidates_by_topic.items()}
        pages_blueprint, notices = self.format_resolver.build_page_and_slot_blueprint(
            format_name=pool.format_name,
            topics=reader.topics,
            story_counts_by_topic=story_counts,
        )

        # Find newest publication date in the pool as recency reference
        all_dates = [
            (c.sources[0].published_date or "")[:10]
            for cands in pool.candidates_by_topic.values()
            for c in cands
            if c.sources and c.sources[0].published_date
        ]
        newest_date = max(all_dates) if all_dates else None

        # Score and sort each topic's candidates by editorial newsworthiness descending
        scored_by_topic: Dict[str, List[CandidateStory]] = {}
        all_regular: List[CandidateStory] = []
        for t in reader.topics:
            topic_cands = [
                c.model_copy(update={"relevance_score": score_editorial_newsworthiness(c, newest_date)})
                for c in pool.candidates_by_topic.get(t, [])
            ]
            topic_cands.sort(key=lambda c: c.relevance_score, reverse=True)
            scored_by_topic[t] = topic_cands
            all_regular.extend(topic_cands)

        # Global ranking across all topics: highest editorial impact & magnitude first
        all_regular.sort(key=lambda c: c.relevance_score, reverse=True)

        # Optional LLM Editor-in-Chief consultation when live API key is active,
        # guarded by deterministic magnitude supremacy (a $1B+ crisis/hack never loses to a minor launch)
        main_news_lead = await self._select_main_news_centrepiece(all_regular)

        used_candidate_ids: set[str] = set()
        used_fingerprints: set[str] = set()
        used_outside_ids: set[str] = set()
        topics_represented_on_p1: set[str] = set()

        def _is_unused(c: CandidateStory) -> bool:
            return c.candidate_id not in used_candidate_ids and c.story_fingerprint not in used_fingerprints

        def _mark_used(c: CandidateStory, is_page_one: bool = False) -> None:
            used_candidate_ids.add(c.candidate_id)
            used_fingerprints.add(c.story_fingerprint)
            if is_page_one:
                topics_represented_on_p1.add(c.topic)

        def _pick_for_topic(preferred_topic: str, is_page_one: bool = False) -> CandidateStory | None:
            # If on Page 1 and preferred_topic was already represented by the Main News lead,
            # check if another active reader topic has not yet been represented on Page 1
            if is_page_one and preferred_topic in topics_represented_on_p1:
                unrepresented = [
                    t for t in reader.topics
                    if t not in topics_represented_on_p1
                    and any(_is_unused(c) for c in scored_by_topic.get(t, []))
                ]
                if unrepresented:
                    # Pick the unrepresented topic whose top unused story has the highest editorial score
                    unrepresented.sort(
                        key=lambda t: next(
                            (c.relevance_score for c in scored_by_topic.get(t, []) if _is_unused(c)),
                            0.0,
                        ),
                        reverse=True,
                    )
                    preferred_topic = unrepresented[0]

            # 1. Try highest-ranked unused story from preferred_topic
            for c in scored_by_topic.get(preferred_topic, []):
                if _is_unused(c):
                    _mark_used(c, is_page_one)
                    return c
            # 2. Try highest-ranked unused story from any topic
            for c in all_regular:
                if _is_unused(c):
                    _mark_used(c, is_page_one)
                    return c
            # 3. If fewer unique candidates exist than slots (Decision #13: NEVER clone or repeat a headline!),
            # pull an unused verified dispatch from CURATED_TOPIC_DISPATCHES so every slot has a 100% unique story.
            from app.models.schemas import SourceDocument
            from app.services.search_web import CURATED_TOPIC_DISPATCHES, compute_story_fingerprint

            for bucket in CURATED_TOPIC_DISPATCHES:
                for raw in bucket["stories"]:
                    fp = compute_story_fingerprint(raw["headline"], preferred_topic)
                    if fp not in used_fingerprints:
                        extra_cand = CandidateStory(
                            candidate_id=f"cand_extra_{fp[:10]}",
                            topic=preferred_topic,
                            headline=raw["headline"],
                            summary=raw["summary"],
                            relevance_score=8.7,
                            mention_count=int(raw.get("mention_count", 2)),
                            story_fingerprint=fp,
                            sources=[
                                SourceDocument(
                                    source_id="S1",
                                    source_name=raw["source_name"],
                                    url=raw["url"],
                                    published_date=raw["published_date"],
                                    verbatim_text=raw["verbatim_text"],
                                )
                            ],
                        )
                        _mark_used(extra_cand, is_page_one)
                        return extra_cand
            return None

        def _pick_outside() -> CandidateStory | None:
            for c in pool.outside_candidates:
                if c.candidate_id not in used_outside_ids:
                    used_outside_ids.add(c.candidate_id)
                    return c
            return None

        slot_assignments: List[SlotAssignment] = []
        for page_spec in pages_blueprint:
            p_num = page_spec["page_number"]
            p_tmpl = page_spec["template"]
            p_flag = page_spec["section_flag"]

            for slot_spec in page_spec["slots"]:
                is_outside = bool(slot_spec.get("outside_topics", False))
                slot_kind = slot_spec["kind"]

                if is_outside:
                    chosen = _pick_outside()
                elif p_num == 1 and slot_kind == "lead" and main_news_lead is not None and _is_unused(main_news_lead):
                    # The #1 Most-Mentioned & Highest-Magnitude Main News story across ALL topics claims the Front-Page Centrepiece Lead slot!
                    chosen = main_news_lead
                    _mark_used(chosen, is_page_one=True)
                else:
                    chosen = _pick_for_topic(slot_spec["topic"], is_page_one=(p_num == 1))

                if chosen is None:
                    notices.append(f"Slot '{slot_spec['slot_id']}' was omitted due to insufficient verified sources.")
                    continue

                # Remaining unused candidates serve as reserve_candidates (FR-022)
                reserves = [c for c in all_regular if c.candidate_id not in used_candidate_ids][:2]
                if not reserves and pool.outside_candidates:
                    reserves = [c for c in pool.outside_candidates if c.candidate_id not in used_outside_ids][:1]

                slot_assignments.append(
                    SlotAssignment(
                        slot_id=slot_spec["slot_id"],
                        page_number=p_num,
                        page_template=p_tmpl,
                        section_flag=p_flag,
                        slot_kind=slot_kind,
                        illustrated=bool(slot_spec.get("illustrated", False)),
                        outside_topics=is_outside,
                        topic=chosen.topic if (is_outside or p_num == 1) else slot_spec["topic"],
                        assigned_candidate=chosen,
                        reserve_candidates=reserves,
                    )
                )

        fmt_spec = self.format_resolver.get_format_spec(pool.format_name)
        return EditionManifest(
            edition_number=edition_number,
            format_name=pool.format_name,
            format_label=fmt_spec["label"],
            design_version="1.0.0",
            reader_snapshot=reader,
            story_window_start=pool.story_window_start,
            story_window_end=pool.story_window_end,
            total_pages=len(pages_blueprint),
            slot_assignments=slot_assignments,
            omitted_topics_notices=notices,
        )

    async def _select_main_news_centrepiece(self, ranked_candidates: List[CandidateStory]) -> CandidateStory | None:
        """
        Determines which story across all topics deserves the Page 1 Centrepiece Lead slot.
        Uses deterministic magnitude scoring first, and if top candidates are close in score
        and live LLM is available, consults the Editor LLM.
        """
        if not ranked_candidates:
            return None
        top_cand = ranked_candidates[0]
        if len(ranked_candidates) == 1:
            return top_cand

        second_cand = ranked_candidates[1]
        # If top candidate has a clear magnitude lead (>= 1.5 points, e.g. $6.3B hack vs routine news),
        # lock it in immediately so a major event never loses the centre page.
        if (top_cand.relevance_score - second_cand.relevance_score) >= 1.5:
            return top_cand

        if settings.has_live_api_key and settings.DEMO_CACHE_MODE != "always":
            try:
                shortlist = ranked_candidates[:5]
                lines = [
                    f"- id={c.candidate_id} | topic={c.topic} | date={c.sources[0].published_date if c.sources else 'unknown'} | score={c.relevance_score} | headline={c.headline}"
                    for c in shortlist
                ]
                decision = await self.llm_client.complete_json(
                    system_prompt=(
                        "You are the Editor-in-Chief of 'Your Daily Muse'. Evaluate the candidate stories "
                        "and select the single most important Main News story for the Front-Page Centrepiece Lead. "
                        "Prioritize multi-billion-dollar events, major cyber heists/crises, landmark scientific breakthroughs, "
                        "and breaking recency over routine product announcements. Reply in JSON."
                    ),
                    user_prompt="Candidates:\n" + "\n".join(lines),
                    response_schema=EditorialLeadDecision,
                    fallback_factory=lambda: EditorialLeadDecision(main_lead_candidate_id=top_cand.candidate_id),
                )
                if decision and decision.main_lead_candidate_id:
                    chosen = next((c for c in shortlist if c.candidate_id == decision.main_lead_candidate_id), None)
                    if chosen is not None:
                        return chosen
            except Exception:
                pass

        return top_cand
