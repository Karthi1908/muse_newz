from datetime import datetime, timedelta, timezone
from app.models.schemas import CandidatePool, CandidateStory, SourceDocument
from app.services.dedup import DeduplicationService
from app.services.search_web import compute_story_fingerprint


def _make_story(cid: str, topic: str, headline: str, url: str, pub_date: str = "2026-10-30") -> CandidateStory:
    text = (
        f"Primary dispatch for {headline} published on {pub_date}. "
        "Telemetry and audit records confirm a 28% operational improvement across 14 regional test facilities "
        "with full regulatory verification and zero unbacked extrapolations in the primary filing. "
        "Independent verification panels corroborated that all performance metrics complied with international safety benchmarks."
    )
    return CandidateStory(
        candidate_id=cid,
        topic=topic,
        headline=headline,
        summary="Summary of " + headline,
        story_fingerprint=compute_story_fingerprint(headline, topic),
        sources=[
            SourceDocument(
                source_id="S1",
                source_name="Test Wire",
                url=url,
                published_date=pub_date,
                verbatim_text=text,
            )
        ],
    )


def test_intra_edition_duplicate_collapsed():
    """FR-020 & Edge Case: Two topics return the same story -> it appears once."""
    now = datetime.now(timezone.utc)
    s1 = _make_story(
        "c1",
        "AI",
        "Sodium-Iron Grid Battery Installations Surpass 18 Gigawatt-Hours",
        "https://example.org/news/sodium-battery-18gwh",
    )
    s2 = _make_story(
        "c2",
        "Clean Energy",
        "Sodium-Iron Grid Battery Installations Surpass 18 Gigawatt-Hours",
        "https://example.org/news/sodium-battery-18gwh/",
    )
    pool = CandidatePool(
        format_name="daily",
        story_window_start=now - timedelta(hours=26),
        story_window_end=now,
        candidates_by_topic={"AI": [s1], "Clean Energy": [s2]},
    )

    dedup = DeduplicationService()
    filtered, dropped = dedup.filter_candidate_pool(pool, recent_records=[], allow_weekly_follow_ups=False)
    total_remaining = sum(len(v) for v in filtered.candidates_by_topic.values())
    assert total_remaining == 1
    assert len(dropped) == 1


def test_cross_edition_no_repeat_and_weekly_followup():
    """FR-021 & Story 7: No repeats in Bulletin/Daily; Weekly allows labelled 'Follow-up' only on new development."""
    now = datetime.now(timezone.utc)
    story_old = _make_story(
        "c1",
        "AI",
        "European Standards Institute Releases Mandatory Audit Schema",
        "https://example.org/eu-audit-schema",
        pub_date="2026-10-28",
    )
    prior_records = [
        {
            "edition_number": "2",
            "format_name": "daily",
            "canonical_url": "https://example.org/eu-audit-schema",
            "story_fingerprint": story_old.story_fingerprint,
            "headline": story_old.headline,
            "published_at": "2026-10-28T10:00:00+00:00",
        }
    ]

    # 1. In Daily edition, repeat story is blocked
    daily_pool = CandidatePool(
        format_name="daily",
        story_window_start=now - timedelta(hours=26),
        story_window_end=now,
        candidates_by_topic={"AI": [story_old]},
    )
    dedup = DeduplicationService()
    filtered_daily, _ = dedup.filter_candidate_pool(daily_pool, recent_records=prior_records, allow_weekly_follow_ups=False)
    assert len(filtered_daily.candidates_by_topic["AI"]) == 0

    # 2. In Weekly edition, if there is a newer date / new development, it is permitted once and flagged is_follow_up=True
    story_followup = _make_story(
        "c2",
        "AI",
        "Follow-up: European Standards Institute Releases Mandatory Audit Schema Implementation Rules",
        "https://example.org/eu-audit-schema",
        pub_date="2026-10-30",
    )
    weekly_pool = CandidatePool(
        format_name="weekly",
        story_window_start=now - timedelta(days=7),
        story_window_end=now,
        candidates_by_topic={"AI": [story_followup]},
    )
    filtered_weekly, _ = dedup.filter_candidate_pool(weekly_pool, recent_records=prior_records, allow_weekly_follow_ups=True)
    kept = filtered_weekly.candidates_by_topic["AI"]
    assert len(kept) == 1
    assert kept[0].is_follow_up is True
