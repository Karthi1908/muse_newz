import pytest
from datetime import datetime, timezone
from pathlib import Path
from app.agents.editor import EditorInChiefAgent
from app.models.schemas import CandidatePool, CandidateStory, ReaderProfile, SourceDocument
from app.services.format_resolver import FormatResolver
from app.services.runner import EditionPipelineRunner
from app.services.search_web import (
    WebResearchService,
    get_curated_dispatches_for_topic,
    topic_matches_bucket,
)
from app.services.storage import StorageService


def test_topic_matching_and_curated_dispatches_for_movies_and_finance():
    """Verifies that topic matching accurately retrieves movie and finance dispatches."""
    assert topic_matches_bucket("Movies", ["movie", "cinema", "film"])
    assert topic_matches_bucket("Cinema & Theatrical", ["movies", "film"])
    assert topic_matches_bucket("Finance", ["banking", "market", "economy"])
    assert not topic_matches_bucket("Movies", ["energy", "battery", "grid"])
    assert not topic_matches_bucket("Finance", ["semiconductor", "lithography"])

    movie_dispatches = get_curated_dispatches_for_topic("Movies")
    assert len(movie_dispatches) >= 3
    for d in movie_dispatches:
        h_lower = d["headline"].lower()
        t_lower = d["verbatim_text"].lower()
        assert any(term in h_lower or term in t_lower for term in ("film", "cinema", "theatrical", "screen", "box office", "movie"))
        # Ensure zero clean energy or semiconductor contamination in movies
        assert "subsea interconnector" not in h_lower
        assert "sodium-iron" not in h_lower

    finance_dispatches = get_curated_dispatches_for_topic("Finance")
    assert len(finance_dispatches) >= 3
    for d in finance_dispatches:
        h_lower = d["headline"].lower()
        assert any(term in h_lower for term in ("bank", "monetary", "settlement", "heist", "crypto", "clearing", "audit"))


@pytest.mark.asyncio
async def test_editor_plan_edition_strict_topic_alignment_for_movies_section(tmp_path: Path):
    """
    Verifies that when a reader has 'Movies' in their topics, the dedicated section page
    for Movies contains strictly cinema/film/theatrical articles and NEVER misattributes
    energy or grid articles to the Movies section.
    """
    resolver = FormatResolver()
    editor = EditorInChiefAgent(format_resolver=resolver)
    reader = ReaderProfile(
        reader_name="Karthik",
        topics=["AI", "Finance", "Movies"],
        geographic_preference="India & South Asia",
    )
    research = WebResearchService()
    now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    pool = CandidatePool(
        format_name="weekly",
        story_window_start=now,
        story_window_end=now,
        candidates_by_topic={
            "AI": research._fallback_candidates_for_topic("AI", max_results=3),
            "Finance": research._fallback_candidates_for_topic("Finance", max_results=3),
            "Movies": research._fallback_candidates_for_topic("Movies", max_results=3),
        },
        outside_candidates=[],
    )

    manifest = await editor.build_edition_manifest(
        edition_number=16,
        reader=reader,
        pool=pool,
    )

    # Inspect all slot assignments
    movie_slots = [s for s in manifest.slot_assignments if "Section: Movies" in (s.section_flag or "")]
    assert len(movie_slots) >= 1

    for slot in movie_slots:
        cand = slot.assigned_candidate
        assert cand is not None
        assert cand.topic == "Movies"
        h_lower = cand.headline.lower()
        # Verify genuine movie/cinema content
        assert any(term in h_lower for term in ("film", "cinema", "theatrical", "screen", "box office", "restoration", "movie", "festival"))
        # Verify zero cross-topic contamination
        assert "subsea" not in h_lower
        assert "interconnector" not in h_lower
        assert "pumped hydro" not in h_lower
        assert "battery" not in h_lower


@pytest.mark.asyncio
async def test_end_to_end_weekly_build_with_movies_topic_produces_legitimate_movie_articles(tmp_path: Path):
    """
    Verifies that a full weekly edition build for a reader with 'Movies' produces a Movies section
    with genuine cinema/film articles, proper byline ('By Muse Newz Movies Desk'), and verified claims.
    """
    store = StorageService(db_path=tmp_path / "test_movie.db", editions_dir=tmp_path / "editions")
    reader = ReaderProfile(
        reader_name="Karthik",
        topics=["AI", "Finance", "Movies"],
        geographic_preference="India & South Asia",
    )
    store.save_reader_profile(reader)
    runner = EditionPipelineRunner(storage=store)

    edition = await runner.execute_edition_build(
        trigger_type="manual",
        override_cadence="weekly",
        override_reader=reader,
    )

    movie_page = next((pg for pg in edition.pages if pg.section_flag and "Movies" in pg.section_flag), None)
    assert movie_page is not None, "Weekly edition must have a Section: Movies page"
    assert len(movie_page.articles) >= 1

    for art in movie_page.articles:
        assert art.topic == "Movies"
        assert "Movies Desk" in art.byline
        h_lower = art.headline.lower()
        body_lower = " ".join(art.body_paragraphs).lower()
        # Must contain legitimate cinema terms
        assert any(term in h_lower or term in body_lower for term in ("film", "cinema", "theatrical", "screen", "box office", "restoration", "director", "festival", "movie"))
        # Must not contain grid/energy terms
        assert "subsea interconnector" not in h_lower
        assert "high-voltage" not in h_lower
        assert "pumped hydro" not in h_lower
