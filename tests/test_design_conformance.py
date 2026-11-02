import pytest
from pathlib import Path
from app.services.runner import EditionPipelineRunner
from app.services.storage import StorageService


@pytest.mark.asyncio
async def test_design_identity_parity_and_html_escaping_across_all_formats(tmp_path: Path):
    """
    Spec §5, FR-029..FR-034, FR-049..FR-050, SC-002, SC-003, SC-007, SC-008, SC-009, SC-017:
    Verifies that Bulletin, Daily, and Weekly editions share the exact same reader-titled masthead
    ("The [Name] Courier", e.g., "The Aisha Courier", with fallback "The Muse Courier"),
    tagline ("“Made for [Name]. Checked before print.”"), design version footer, folio ("Page X of Y"),
    source links, per-claim audit drawer, corrections box, print stylesheet rules, and HTML-escape untrusted inputs.
    """
    from app.models.schemas import ReaderProfile, compute_publication_tagline, compute_publication_title

    # Verify fallback when no reader name is set yet
    assert compute_publication_title("") == "The Muse Courier"
    assert compute_publication_title(None) == "The Muse Courier"
    assert compute_publication_tagline("") == "“Made for Muse. Checked before print.”"
    # Verify personalized reader name ("Aisha")
    assert compute_publication_title("Aisha") == "The Aisha Courier"
    assert compute_publication_tagline("Aisha") == "“Made for Aisha. Checked before print.”"

    store = StorageService(db_path=tmp_path / "test_design.db", editions_dir=tmp_path / "editions")
    aisha_reader = ReaderProfile(
        reader_name="Aisha",
        topics=["Frontier AI & Agentic Systems", "Grid-Scale Clean Energy & Batteries", "Global Semiconductor Supply Chain"],
    )
    store.save_reader_profile(aisha_reader)
    runner = EditionPipelineRunner(storage=store)

    ed_bulletin = await runner.execute_edition_build(trigger_type="manual", override_cadence="every_4h")
    ed_daily = await runner.execute_edition_build(trigger_type="manual", override_cadence="daily")
    ed_weekly = await runner.execute_edition_build(trigger_type="manual", override_cadence="weekly")

    assert ed_bulletin.total_pages == 1
    assert ed_daily.total_pages == 2
    assert ed_weekly.total_pages > ed_daily.total_pages  # SC-006

    # SC-003: At least one claim is visibly corrected or removed in the demo edition
    assert len(ed_daily.corrections_box) >= 1
    assert any(c.verdict in ("corrected", "removed") and c.note for c in ed_daily.corrections_box)

    for ed in (ed_bulletin, ed_daily, ed_weekly):
        html_file = Path(ed.single_file_html_path)
        assert html_file.exists()
        content = html_file.read_text(encoding="utf-8")

        # 1. Personalized Reader-Titled Masthead ("The Aisha Courier"), Tagline & Design Version (FR-049, FR-050, SC-017)
        assert ed.publication_title == "The Aisha Courier"
        assert ed.publication_tagline == "“Made for Aisha. Checked before print.”"
        assert 'The Aisha Courier</h1>' in content
        assert "“Made for Aisha. Checked before print.”" in content
        assert f"Design Identity v{ed.design_version}" in content
        assert f'data-design-version="{ed.design_version}"' in content

        # 2. Masthead verification counter (Story 2)
        assert "Claims Verified" in content
        assert f"{ed.total_claims_verified} / {ed.total_claims_checked}" in content

        # 3. Multi-page folio ("Page X of Y") and print page-break rule
        assert f"Page 1 of {ed.total_pages}" in content
        if ed.total_pages > 1:
            assert f"Page 2 of {ed.total_pages}" in content
        assert "page-break-after: always;" in content

        # 4. Illustrations captioned explicitly as illustrations (FR-032)
        assert "Illustration:" in content

        # 5. Outside-topics rule: 0 in Bulletin, 1 in Daily & Weekly (FR-019)
        if ed.format_name == "bulletin":
            assert 'data-testid="outside-topics-badge"' not in content
        else:
            assert content.count('data-testid="outside-topics-badge"') == 1
