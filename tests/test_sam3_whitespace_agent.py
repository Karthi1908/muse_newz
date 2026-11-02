from __future__ import annotations
import pytest
from datetime import datetime, timezone
from pathlib import Path
from app.agents.whitespace_agent import WhitespaceCreativeAgent
from app.models.schemas import WhitespaceRegion
from app.services.runner import EditionPipelineRunner
from app.services.sam_layout_analyzer import (
    SamLayoutAnalyzer,
    classify_whitespace_tier,
    compute_grid_fallback_regions,
)
from app.services.storage import StorageService


def test_classify_whitespace_tier_rules():
    """Verifies size tier classification thresholds (FR-040)."""
    # Compact: < 220px height
    assert classify_whitespace_tier(width=360, height=180, column_span=4, area_ratio=0.1) == "compact"
    assert classify_whitespace_tier(width=150, height=280, column_span=2, area_ratio=0.08) == "compact"

    # Banner: >= 8 columns or wide aspect ratio >= 2.1 with width >= 500
    assert classify_whitespace_tier(width=1120, height=240, column_span=12, area_ratio=0.18) == "banner"
    assert classify_whitespace_tier(width=800, height=300, column_span=8, area_ratio=0.16) == "banner"

    # Column: standard 4-column broadsheet slot
    assert classify_whitespace_tier(width=380, height=480, column_span=4, area_ratio=0.16) == "column"


def test_grid_fallback_regions_coverage():
    """Verifies deterministic grid geometry fallback returns valid regions with density guards."""
    # Front page
    front_regs = compute_grid_fallback_regions("front", 1, 5, "daily")
    assert len(front_regs) >= 1
    assert front_regs[0].size_tier == "column"
    assert front_regs[0].detection_source == "grid_fallback"
    assert front_regs[0].area_ratio >= 0.08

    # Inside page with 4 articles (4 % 3 == 1) -> 8 columns open -> 2 regions
    inside_regs_1 = compute_grid_fallback_regions("inside", 2, 4, "daily")
    assert len(inside_regs_1) == 2
    assert {r.size_tier for r in inside_regs_1} == {"column", "compact"}

    # Inside page with 3 articles (3 % 3 == 0) -> full row -> side-by-side banner + column fillers
    inside_regs_0 = compute_grid_fallback_regions("inside", 2, 3, "daily")
    assert len(inside_regs_0) == 2
    assert inside_regs_0[0].size_tier == "banner"

    # Section page -> 2 regions (column + compact) to balance feature height
    sec_regs = compute_grid_fallback_regions("section", 2, 2, "weekly")
    assert len(sec_regs) == 2
    assert sec_regs[0].size_tier == "column"

    # Closing page
    close_regs = compute_grid_fallback_regions("closing", 3, 1, "weekly")
    assert len(close_regs) >= 1
    assert close_regs[0].size_tier == "banner"


def test_sam3_response_parsing():
    """Verifies SAM-3 segmentation JSON parsing into WhitespaceRegion models."""
    analyzer = SamLayoutAnalyzer()
    mock_sam_data = {
        "regions": [
            {"bbox": [780, 500, 380, 460], "label": "blank paper whitespace"},
            {"bbox": [40, 700, 1120, 220], "label": "blank paper whitespace"},
            {"bbox": [10, 10, 50, 40], "label": "blank paper whitespace"},  # tiny sliver, should be filtered by 8% guard
        ]
    }
    parsed = analyzer._parse_sam_response(mock_sam_data, page_number=1)
    assert len(parsed) == 2, f"Expected 2 regions after density guard, got {len(parsed)}"
    assert parsed[0].size_tier == "column"
    assert parsed[0].detection_source == "sam-3"
    assert parsed[1].size_tier == "banner"
    assert parsed[1].detection_source == "sam-3"


@pytest.mark.asyncio
async def test_whitespace_creative_agent_balanced_allocation():
    """
    Verifies Balanced Cadence-Aware Allocation policy (Decision #10):
    - Front/Section pages prioritize satirical comic jokes in the primary slot and pair with house ads & wit.
    - Inside/Closing pages prioritize 'The Muse Newz' ads or epigram wit.
    """
    agent = WhitespaceCreativeAgent()
    topics = ["Quantum Computing", "Clean Tech Batteries"]
    used: set[str] = set()

    # Front page -> primary filler is comic joke, plus left-wing ad and right-wing wit
    front_regs = compute_grid_fallback_regions("front", 1, 5, "daily")
    front_fillers = await agent.create_fillers_for_page(1, "front", front_regs, topics, used)
    assert len(front_fillers) == 3
    assert front_fillers[0].filler_type == "comic_joke"
    assert "THE MECHANICAL MUSE" in front_fillers[0].title
    assert front_fillers[0].image_data_uri is not None and front_fillers[0].image_data_uri.startswith("data:image/png;base64,")
    assert front_fillers[1].filler_type == "muse_brief_ad"
    assert front_fillers[2].filler_type == "epigram_wit"

    # Closing page -> The Muse Newz house ad
    close_regs = compute_grid_fallback_regions("closing", 3, 1, "weekly")
    close_fillers = await agent.create_fillers_for_page(3, "closing", close_regs, topics, used)
    assert len(close_fillers) == 1
    assert close_fillers[0].filler_type == "muse_brief_ad"
    assert "THE MUSE NEWZ" in close_fillers[0].title
    assert close_fillers[0].image_data_uri is not None and close_fillers[0].image_data_uri.startswith("data:image/png;base64,")

    # Verify no two adjacent fillers share identical variant keys
    assert front_fillers[0].variant_key != close_fillers[0].variant_key


@pytest.mark.asyncio
async def test_end_to_end_edition_build_with_sam3_whitespace_fillers(tmp_path: Path):
    """
    Verifies full end-to-end pipeline execution with Stage 4b (SAM-3 layout analysis)
    and Stage 4c (Whitespace Creative Agent) populating whitespace_fillers across all pages.
    """
    store = StorageService(db_path=tmp_path / "test_ws.db", editions_dir=tmp_path / "editions_ws")
    runner = EditionPipelineRunner(storage=store)
    ref_time = datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc)

    edition = await runner.execute_edition_build(
        trigger_type="manual",
        override_cadence="daily",
        now=ref_time,
    )

    assert edition.total_pages == 2
    p1 = edition.pages[0]
    p2 = edition.pages[1]

    # Verify whitespace_fillers populated on pages
    assert len(p1.whitespace_fillers) >= 1
    assert p1.whitespace_fillers[0].filler_type == "comic_joke"

    assert len(p2.whitespace_fillers) >= 1

    # Verify rendered HTML contains both comic and house ad elements
    html = Path(edition.single_file_html_path).read_text(encoding="utf-8")
    assert "newspaper-comic-box" in html
    assert "house-ad-box" in html
    assert "THE MECHANICAL MUSE" in html
    assert "THE MUSE NEWZ" in html
    assert 'data-testid="centrepiece-lead-slot"' in html
    # Every <img> tag in standalone HTML must use a self-contained data:image/... URI
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    imgs = soup.find_all("img")
    assert len(imgs) >= 4
    for img in imgs:
        assert img.get("src", "").startswith("data:image/"), f"Expected inlined data:image/ URI, got {img.get('src')[:60]}"


@pytest.mark.asyncio
async def test_editor_prioritizes_6b_hack_as_centrepiece_and_dedups_same_event():
    """
    Verifies that:
    1. Two stories about the $6.3B Binance hack across different topics ('crypto' and 'blockchain')
       are consolidated by DeduplicationService into a single multi-source candidate.
    2. EditorInChiefAgent evaluates editorial magnitude first so the $6.3B Binance hack beats a routine
       product launch ('CrowdStrike launches cyber frontier AI models') for the Page 1 Centrepiece Lead slot,
       even when 'Frontier AI & Agentic Systems' is listed first in reader.topics.
    """
    from datetime import timedelta
    from app.agents.editor import EditorInChiefAgent
    from app.models.schemas import CandidatePool, CandidateStory, ReaderProfile, SourceDocument
    from app.services.dedup import DeduplicationService
    from app.services.search_web import compute_story_fingerprint

    now = datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc)
    routine_ai = CandidateStory(
        candidate_id="cand_ai_1",
        topic="Frontier AI & Agentic Systems",
        headline="CrowdStrike launches cyber frontier AI models, agentic security system",
        summary="CrowdStrike announced new frontier AI models and an agentic security system on 2025-09-01.",
        relevance_score=9.1,
        story_fingerprint=compute_story_fingerprint("CrowdStrike launches cyber frontier AI models"),
        sources=[
            SourceDocument(
                source_id="S1",
                source_name="CyberScoop",
                url="https://example.org/crowdstrike-ai-models",
                published_date="2025-09-01",
                verbatim_text="Reported by CyberScoop on 2025-09-01: CrowdStrike launches cyber frontier AI models, agentic security system for enterprise SOC teams." * 3,
            )
        ],
    )
    binance_hack_1 = CandidateStory(
        candidate_id="cand_crypto_1",
        topic="crypto",
        headline="Binance Suspends Withdrawals After Crypto Hackers Steal $6.3 Billion",
        summary="Binance suspended withdrawals after hackers stole $6.3 billion, the largest crypto heist in history.",
        relevance_score=9.1,
        story_fingerprint=compute_story_fingerprint("Binance Suspends Withdrawals After Crypto Hackers Steal $6.3 Billion"),
        sources=[
            SourceDocument(
                source_id="S1",
                source_name="The New York Times",
                url="https://example.org/nytimes-binance-6b-hack",
                published_date="2026-10-30",
                verbatim_text="Reported by The New York Times on 2026-10-30: Binance Suspends Withdrawals After Crypto Hackers Steal $6.3 Billion in biggest digital heist." * 3,
            )
        ],
    )
    binance_hack_dup = CandidateStory(
        candidate_id="cand_chain_1",
        topic="blockchain",
        headline="TRM Labs Reports Alleged $6.36B Binance Theft Tied to North Korea",
        summary="TRM Labs attributed the $6.36B Binance theft to North Korean state hackers.",
        relevance_score=9.1,
        story_fingerprint=compute_story_fingerprint("TRM Labs Reports Alleged $6.36B Binance Theft Tied to North Korea"),
        sources=[
            SourceDocument(
                source_id="S1",
                source_name="CoinDesk",
                url="https://example.org/coindesk-trm-labs-binance-6-36b",
                published_date="2026-10-30",
                verbatim_text="Reported by CoinDesk on 2026-10-30: TRM Labs Reports Alleged $6.36B Binance Theft Tied to North Korea." * 3,
            )
        ],
    )

    pool = CandidatePool(
        format_name="daily",
        story_window_start=now - timedelta(hours=26),
        story_window_end=now,
        candidates_by_topic={
            "Frontier AI & Agentic Systems": [routine_ai],
            "crypto": [binance_hack_1],
            "blockchain": [binance_hack_dup],
        },
    )

    dedup = DeduplicationService()
    filtered_pool, dropped = dedup.filter_candidate_pool(pool, recent_records=[], allow_weekly_follow_ups=False)

    # 1. Verify duplicate Binance hack story was collapsed and its source merged into binance_hack_1
    assert len(filtered_pool.candidates_by_topic["blockchain"]) == 0
    assert len(filtered_pool.candidates_by_topic["crypto"]) == 1
    consolidated_binance = filtered_pool.candidates_by_topic["crypto"][0]
    assert len(consolidated_binance.sources) == 2

    # 2. Verify EditorInChiefAgent assigns the $6.3B Binance hack to the Page 1 Lead / Centrepiece slot ('p1_lead')
    editor = EditorInChiefAgent()
    reader = ReaderProfile(
        reader_name="Alex Rivera",
        topics=["Frontier AI & Agentic Systems", "crypto", "blockchain"],
    )
    manifest = await editor.build_edition_manifest(edition_number=6, reader=reader, pool=filtered_pool)
    lead_slot = next(s for s in manifest.slot_assignments if s.slot_id == "p1_lead")
    assert "6.3 Billion" in lead_slot.assigned_candidate.headline
    assert lead_slot.topic == "crypto"


@pytest.mark.asyncio
async def test_geographic_preference_parsing_and_persistence(tmp_path: Path):
    """
    Verifies Decision #16 (FR-048):
    1. TopicEditorAgent parses geographic preference commands alongside topic changes.
    2. StorageService persists geographic_preference in SQLite.
    """
    from app.agents.topic_agent import TopicEditorAgent
    from app.models.schemas import ReaderProfile

    agent = TopicEditorAgent()
    proposal = await agent.propose_topic_change(
        current_topics=["Frontier AI & Agentic Systems", "Clean Energy"],
        user_command="add Fintech; set region to Europe & United Kingdom",
        current_geographic_preference="Global",
    )
    assert "Fintech" in proposal.proposed_topics
    assert proposal.proposed_geographic_preference == "Europe & United Kingdom"

    store = StorageService(db_path=tmp_path / "geo.db", editions_dir=tmp_path / "ed_geo")
    saved = store.save_reader_profile(
        ReaderProfile(
            reader_name="Muse",
            topics=proposal.proposed_topics,
            geographic_preference=proposal.proposed_geographic_preference or "Global",
        )
    )
    assert saved.geographic_preference == "Europe & United Kingdom"
    reloaded = store.get_reader_profile()
    assert reloaded.geographic_preference == "Europe & United Kingdom"


@pytest.mark.asyncio
async def test_zero_duplicate_news_and_images_and_horizontal_vertical_orientation(tmp_path: Path):
    """
    Verifies Decisions #13, #14, and #15 (FR-045..FR-047, SC-014..SC-016):
    - Zero duplicate headlines across all pages of an edition.
    - Zero duplicate images across all articles and comic/ad fillers.
    - Horizontal and vertical layout_orientation classes present in rendered HTML.
    """
    import hashlib
    from bs4 import BeautifulSoup
    from app.models.schemas import ReaderProfile

    store = StorageService(db_path=tmp_path / "dedup_check.db", editions_dir=tmp_path / "ed_dedup")
    runner = EditionPipelineRunner(storage=store)
    reader = ReaderProfile(
        reader_name="Muse",
        topics=["Frontier AI & Agentic Systems", "crypto", "Fintech"],
        geographic_preference="Asia-Pacific",
    )
    edition = await runner.execute_edition_build(
        trigger_type="manual",
        override_cadence="daily",
        override_reader=reader,
        now=datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc),
    )

    assert edition.geographic_preference == "Asia-Pacific"
    html = Path(edition.single_file_html_path).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    # 1. Zero duplicate headlines
    headlines = [h.get_text(strip=True).lower() for h in soup.find_all("h2", class_="article-headline")]
    assert len(headlines) == len(set(headlines)), f"Found duplicate headlines: {headlines}"

    # 2. Zero duplicate images across entire edition
    img_hashes = [hashlib.sha256(img.get("src", "").encode("utf-8")).hexdigest()[:16] for img in soup.find_all("img")]
    assert len(img_hashes) == len(set(img_hashes)), f"Found duplicate images in edition: {img_hashes}"

    # 3. Horizontal and vertical space placement classes present
    assert "layout-horizontal" in html
    assert "layout-vertical" in html
    assert "Region: Asia-Pacific" in html
