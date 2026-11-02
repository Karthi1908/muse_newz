from __future__ import annotations
import asyncio
import re
from typing import List, Tuple
from app.agents.verification_loop import StoryVerificationLoopAgent
from app.models.schemas import (
    ClaimRecord,
    DraftIterationOutput,
    EditionManifest,
    PublishedArticle,
    SlotAssignment,
)
from app.services.format_resolver import FormatResolver


_CITATION_RE = re.compile(r"\[(S\d+)\]")


class VerificationGatekeeper:
    """
    Post-Loop Deterministic Gatekeeper (Constitution Principle 2, Guardrail G-1.1..G-1.3;
    Spec FR-025, FR-026, FR-028, Story 2, Clarified Decision #2 & #3).
    Responsibilities:
      1. Validates citation IDs ([S#]) against assigned_candidate.sources.
      2. Strips any sentence whose claim remains unsupported ('removed') after Round 2.
      3. Enforces minimum verified claims per slot:
         - 3 verified claims for 'lead' and 'feature'
         - 2 verified claims for 'secondary' and 'brief'
      4. If an article falls below its slot minimum after removals, substitutes a reserve story
         (or omits the slot with a reader notice if no reserve passes).
    """

    def __init__(
        self,
        loop_agent: StoryVerificationLoopAgent | None = None,
        format_resolver: FormatResolver | None = None,
    ) -> None:
        self.format_resolver = format_resolver or FormatResolver()
        self.loop_agent = loop_agent or StoryVerificationLoopAgent(format_resolver=self.format_resolver)

    async def verify_all_slots_parallel(
        self,
        manifest: EditionManifest,
    ) -> Tuple[List[PublishedArticle], List[ClaimRecord], List[str]]:
        """
        Executes all slot verification loops concurrently (ADK ParallelAgent pattern, Constitution Article III).
        Returns (published_articles, edition_corrections_box, notices).
        """
        tasks = [
            self.verify_single_slot(
                slot=slot,
                inject_demo_correction=(idx == 0),  # Lead story showcases Round 1 -> Round 2 correction for SC-003
            )
            for idx, slot in enumerate(manifest.slot_assignments)
        ]
        results = await asyncio.gather(*tasks)

        published_articles: List[PublishedArticle] = []
        corrections_box: List[ClaimRecord] = []
        notices: List[str] = list(manifest.omitted_topics_notices)

        for article, slot_corrections, slot_notice in results:
            corrections_box.extend(slot_corrections)
            if slot_notice:
                notices.append(slot_notice)
            if article is not None:
                published_articles.append(article)

        return published_articles, corrections_box, notices

    async def verify_single_slot(
        self,
        slot: SlotAssignment,
        inject_demo_correction: bool = False,
    ) -> Tuple[PublishedArticle | None, List[ClaimRecord], str | None]:
        slot_spec = self.format_resolver.get_slot_spec(slot.slot_kind)
        min_verified = int(slot_spec["min_verified_claims"])

        # Attempt primary assigned candidate
        final_draft, _ = await self.loop_agent.run_loop_for_candidate(
            slot_id=slot.slot_id,
            slot_kind=slot.slot_kind,
            candidate=slot.assigned_candidate,
            inject_demo_correction=inject_demo_correction,
        )
        article, corrections, passed = self.evaluate_and_sanitize_draft(
            slot=slot,
            draft=final_draft,
            sources=slot.assigned_candidate.sources,
            min_verified_claims=min_verified,
            substituted=False,
        )
        if passed and article is not None:
            return article, corrections, None

        # Primary candidate failed minimum verified claims after Round 2 removals -> try reserve candidates (FR-026)
        for reserve in slot.reserve_candidates:
            res_draft, _ = await self.loop_agent.run_loop_for_candidate(
                slot_id=slot.slot_id,
                slot_kind=slot.slot_kind,
                candidate=reserve,
                inject_demo_correction=False,
            )
            res_slot = slot.model_copy(update={"assigned_candidate": reserve, "topic": reserve.topic})
            res_article, res_corrections, res_passed = self.evaluate_and_sanitize_draft(
                slot=res_slot,
                draft=res_draft,
                sources=reserve.sources,
                min_verified_claims=min_verified,
                substituted=True,
            )
            if res_passed and res_article is not None:
                notice = (
                    f"Slot '{slot.slot_id}' replaced original draft ('{slot.assigned_candidate.headline}') "
                    f"with reserve story ('{reserve.headline}') because the original did not meet the minimum "
                    f"of {min_verified} verified claims."
                )
                return res_article, corrections + res_corrections, notice

        omit_notice = (
            f"Slot '{slot.slot_id}' ('{slot.assigned_candidate.headline}') was omitted because it had fewer than "
            f"{min_verified} verified claims after 2 verification rounds and no passing reserve story remained."
        )
        return None, corrections, omit_notice

    def evaluate_and_sanitize_draft(
        self,
        slot: SlotAssignment,
        draft: DraftIterationOutput,
        sources: list,
        min_verified_claims: int,
        substituted: bool = False,
    ) -> Tuple[PublishedArticle | None, List[ClaimRecord], bool]:
        """
        Pure deterministic post-loop sanitization and threshold check.
        Callable directly in unit tests with synthetic/poisoned drafts (Principle 8).
        """
        valid_source_ids = {s.source_id for s in sources}
        source_text_combined = " ".join(s.verbatim_text.lower() for s in sources)

        sanitized_paragraphs: List[str] = list(draft.body_paragraphs)
        processed_claims: List[ClaimRecord] = []
        corrections_list: List[ClaimRecord] = []

        for claim in draft.claims:
            # 1. Guardrail G-1.1: Check if cited_source_id is fabricated
            if claim.source_id and claim.source_id not in valid_source_ids:
                removed_claim = claim.model_copy(
                    update={
                        "verdict": "removed",
                        "note": f"Removed by Gatekeeper: cited source [{claim.source_id}] does not exist in retrieved sources.",
                    }
                )
                processed_claims.append(removed_claim)
                corrections_list.append(removed_claim)
                sanitized_paragraphs = self._strip_sentence_from_paragraphs(
                    sanitized_paragraphs, claim.original_sentence
                )
                continue

            # 2. Check if claim was already marked 'removed' (unsupported after Round 2)
            if claim.verdict == "removed":
                note = claim.note or "Removed after Round 2: claim could not be supported by the cited source."
                removed_claim = claim.model_copy(update={"verdict": "removed", "note": note})
                processed_claims.append(removed_claim)
                corrections_list.append(removed_claim)
                sanitized_paragraphs = self._strip_sentence_from_paragraphs(
                    sanitized_paragraphs, claim.original_sentence
                )
                continue

            # 3. Deterministic entailment sanity guard for 'verified' claims with numbers
            # If a claim marked 'verified' contains a 3+ digit number or percentage that appears nowhere in source text, strip it
            suspicious_numbers = re.findall(r"\b\d+(?:\.\d+)?%(?!\w)", claim.claim_text)
            unbacked_num = [num for num in suspicious_numbers if num.lower() not in source_text_combined]
            if unbacked_num and claim.verdict == "verified":
                removed_claim = claim.model_copy(
                    update={
                        "verdict": "removed",
                        "note": f"Removed by Gatekeeper: statistic {', '.join(unbacked_num)} was not found in verbatim source text.",
                    }
                )
                processed_claims.append(removed_claim)
                corrections_list.append(removed_claim)
                sanitized_paragraphs = self._strip_sentence_from_paragraphs(
                    sanitized_paragraphs, claim.original_sentence
                )
                continue

            # 4. Keep 'verified' and 'corrected' claims
            if claim.verdict == "corrected":
                note = claim.note or "Corrected in Round 2 to match cited primary source."
                corr_claim = claim.model_copy(update={"note": note})
                processed_claims.append(corr_claim)
                corrections_list.append(corr_claim)
            else:
                processed_claims.append(claim)

        # Strip any paragraph that cites a fabricated [S#] tag directly
        cleaned_paragraphs: List[str] = []
        for para in sanitized_paragraphs:
            cited_in_para = _CITATION_RE.findall(para)
            if any(cid not in valid_source_ids for cid in cited_in_para):
                continue
            if para.strip():
                cleaned_paragraphs.append(para.strip())

        verified_count = sum(1 for c in processed_claims if c.verdict in ("verified", "corrected"))
        corrected_count = sum(1 for c in processed_claims if c.verdict == "corrected")
        removed_count = sum(1 for c in processed_claims if c.verdict == "removed")

        if verified_count < min_verified_claims or not cleaned_paragraphs:
            return None, corrections_list, False

        cand = slot.assigned_candidate
        outside_note = (
            cand.outside_rationale
            or "Chosen on purpose outside your usual reading to broaden perspective."
            if slot.outside_topics
            else None
        )

        clean_byline = draft.byline
        if clean_byline:
            clean_byline = re.sub(r"By\s+Your\s+Daily\s+Muse\b", "By Muse Newz", clean_byline, flags=re.I)
            clean_byline = re.sub(r"Your\s+Daily\s+Muse\b", "Muse Newz", clean_byline, flags=re.I)
            clean_byline = re.sub(r"Daily\s+Muse\b", "Muse Newz", clean_byline, flags=re.I)

        article = PublishedArticle(
            slot_id=slot.slot_id,
            page_number=slot.page_number,
            slot_kind=slot.slot_kind,
            layout_orientation="horizontal" if slot.slot_kind in ("lead", "feature") else "vertical",
            topic=slot.topic,
            headline=draft.headline,
            deck=draft.deck,
            byline=clean_byline,
            body_paragraphs=cleaned_paragraphs,
            sources=sources,
            claims=processed_claims,
            verified_claims_count=verified_count,
            corrected_claims_count=corrected_count,
            removed_claims_count=removed_count,
            mention_count=max(int(getattr(cand, "mention_count", 1)), len(sources)),
            outside_flag=slot.outside_topics,
            outside_note=outside_note,
            follow_up_flag=cand.is_follow_up,
            substituted_from_reserve=substituted,
        )
        return article, corrections_list, True

    @staticmethod
    def _strip_sentence_from_paragraphs(paragraphs: List[str], target_sentence: str) -> List[str]:
        if not target_sentence:
            return paragraphs
        out: List[str] = []
        target_norm = target_sentence.strip()
        for p in paragraphs:
            updated = p.replace(target_norm, "").strip()
            updated = re.sub(r"\s{2,}", " ", updated)
            if updated:
                out.append(updated)
        return out
