import pytest
from app.models.schemas import (
    CandidateStory,
    ClaimRecord,
    DraftIterationOutput,
    SlotAssignment,
    SourceDocument,
)
from app.services.gatekeeper import VerificationGatekeeper
from app.services.search_web import compute_story_fingerprint


def _build_test_slot(slot_kind: str = "lead", with_reserve: bool = True) -> SlotAssignment:
    src = SourceDocument(
        source_id="S1",
        source_name="Journal of Applied AI Systems",
        url="https://ai-systems.example.org/benchmark",
        published_date="2026-10-30",
        verbatim_text=(
            "A consortium of 14 distributed systems laboratories published the Autumn 2026 Benchmark on October 30, 2026. "
            "Parallel verification loops reduced unsupported factual claims from 14.6% down to 1.1% across synthesis tasks. "
            "End-to-end pipeline latency dropped by 38% compared to sequential agent chains, averaging 19.4 seconds. "
            "Deterministic post-loop gatekeepers eliminated citation laundering across all 600 audited runs."
        ),
    )
    cand = CandidateStory(
        candidate_id="cand_primary",
        topic="Frontier AI",
        headline="Parallel Verification Loops Cut Error Rates to 1.1%",
        summary="Benchmark across 600 runs shows 38% latency reduction.",
        story_fingerprint=compute_story_fingerprint("Parallel Verification Loops Cut Error Rates"),
        sources=[src],
    )
    reserves = []
    if with_reserve:
        res_src = SourceDocument(
            source_id="S1",
            source_name="Continental Tech Policy Wire",
            url="https://techpolicy.example.org/audit",
            published_date="2026-10-30",
            verbatim_text=(
                "On October 30, 2026, the European Standards Institute ratified Specification EN-4092 for AI workflows. "
                "Automated publishing systems must retain a per-claim verification record linking assertions to primary URLs. "
                "Compliance audits across 85 pilot enterprises showed that claim-level provenance increased trust by 44 points. "
                "The specification takes effect for public-sector contractors in Q2 2027."
            ),
        )
        reserves.append(
            CandidateStory(
                candidate_id="cand_reserve",
                topic="Frontier AI",
                headline="European Standards Institute Ratifies Audit Schema EN-4092",
                summary="Mandatory per-claim provenance increases trust scores across 85 enterprises.",
                story_fingerprint=compute_story_fingerprint("European Standards Institute Ratifies Audit Schema"),
                sources=[res_src],
            )
        )
    return SlotAssignment(
        slot_id="p1_lead",
        page_number=1,
        page_template="front",
        section_flag="Front Page",
        slot_kind=slot_kind,  # type: ignore[arg-type]
        illustrated=True,
        outside_topics=False,
        topic="Frontier AI",
        assigned_candidate=cand,
        reserve_candidates=reserves,
    )


def test_adversarial_poison_claim_and_fabricated_citation_stripped():
    """
    Constitution Part V Mandatory Verification Gate (Adversarial Poison Test) & FR-026:
    Injects a fabricated statistic ('999% revenue growth') and a fabricated citation ('[S99]')
    and verifies the Gatekeeper strips both, logs them in corrections_box, and preserves valid claims.
    """
    slot = _build_test_slot(slot_kind="lead")
    poisoned_draft = DraftIterationOutput(
        slot_id="p1_lead",
        iteration=2,
        headline="Parallel Verification Loops Cut Error Rates",
        deck="Benchmark study findings.",
        byline="By AI Desk",
        body_paragraphs=[
            "A consortium of 14 distributed systems laboratories published the Autumn 2026 Benchmark [S1].",
            "Parallel verification loops reduced unsupported factual claims from 14.6% down to 1.1% [S1].",
            "End-to-end pipeline latency dropped by 38% compared to sequential chains [S1].",
            "Secret internal projections claim revenue grew 999% overnight [S1].",
            "An unverified blog post also claimed quantum entanglement [S99].",
        ],
        illustration_prompt="Woodcut of server racks",
        claims=[
            ClaimRecord(
                claim_id="c1",
                claim_text="14 distributed systems laboratories published the Autumn 2026 Benchmark.",
                original_sentence="A consortium of 14 distributed systems laboratories published the Autumn 2026 Benchmark [S1].",
                verdict="verified",
                source_id="S1",
                source_url="https://ai-systems.example.org/benchmark",
            ),
            ClaimRecord(
                claim_id="c2",
                claim_text="Unsupported factual claims fell from 14.6% down to 1.1%.",
                original_sentence="Parallel verification loops reduced unsupported factual claims from 14.6% down to 1.1% [S1].",
                verdict="verified",
                source_id="S1",
                source_url="https://ai-systems.example.org/benchmark",
            ),
            ClaimRecord(
                claim_id="c3",
                claim_text="Pipeline latency dropped by 38%.",
                original_sentence="End-to-end pipeline latency dropped by 38% compared to sequential chains [S1].",
                verdict="verified",
                source_id="S1",
                source_url="https://ai-systems.example.org/benchmark",
            ),
            ClaimRecord(
                claim_id="c_poison_stat",
                claim_text="Revenue grew 999% overnight.",
                original_sentence="Secret internal projections claim revenue grew 999% overnight [S1].",
                verdict="verified",  # Even if an LLM hallucinated 'verified', deterministic sanity guard catches '999%'!
                source_id="S1",
                source_url="https://ai-systems.example.org/benchmark",
            ),
            ClaimRecord(
                claim_id="c_bad_cite",
                claim_text="Quantum entanglement reported.",
                original_sentence="An unverified blog post also claimed quantum entanglement [S99].",
                verdict="verified",
                source_id="S99",
                source_url="https://fake.example.org",
            ),
        ],
        all_supported=True,
    )

    gatekeeper = VerificationGatekeeper()
    article, corrections, passed = gatekeeper.evaluate_and_sanitize_draft(
        slot=slot,
        draft=poisoned_draft,
        sources=slot.assigned_candidate.sources,
        min_verified_claims=3,
    )

    assert passed is True
    assert article is not None
    # 3 valid claims remain verified; 2 poisoned claims were stripped and logged to corrections_box
    assert article.verified_claims_count == 3
    assert article.removed_claims_count == 2
    assert len(corrections) == 2
    body_joined = " ".join(article.body_paragraphs)
    assert "999%" not in body_joined
    assert "[S99]" not in body_joined


@pytest.mark.asyncio
async def test_minimum_verified_claims_threshold_triggers_reserve_substitution():
    """
    Clarified FR-026: Lead/Feature require >= 3 verified claims; Secondary/Brief require >= 2.
    When a Lead draft only has 2 verified claims after removals, it fails and promotes the reserve story.
    """
    slot = _build_test_slot(slot_kind="lead", with_reserve=True)
    under_threshold_draft = DraftIterationOutput(
        slot_id="p1_lead",
        iteration=2,
        headline="Under Threshold Draft",
        deck="Only 2 claims",
        byline="By Desk",
        body_paragraphs=[
            "A consortium of 14 distributed systems laboratories published the Autumn 2026 Benchmark [S1].",
            "Pipeline latency dropped by 38% [S1].",
        ],
        illustration_prompt="Prompt",
        claims=[
            ClaimRecord(
                claim_id="c1",
                claim_text="14 laboratories published the Autumn 2026 Benchmark.",
                original_sentence="A consortium of 14 distributed systems laboratories published the Autumn 2026 Benchmark [S1].",
                verdict="verified",
                source_id="S1",
            ),
            ClaimRecord(
                claim_id="c2",
                claim_text="Pipeline latency dropped by 38%.",
                original_sentence="Pipeline latency dropped by 38% [S1].",
                verdict="verified",
                source_id="S1",
            ),
        ],
        all_supported=True,
    )

    gatekeeper = VerificationGatekeeper()
    # Direct check confirms 2 verified claims fails a 'lead' slot (which requires min 3)
    art_direct, _, passed_direct = gatekeeper.evaluate_and_sanitize_draft(
        slot=slot,
        draft=under_threshold_draft,
        sources=slot.assigned_candidate.sources,
        min_verified_claims=3,
    )
    assert passed_direct is False
    assert art_direct is None

    # But 2 verified claims passes a 'brief' slot (which requires min 2)
    art_brief, _, passed_brief = gatekeeper.evaluate_and_sanitize_draft(
        slot=slot.model_copy(update={"slot_kind": "brief"}),
        draft=under_threshold_draft,
        sources=slot.assigned_candidate.sources,
        min_verified_claims=2,
    )
    assert passed_brief is True
    assert art_brief is not None
