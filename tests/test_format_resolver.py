from datetime import datetime, timedelta, timezone
from app.services.format_resolver import FormatResolver


def test_bulletin_and_daily_format_counts():
    resolver = FormatResolver()

    # Bulletin: every_4h and every_8h -> 1 page, 3 articles, 0 outside-topics
    for cad in ("every_4h", "every_8h"):
        fmt = resolver.cadence_to_format_name(cad)
        assert fmt == "bulletin"
        pages, notices = resolver.build_page_and_slot_blueprint(fmt, ["AI", "Energy", "Biotech"])
        assert len(pages) == 1
        slots = [s for p in pages for s in p["slots"]]
        assert len(slots) == 3
        assert sum(1 for s in slots if s.get("outside_topics")) == 0
        assertnotices_empty = len(notices) == 0
        assert assertnotices_empty

    # Daily: every_12h and daily -> 2 pages, 8 articles, 1 outside-topics
    for cad in ("every_12h", "daily"):
        fmt = resolver.cadence_to_format_name(cad)
        assert fmt == "daily"
        pages, _ = resolver.build_page_and_slot_blueprint(fmt, ["AI", "Energy", "Biotech", "Space"])
        assert len(pages) == 2
        slots = [s for p in pages for s in p["slots"]]
        assert len(slots) == 8
        assert sum(1 for s in slots if s.get("outside_topics")) == 1


def test_weekly_always_has_more_pages_than_daily_for_1_to_5_topics():
    """FR-015 & SC-006: A Weekly edition MUST always have more pages than a Daily edition for 1 to 5 topics."""
    resolver = FormatResolver()
    daily_pages, _ = resolver.build_page_and_slot_blueprint("daily", ["AI"])
    daily_page_count = len(daily_pages)
    assert daily_page_count == 2

    all_topics = ["AI", "Clean Energy", "Semiconductors", "Biotech", "Space"]
    for n in range(1, 6):
        subset = all_topics[:n]
        weekly_pages, _ = resolver.build_page_and_slot_blueprint("weekly", subset)
        assert len(weekly_pages) == n + 2  # Front + N section pages + Closing
        assert len(weekly_pages) >= 3
        assert len(weekly_pages) > daily_page_count
        slots = [s for p in weekly_pages for s in p["slots"]]
        assert len(slots) <= 16
        assert sum(1 for s in slots if s.get("outside_topics")) == 1


def test_weekly_sparse_topics_shortened_or_omitted_keeps_min_3_pages():
    """FR-016: If a topic lacks material for its section page, shorten or omit it, keep Weekly >= 3 pages, and notify reader."""
    resolver = FormatResolver()
    topics = ["AI", "Clean Energy", "Biotech"]
    # Suppose Clean Energy has 0 stories and Biotech has only 1 story
    counts = {"AI": 2, "Clean Energy": 0, "Biotech": 1}
    pages, notices = resolver.build_page_and_slot_blueprint("weekly", topics, story_counts_by_topic=counts)

    # Clean Energy omitted (1 fewer page), AI (full) + Biotech (shortened to 1 feature) -> Front + 2 section + Closing = 4 pages >= 3
    assert len(pages) == 4
    assert any("Clean Energy" in n and "omitted" in n for n in notices)
    assert any("Biotech" in n and "shortened" in n for n in notices)

    # Even if ALL topics returned 0 stories, Weekly still never drops below 3 pages
    zero_counts = {"AI": 0, "Clean Energy": 0, "Biotech": 0}
    pages_min, notices_min = resolver.build_page_and_slot_blueprint("weekly", topics, story_counts_by_topic=zero_counts)
    assert len(pages_min) >= 3
    assert len(notices_min) >= 1


def test_story_window_buffer_calculation():
    """Clarified FR-017: Window = since previous edition (or cadence length) + 2h buffer."""
    resolver = FormatResolver()
    now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    last_ed = datetime(2026, 10, 31, 8, 0, tzinfo=timezone.utc)

    start, end = resolver.compute_story_window("every_4h", last_edition_at=last_ed, now=now)
    assert end == now
    assert start == last_ed - timedelta(hours=2)
