import pytest
from datetime import datetime, timezone
from pathlib import Path
from app.models.schemas import ReaderProfile
from app.services.runner import EditionPipelineRunner
from app.services.storage import StorageService
from app.services.illustrator import _find_cached_real_image, _normalize_headline, _get_headline_cache_key
from config.settings import settings


@pytest.mark.asyncio
async def test_illustrator_deduplication_and_no_repeated_images(tmp_path: Path):
    """
    Verifies that no two illustrated articles in the same edition ever receive the same image.
    """
    store = StorageService(db_path=tmp_path / "test.db", editions_dir=tmp_path / "editions")
    runner = EditionPipelineRunner(storage=store)

    ref_time = datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc)

    edition = await runner.execute_edition_build(
        trigger_type="manual",
        override_cadence="weekly",
        now=ref_time,
    )

    assert edition.total_pages >= 3, f"Expected at least 3 pages, got {edition.total_pages}"
    illustrated_articles = [
        a for p in edition.pages for a in p.articles if a.image_path or a.image_data_uri
    ]
    assert len(illustrated_articles) >= 2, "Expected at least 2 illustrated articles in Weekly edition"

    # Verify all assigned images are distinct
    assigned_images = [a.image_path for a in illustrated_articles if a.image_path]
    unique_images = set(assigned_images)
    assert len(assigned_images) == len(unique_images), (
        f"Found duplicate images in the same edition! Images: {assigned_images}"
    )

    # Verify all image captions conform to Principle 3 (explicit illustration labeling)
    for art in illustrated_articles:
        assert "Illustration:" in art.image_caption
        assert "Your Daily Muse House Illustration Style" in art.image_caption


@pytest.mark.asyncio
async def test_house_ads_and_comics_rendered_in_blank_spaces(tmp_path: Path):
    """
    Verifies that 'The Muse Newz' house advertisements and satirical comic strips
    are placed in whitespace slots across the newspaper pages (Front, Section, Inside, Closing).
    """
    store = StorageService(db_path=tmp_path / "test_ads.db", editions_dir=tmp_path / "editions_ads")
    runner = EditionPipelineRunner(storage=store)
    ref_time = datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc)

    edition = await runner.execute_edition_build(
        trigger_type="manual",
        override_cadence="weekly",
        now=ref_time,
    )

    assert edition.single_file_html_path is not None, "HTML path must be set on edition"
    html = Path(edition.single_file_html_path).read_text(encoding="utf-8")

    assert "house-ad-box" in html, "Rendered HTML must contain house-ad-box component"
    assert "THE MUSE NEWZ" in html, "House ad must feature 'THE MUSE NEWZ' masthead"
    assert "ad_muse_brief_" in html, "House ad must reference an ad_muse_brief illustration"
    assert "newspaper-comic-box" in html, "Rendered HTML must contain satirical comic box"
    assert "THE MECHANICAL MUSE" in html, "Comic strip must feature title"


@pytest.mark.asyncio
async def test_daily_front_page_whitespace_filled_with_comic(tmp_path: Path):
    """
    Verifies that on Daily format Page 1 (underneath the briefs in the right column),
    empty space is filled with a broadsheet comic strip.
    """
    store = StorageService(db_path=tmp_path / "test_daily.db", editions_dir=tmp_path / "ed_daily")
    runner = EditionPipelineRunner(storage=store)
    ref_time = datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc)

    edition = await runner.execute_edition_build(
        trigger_type="manual",
        override_cadence="daily",
        now=ref_time,
    )

    html = Path(edition.single_file_html_path).read_text(encoding="utf-8")
    assert "newspaper-comic-box" in html, "Daily Page 1 right column must contain comic strip"
    assert "THE MECHANICAL MUSE" in html


def test_headline_normalization_and_cache_key():
    """
    Verifies headline normalization correctly strips editorial prefixes
    so analysis angles map to the same topic key without colliding.
    """
    h1 = "Open-Weights Multi-Agent Benchmarks Show 38% Latency Drop"
    h2 = "Analysis: Open-Weights Multi-Agent Benchmarks Show 38% Latency Drop"
    h3 = "Follow-up: Open-Weights Multi-Agent Benchmarks Show 38% Latency Drop"

    k1 = _get_headline_cache_key(h1)
    k2 = _get_headline_cache_key(h2)
    k3 = _get_headline_cache_key(h3)

    assert k1 == k2 == k3, "Normalized headline cache keys must match regardless of editorial prefixes"


@pytest.mark.asyncio
async def test_no_image_reused_across_consecutive_editions(tmp_path: Path):
    """
    Mandatory Freshness Rule:
    Verifies that old images from past editions are NEVER reused in subsequent editions.
    """
    store = StorageService(db_path=tmp_path / "test_fresh.db", editions_dir=tmp_path / "editions_fresh")
    runner = EditionPipelineRunner(storage=store)
    t1 = datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)

    # Build Edition 1
    ed1 = await runner.execute_edition_build(trigger_type="manual", override_cadence="every_4h", now=t1)
    imgs_ed1 = {
        a.image_path for p in ed1.pages for a in p.articles if a.image_path
    }
    data_uris_ed1 = {
        a.image_data_uri for p in ed1.pages for a in p.articles if a.image_data_uri
    }

    # Build Edition 2
    ed2 = await runner.execute_edition_build(trigger_type="manual", override_cadence="every_4h", now=t2)
    imgs_ed2 = {
        a.image_path for p in ed2.pages for a in p.articles if a.image_path
    }
    data_uris_ed2 = {
        a.image_data_uri for p in ed2.pages for a in p.articles if a.image_data_uri
    }

    # Cross-edition collision check
    overlap_paths = imgs_ed1 & imgs_ed2
    overlap_uris = data_uris_ed1 & data_uris_ed2
    assert len(overlap_paths) == 0, f"Detected image path collision across editions: {overlap_paths}"
    assert len(overlap_uris) == 0, "Detected identical image data URI across editions"
