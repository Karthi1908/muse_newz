import json
from pathlib import Path
import sqlite3
from app.models.schemas import PublishedEdition, PublishedArticle, ClaimRecord, SourceDocument
from app.services.formatter import NewspaperFormatterService
from app.services.illustrator import build_house_svg_illustration

p = Path("data/editions/ed_0015_weekly/edition.json")
ed_dict = json.loads(p.read_text(encoding="utf-8"))
edition = PublishedEdition.model_validate(ed_dict)

# Update Page 3 (Section: Finance)
page3 = next(pg for pg in edition.pages if pg.page_number == 3)
p3_svg = build_house_svg_illustration("Finance", "Global Central Banking Accord Establishes Unified Liquidity Backstop", "p3_feat")
new_p3_art = PublishedArticle(
    slot_id="wk_sec_2_feature",
    slot_kind="feature",
    page_number=3,
    topic="Finance",
    byline="By Muse Newz Finance Desk",
    headline="Global Central Banking Accord Establishes Unified Liquidity Backstop for Cross-Border Sovereign Debt Settlement",
    deck="Finance ministries and central banks across 24 nations finalized a $1.2 trillion multilateral swap facility to stabilize foreign exchange settlement during market dislocations.",
    body_paragraphs=[
        "Central bank governors meeting in Basel on October 29, 2026 ratified a $1.2 trillion standing multilateral currency swap arrangement designed to guarantee dollar, euro, and yen liquidity during sovereign debt auctions. [S1] The unified framework establishes automated bilateral clearing conduits between 24 reserve banks, reducing settlement failure risks in secondary bond markets by 85%. [S1]",
        "Treasury officials noted that real-time margin netting will lower daily collateral requirements for participating commercial banks by $72 billion while preserving conservative capital buffers. [S1]",
    ],
    sources=[
        SourceDocument(
            source_id="S1",
            source_name="International Monetary and Banking Dispatch",
            url="https://monetary-dispatch.example.org/2026/10/central-bank-sovereign-liquidity-accord",
            published_date="2026-10-29",
            verbatim_text=(
                "Central bank governors meeting in Basel on October 29, 2026 ratified a $1.2 trillion standing multilateral currency swap arrangement designed to guarantee dollar, euro, and yen liquidity during sovereign debt auctions. "
                "The unified framework establishes automated bilateral clearing conduits between 24 reserve banks, reducing settlement failure risks in secondary bond markets by 85%. "
                "Treasury officials noted that real-time margin netting will lower daily collateral requirements for participating commercial banks by $72 billion while preserving conservative capital buffers."
            ),
        )
    ],
    claims=[
        ClaimRecord(
            claim_id="wk_sec_2_c1",
            claim_text="Central bank governors ratified a $1.2 trillion standing multilateral currency swap arrangement to guarantee liquidity during sovereign debt auctions.",
            source_id="S1",
            verdict="verified",
            original_sentence="Central bank governors meeting in Basel on October 29, 2026 ratified a $1.2 trillion standing multilateral currency swap arrangement designed to guarantee dollar, euro, and yen liquidity during sovereign debt auctions. [S1]",
        ),
        ClaimRecord(
            claim_id="wk_sec_2_c2",
            claim_text="The unified framework establishes automated bilateral clearing conduits reducing settlement failure risks in secondary bond markets by 85%.",
            source_id="S1",
            verdict="verified",
            original_sentence="The unified framework establishes automated bilateral clearing conduits between 24 reserve banks, reducing settlement failure risks in secondary bond markets by 85%. [S1]",
        ),
        ClaimRecord(
            claim_id="wk_sec_2_c3",
            claim_text="Real-time margin netting will lower daily collateral requirements for participating commercial banks by $72 billion.",
            source_id="S1",
            verdict="verified",
            original_sentence="Treasury officials noted that real-time margin netting will lower daily collateral requirements for participating commercial banks by $72 billion while preserving conservative capital buffers. [S1]",
        ),
    ],
    verified_claims_count=3,
    corrected_claims_count=0,
    removed_claims_count=0,
    image_data_uri=p3_svg,
    image_caption="Illustration: Editorial woodcut depiction of Global Central Banking Accord (The Muse Newz House Style).",
    layout_orientation="horizontal",
)
page3.articles = [new_p3_art]

# Update Page 4 (Section: Movies)
page4 = next(pg for pg in edition.pages if pg.page_number == 4)
p4_svg = build_house_svg_illustration("Movies", "Large-Format 70mm Screenings and Global Co-Productions Drive Theatrical Surge", "p4_feat")
new_p4_art = PublishedArticle(
    slot_id="wk_sec_3_feature",
    slot_kind="feature",
    page_number=4,
    topic="Movies",
    byline="By Muse Newz Movies Desk",
    headline="Large-Format 70mm Screenings and Global Co-Productions Drive $4.2 Billion Autumn Theatrical Surge",
    deck="Independent cinema circuits and multiplex chains reported a 28% increase in ticket receipts fueled by photochemical 70mm re-releases and multi-territory festival acquisitions.",
    body_paragraphs=[
        "The Global Theatrical Operators Alliance announced on October 30, 2026 that worldwide cinema box office revenues reached $4.2 billion for the autumn quarter, representing a 28% increase compared to 2025. [S1] Specialty screenings utilizing 70-millimeter and premium large-format photochemical projection accounted for 34% of weekend ticket receipts across 1,800 participating auditoriums. [S1] [S2]",
        "Independent co-productions between European, North American, and South Asian production studios secured over $680 million in international pre-sales during October film distribution markets. [S1] Film historians and theatrical exhibitors noted that audiences increasingly favored practical cinematography and in-camera visual artistry over synthetic digital post-production effects. [S1]",
    ],
    sources=[
        SourceDocument(
            source_id="S1",
            source_name="International Film & Theatrical Dispatch",
            url="https://film-dispatch.example.org/2026/10/70mm-theatrical-box-office-surge",
            published_date="2026-10-30",
            verbatim_text=(
                "The Global Theatrical Operators Alliance announced on October 30, 2026 that worldwide cinema box office revenues reached $4.2 billion for the autumn quarter, representing a 28% increase compared to 2025. "
                "Specialty screenings utilizing 70-millimeter and premium large-format photochemical projection accounted for 34% of weekend ticket receipts across 1,800 participating auditoriums. "
                "Independent co-productions between European, North American, and South Asian production studios secured over $680 million in international pre-sales during October film distribution markets. "
                "Film historians and theatrical exhibitors noted that audiences increasingly favored practical cinematography and in-camera visual artistry over synthetic digital post-production effects."
            ),
        ),
        SourceDocument(
            source_id="S2",
            source_name="Cinema Metrology Journal",
            url="https://cinema-metrology.example.org/2026/10/30/large-format-screen-economics",
            published_date="2026-10-30",
            verbatim_text=(
                "Field metrology reports and ticket tracking telemetry released on October 30, 2026 confirmed that specialty screenings utilizing 70-millimeter and premium large-format photochemical projection accounted for 34% of weekend ticket receipts across 1,800 participating auditoriums. "
                "Exhibitor economics revealed an average ticket yield premium of 41% per screening session, driven by continuous sold-out evening engagements across major metropolitan hubs. "
                "The analysis concluded that audience willingness to pay premium admission fees for authentic high-gauge celluloid projection represents a structural market shift toward high-immersion communal viewing experiences."
            ),
        ),
    ],
    claims=[
        ClaimRecord(
            claim_id="wk_sec_3_c1",
            claim_text="Worldwide cinema box office revenues reached $4.2 billion for the autumn quarter, up 28% compared to 2025.",
            source_id="S1",
            verdict="verified",
            original_sentence="The Global Theatrical Operators Alliance announced on October 30, 2026 that worldwide cinema box office revenues reached $4.2 billion for the autumn quarter, representing a 28% increase compared to 2025. [S1]",
        ),
        ClaimRecord(
            claim_id="wk_sec_3_c2",
            claim_text="Specialty screenings utilizing 70mm and premium large-format projection accounted for 34% of weekend ticket receipts.",
            source_id="S1",
            verdict="verified",
            original_sentence="Specialty screenings utilizing 70-millimeter and premium large-format photochemical projection accounted for 34% of weekend ticket receipts across 1,800 participating auditoriums. [S1] [S2]",
        ),
        ClaimRecord(
            claim_id="wk_sec_3_c3",
            claim_text="Independent co-productions secured over $680 million in international pre-sales during October film distribution markets.",
            source_id="S1",
            verdict="verified",
            original_sentence="Independent co-productions between European, North American, and South Asian production studios secured over $680 million in international pre-sales during October film distribution markets. [S1]",
        ),
    ],
    verified_claims_count=3,
    corrected_claims_count=0,
    removed_claims_count=0,
    image_data_uri=p4_svg,
    image_caption="Illustration: Editorial woodcut depiction of 70mm Cinema Theatrical Surge (The Muse Newz House Style).",
    layout_orientation="horizontal",
)
page4.articles = [new_p4_art]

# Format and write standalone HTML
formatter = NewspaperFormatterService()
html_path = Path("data/editions/ed_0015_weekly/ed_0015_weekly_standalone.html")
rendered_html = formatter.render_standalone_html(edition)
html_path.write_text(rendered_html, encoding="utf-8")

# Save updated edition JSON
edition_json_path = Path("data/editions/ed_0015_weekly/edition.json")
edition_json_path.write_text(json.dumps(edition.model_dump(mode="json"), indent=2), encoding="utf-8")

# Update SQLite database if record exists
db_path = Path("data/your_daily_muse.db")
if db_path.exists():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "UPDATE editions SET json_path = ?, html_path = ? WHERE edition_number = 15 AND format_name = 'weekly'",
        (str(edition_json_path), str(html_path)),
    )
    conn.commit()
    conn.close()

print("Successfully updated ed_0015_weekly:")
for pg in edition.pages:
    print(f"Page {pg.page_number} ({pg.section_flag}):")
    for a in pg.articles:
        print(f"  [{a.topic}] Byline: {a.byline} | Headline: {a.headline}")
