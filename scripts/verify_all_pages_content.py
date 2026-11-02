from __future__ import annotations
import asyncio
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.schemas import ReaderProfile
from app.services.runner import EditionPipelineRunner
from app.services.storage import StorageService
from config.settings import settings


class ContentVerificationReport:
    def __init__(self):
        self.total_pages_checked = 0
        self.total_articles_checked = 0
        self.total_fillers_checked = 0
        self.total_images_checked = 0
        self.issues: list[str] = []

    def add_issue(self, page_desc: str, problem: str):
        self.issues.append(f"[{page_desc}] {problem}")

    def print_summary(self):
        print("\n" + "=" * 70)
        print("          NEWSPAPER CONTENT & WHITESPACE VERIFICATION REPORT")
        print("=" * 70)
        print(f"Total Pages Checked:    {self.total_pages_checked}")
        print(f"Total Articles Checked: {self.total_articles_checked}")
        print(f"Total Fillers Checked:  {self.total_fillers_checked}")
        print(f"Total Images Checked:   {self.total_images_checked}")
        print("-" * 70)
        if not self.issues:
            print(">>> ALL PAGES ARE 100% CONTENT-COMPLETE! ZERO BLANK GAPS FOUND! <<<")
            print("=" * 70)
            return True
        else:
            print(f">>> FOUND {len(self.issues)} ISSUE(S): <<<")
            for iss in self.issues:
                print(f"  - {iss}")
            print("=" * 70)
            return False


def verify_page_dom(page_section: BeautifulSoup, page_num: int, total_pages: int, format_name: str, report: ContentVerificationReport):
    report.total_pages_checked += 1
    page_desc = f"{format_name.upper()} Page {page_num}/{total_pages}"

    # 1. Page template container check
    if not page_section or "newspaper-page" not in page_section.get("class", []):
        report.add_issue(page_desc, "Missing <section class='newspaper-page'> container")
        return

    # 2. Check Masthead or Running Header
    if page_num == 1:
        masthead = page_section.find("header", class_="newspaper-masthead")
        if not masthead or not masthead.get_text(strip=True):
            report.add_issue(page_desc, "Page 1 is missing masthead or masthead has no text")
    else:
        running_header = page_section.find("header", class_="newspaper-running-header")
        if not running_header or not running_header.get_text(strip=True):
            report.add_issue(page_desc, f"Page {page_num} is missing running header")

    # 3. Check Page Footer / Folio
    footer = page_section.find("footer", class_="newspaper-page-footer")
    if not footer or not footer.get_text(strip=True):
        report.add_issue(page_desc, "Missing page footer or folio text")
    else:
        ft_text = footer.get_text()
        if f"Page {page_num} of {total_pages}" not in ft_text:
            report.add_issue(page_desc, f"Folio text mismatch, expected 'Page {page_num} of {total_pages}', got: '{ft_text.strip()}'")

    # 4. Check all Grid Slots (Articles + Whitespace Fillers)
    grid_container = page_section.find("div", class_=re.compile(r"grid"))
    if not grid_container:
        report.add_issue(page_desc, "Missing page grid layout container")
        return

    grid_slots = grid_container.find_all("div", class_="grid-slot")
    if not grid_slots:
        report.add_issue(page_desc, "Grid container has 0 grid-slot elements")
        return

    for s_idx, slot in enumerate(grid_slots, start=1):
        slot_text = slot.get_text(strip=True)
        if not slot_text:
            report.add_issue(page_desc, f"Grid slot #{s_idx} is completely empty (no text or content)")
            continue

        # Is it an article?
        art_card = slot.find("article", class_="newspaper-article")
        if art_card:
            report.total_articles_checked += 1
            headline_el = art_card.find(re.compile(r"h[1-4]"), class_="article-headline")
            if not headline_el or not headline_el.get_text(strip=True):
                report.add_issue(page_desc, f"Article #{s_idx} has empty headline")
            body_div = art_card.find("div", class_="article-body")
            if not body_div:
                report.add_issue(page_desc, f"Article #{s_idx} missing .article-body container")
            else:
                body_p = body_div.find_all("p")
                if not body_p:
                    report.add_issue(page_desc, f"Article #{s_idx} has 0 body paragraphs")
                else:
                    for p_idx, bp in enumerate(body_p):
                        if len(bp.get_text(strip=True)) < 20:
                            report.add_issue(page_desc, f"Article #{s_idx} paragraph #{p_idx+1} is suspiciously short: '{bp.get_text(strip=True)}'")
            # Check source line
            source_el = art_card.find("div", class_="article-sources-line")
            if not source_el:
                report.add_issue(page_desc, f"Article #{s_idx} lacks source link footer")
            continue

        # Is it a filler? (Comic, House Ad, Curiosities)
        comic_box = slot.find("aside", class_="newspaper-comic-box")
        if comic_box:
            report.total_fillers_checked += 1
            dialogue_el = comic_box.find("p", class_="comic-dialogue")
            if not dialogue_el or len(dialogue_el.get_text(strip=True)) < 25:
                report.add_issue(page_desc, f"Comic box in slot #{s_idx} has empty or incomplete dialogue")
            title_el = comic_box.find("div", class_="comic-banner")
            if not title_el or not title_el.get_text(strip=True):
                report.add_issue(page_desc, f"Comic box in slot #{s_idx} missing comic banner title")
            continue

        house_ad = slot.find("aside", class_="house-ad-box")
        if house_ad:
            report.total_fillers_checked += 1
            title_el = house_ad.find("h3", class_="house-ad-title")
            title_text = title_el.get_text(strip=True).upper() if title_el else ""
            if not title_el or ("MUSE NEWZ" not in title_text and "MUSE BRIEF" not in title_text):
                report.add_issue(page_desc, f"House ad in slot #{s_idx} missing 'THE MUSE NEWZ' title")
            copy_el = house_ad.find("p", class_="house-ad-copy")
            if not copy_el or len(copy_el.get_text(strip=True)) < 40:
                report.add_issue(page_desc, f"House ad in slot #{s_idx} missing body copy")
            continue

        curiosities = slot.find("aside", class_="newspaper-curiosities-box")
        if curiosities:
            report.total_fillers_checked += 1
            entries = curiosities.find_all("div", class_="curiosities-entry")
            if not entries:
                report.add_issue(page_desc, f"Curiosities box in slot #{s_idx} has 0 entries")
            continue

        # If it's none of the above, check if it's an unrecognized empty slot
        report.add_issue(page_desc, f"Slot #{s_idx} contains unrecognized content: '{slot_text[:60]}...'")

    # 5. Check all images on the page (must be self-contained data:image/... URIs in standalone HTML)
    for img in page_section.find_all("img"):
        report.total_images_checked += 1
        src = img.get("src", "")
        if not src:
            report.add_issue(page_desc, f"Image tag has missing or empty src: {img}")
            continue

        if src.startswith("data:image/"):
            if len(src) < 200:
                report.add_issue(page_desc, f"Image data URI is truncated or too short: {src[:50]}")
        else:
            report.add_issue(page_desc, f"Standalone HTML image must be inlined as data:image/..., got: {src[:80]}")

        # Check alt text
        alt = img.get("alt", "")
        if not alt or len(alt.strip()) < 3:
            report.add_issue(page_desc, f"Image is missing descriptive alt text: {src[:40]}")

    # 5b. On Page 1, verify Centrepiece Lead Slot, real woodcut PNG, mention-count badge, and geographic preference
    if page_num == 1:
        geo_el = page_section.find(attrs={"data-testid": "masthead-geo-line"})
        if not geo_el or "Region:" not in geo_el.get_text():
            report.add_issue(page_desc, "Masthead is missing geographic_preference [data-testid='masthead-geo-line']")

        centrepiece = page_section.find("div", attrs={"data-testid": "centrepiece-lead-slot"})
        if not centrepiece:
            report.add_issue(page_desc, "Page 1 is missing [data-testid='centrepiece-lead-slot']")
        else:
            lead_hl = centrepiece.find("h2", class_="article-headline")
            if not lead_hl or "6.3 Billion" not in lead_hl.get_text():
                report.add_issue(
                    page_desc,
                    f"Expected $6.3B Binance hack to win Centrepiece Lead slot, got: '{lead_hl.get_text(strip=True) if lead_hl else 'None'}'",
                )
            lead_img = centrepiece.find("img", class_="article-illustration-img")
            if not lead_img or not lead_img.get("src", "").startswith("data:image/png;base64,"):
                report.add_issue(page_desc, "Centrepiece Lead must have a real woodcut PNG illustration (data:image/png;base64,...)")
            mention_badge = centrepiece.find(attrs={"data-testid": "mention-count-badge"})
            if not mention_badge or "Sources Reporting" not in mention_badge.get_text():
                report.add_issue(page_desc, "Centrepiece Lead is missing multi-source mention_count badge")

    # 6. Check for unrendered template tags or null/undefined
    raw_text = page_section.get_text()
    for bad_token in ["{{", "}}", "{%", "%}", "None", "null", "undefined"]:
        if bad_token in raw_text:
            report.add_issue(page_desc, f"Detected raw template artifact or null string: '{bad_token}' in visible page text")


async def run_end_to_end_verification():
    test_dir = Path("data/test_verification_editions")
    test_dir.mkdir(parents=True, exist_ok=True)
    db_path = test_dir / "verify.db"
    if db_path.exists():
        db_path.unlink()

    ref_time = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    custom_reader = ReaderProfile(
        reader_name="Alex Rivera",
        time_zone="UTC",
        topics=["Frontier AI & Agentic Systems", "crypto", "blockchain", "Biotech & CRISPR", "Clean Energy Grid Batteries"],
        geographic_preference="Europe & United Kingdom",
    )
    report = ContentVerificationReport()

    cadences_to_test = [("every_4h", "bulletin"), ("daily", "daily"), ("weekly", "weekly")]
    for cad, fmt in cadences_to_test:
        fmt_db = test_dir / f"verify_{fmt}.db"
        if fmt_db.exists():
            fmt_db.unlink()
        store = StorageService(db_path=fmt_db, editions_dir=test_dir / f"editions_{fmt}")
        runner = EditionPipelineRunner(storage=store)
        print(f"\n---> Building and testing end-to-end {fmt.upper()} edition (cadence={cad})...")
        edition = await runner.execute_edition_build(
            trigger_type="manual",
            override_cadence=cad,
            override_reader=custom_reader,
            now=ref_time,
        )
        print(f"Generated {fmt.upper()} Edition #{edition.edition_number} with {edition.total_pages} page(s).")
        html_content = Path(edition.single_file_html_path).read_text(encoding="utf-8")
        soup = BeautifulSoup(html_content, "html.parser")
        page_sections = soup.find_all("section", class_="newspaper-page")
        assert len(page_sections) == edition.total_pages, f"Rendered page sections ({len(page_sections)}) != edition.total_pages ({edition.total_pages})"

        # Check edition-wide zero duplicate headlines & zero duplicate images (Decision #13, SC-014)
        import hashlib
        seen_headlines: set[str] = set()
        seen_img_hashes: set[str] = set()
        for hl_el in soup.find_all("h2", class_="article-headline"):
            hl_txt = hl_el.get_text(strip=True).lower()
            if hl_txt in seen_headlines:
                report.add_issue(fmt.upper(), f"Duplicate article headline across edition: '{hl_el.get_text(strip=True)}'")
            seen_headlines.add(hl_txt)
        for img_el in soup.find_all("img"):
            src = img_el.get("src", "")
            ihash = hashlib.sha256(src.encode("utf-8")).hexdigest()[:16]
            if ihash in seen_img_hashes:
                report.add_issue(fmt.upper(), f"Duplicate image detected across edition: alt='{img_el.get('alt')}' hash={ihash}")
            seen_img_hashes.add(ihash)

        for p_idx, p_soup in enumerate(page_sections, start=1):
            verify_page_dom(p_soup, p_idx, edition.total_pages, fmt, report)

    success = report.print_summary()
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_end_to_end_verification())
