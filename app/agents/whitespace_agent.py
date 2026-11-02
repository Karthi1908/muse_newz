from __future__ import annotations
import base64
import hashlib
import logging
from typing import List, Optional, Set
from pydantic import BaseModel
from config.settings import settings
from app.agents.meta_model import get_muse_model
from app.models.schemas import (
    WhitespaceFillerItem,
    WhitespaceFillerType,
    WhitespaceRegion,
    WhitespaceSizeTier,
)

logger = logging.getLogger(__name__)


def _encode_static_image_data_uri(image_path: str | None) -> str | None:
    """
    Loads a /static/images/... PNG from disk and returns a self-contained
    data:image/png;base64,... URI so standalone HTML files never fail to load images.
    """
    if not image_path or not image_path.startswith("/static/"):
        return None
    full_path = settings.BASE_DIR / "app" / image_path.lstrip("/")
    if full_path.exists():
        try:
            b64 = base64.b64encode(full_path.read_bytes()).decode("ascii")
            return f"data:image/png;base64,{b64}"
        except Exception:
            return None
    return None


class GeneratedWhitespaceFiller(BaseModel):
    filler_type: WhitespaceFillerType
    title: str
    subtitle_or_eyebrow: str
    dialogue_or_copy: str
    comic_dialogue_speaker: Optional[str] = None
    image_prompt: Optional[str] = None
    caption_or_motto: Optional[str] = None


# Curated Victorian broadsheet satirical humor and house ad fallbacks (Constitution Principle 1 & 4)
COMIC_TOPIC_FALLBACKS = [
    {
        "variant_key": "mechanical",
        "title": "THE MECHANICAL MUSE",
        "subtitle": "NO. 42: THE TYPESETTER’S VERIFICATION DILEMMA",
        "dialogue": (
            "Editor: “Automaton, why hast thou cited nine government registers for a dispatch on tea?”\n"
            "Automaton: “Lest the Gatekeeper strike it down as unverified gossip, sir! Black tea verified; lemon was hallucinated in Stage 1.”"
        ),
        "speaker": "Editor & Automaton",
        "prompt": "Classic 19th-century Victorian newspaper satirical comic illustration. Eccentric editor with monocle inspects brass steampunk automaton typesetter holding a quill pen at printing desk, woodcut engraving.",
        "motto": "★ VERITAS IN JEST · DRAWN FOR THE DAILY MUSE ★",
        "image_path": "/static/images/comics/comic_mechanical_muse.png",
    },
    {
        "variant_key": "trap",
        "title": "THE MECHANICAL MUSE",
        "subtitle": "NO. 43: THE HALLUCINATION NET & THE SAGE OWL",
        "dialogue": (
            "Fact-Checker: “Behold, sir! A wild speculative assertion captured in my primary-source butterfly net!”\n"
            "The Owl: “Fascinating specimen. Note how its confidence score drops from 99.8% to zero upon contact with an audit ledger.”"
        ),
        "speaker": "Fact-Checker & Mechanical Owl",
        "prompt": "Satirical 19th-century editorial cartoon. Stern fact-checker with folio ledger catches winged automaton in butterfly net made of primary source citations, woodcut engraving.",
        "motto": "★ VERITAS IN JEST · ZERO CITATION LAUNDERING ★",
        "image_path": "/static/images/comics/comic_hallucination_trap.png",
    },
    {
        "variant_key": "vault_audit",
        "title": "THE MECHANICAL MUSE",
        "subtitle": "NO. 44: THE CRYPTOGRAPHIC VAULT & THE LEDGER CLERK",
        "dialogue": (
            "Banker: “Good heavens! The cold-storage cipher vault is empty, yet the dashboard still reports 100% uptime!”\n"
            "Auditor: “Fear not, sir—our Gatekeeper has already moved the missing six billion to the Corrections Ledger.”"
        ),
        "speaker": "Vault Banker & Chief Auditor",
        "prompt": "Victorian broadsheet woodcut cartoon of a top-hatted banker peering into an ornate cast-iron cryptographic vault with a magnifying glass.",
        "motto": "★ VERITAS IN JEST · PROVENANCE OVER PROMISES ★",
        "image_path": "/static/images/comics/comic_vault_audit.png",
    },
    {
        "variant_key": "telegraph_speed",
        "title": "THE MECHANICAL MUSE",
        "subtitle": "NO. 45: THE PARALLEL BEAT REPORTERS’ RACE",
        "dialogue": (
            "Senior Sub-Editor: “Five pneumatic dispatches arrived simultaneously from the orbital and biotech desks!”\n"
            "Typesetter: “And not a single unverified adjective survived the trip through the brass Gatekeeper, sir.”"
        ),
        "speaker": "Sub-Editor & Master Typesetter",
        "prompt": "Victorian woodcut engraving of pneumatic telegraph tubes delivering scrolls to a bustling broadsheet composing room.",
        "motto": "★ VERITAS IN JEST · PRINTED BEFORE SUNRISE ★",
        "image_path": "/static/images/comics/comic_telegraph_race.png",
    },
]

MUSE_BRIEF_AD_FALLBACKS = [
    {
        "variant_key": "owl",
        "eyebrow": "The Sovereign Fact-Checker’s Emblem",
        "title": "THE MUSE NEWZ",
        "tagline": "Audited Knowledge · Verified by Adversarial Agents",
        "copy": (
            "Every published assertion across your personal edition has been audited by autonomous adversarial "
            "fact-checkers against primary source repositories before ink meets paper. Zero hallucinated claims. "
            "Savor the day’s essential truths in three unhurried minutes."
        ),
        "motto": "★ CONSTITUTIONAL INTEGRITY · PROVENANCE PRESERVED ★",
        "image_path": "/static/images/ads/ad_muse_brief_owl.png",
    },
    {
        "variant_key": "pocket",
        "eyebrow": "Paced for the Commute & the Quiet Fireside",
        "title": "THE MUSE NEWZ",
        "tagline": "A Three-Minute Morning Ritual · Paced to Your Rhythm",
        "copy": (
            "Structured to honor human attention without endless algorithmic feeds or speculative clickbait. "
            "Configured to your exact delivery schedule, whether a brisk four-hour dispatch, a two-page daily, "
            "or a deep seven-page weekly folio."
        ),
        "motto": "★ FORMATTED FOR FOCUS · NO ENDLESS FEEDS ★",
        "image_path": "/static/images/ads/ad_muse_brief_pocket.png",
    },
    {
        "variant_key": "press",
        "eyebrow": "A Constitutional Dispatch from the Editorial Desk",
        "title": "THE MUSE NEWZ",
        "tagline": "The Morning Dispatch Edition · Est. 2026",
        "copy": (
            "Every factual statement is anchored to cross-referenced primary documents. From deep-sea biology "
            "to orbital telecommunication networks, read with calm certainty. Delivered unconditionally to your chosen cadence."
        ),
        "motto": "★ VERIFICATION-FIRST · ZERO CITATION LAUNDERING ★",
        "image_path": "/static/images/ads/ad_muse_brief_press.png",
    },
]

CURIOSITIES_EPIGRAM_FALLBACKS = [
    {
        "variant_key": "parable",
        "title": "THE NEWSROOM DISPATCHES",
        "eyebrow": "A Compendium of Wit, Curiosities & Epigrams",
        "copy": (
            "★ THE FACT-CHECKER’S PARABLE ★: An LLM, a strict compiler, and an adversarial fact-checker walk into a public house. "
            "The LLM instantly orders four thousand pints. The compiler rejects the request for improper schema formatting. "
            "The fact-checker inspects the bar’s tax records and proves nobody entered the room at all."
        ),
        "motto": "★ THE DAILY MUSE · DEPARTMENT OF MORAL PHILOSOPHY ★",
    },
    {
        "variant_key": "remedy",
        "title": "THE NEWSROOM DISPATCHES",
        "eyebrow": "A Compendium of Wit, Curiosities & Epigrams",
        "copy": (
            "★ DR. BABBAGE’S REMEDY ★: Patent Elixir of Algorithmic Temperance. Guaranteed to relieve sudden context drift, "
            "phantom citations, and late-night hallucination fever. Prepared fresh before sunrise."
        ),
        "motto": "★ THE DAILY MUSE · PROPRIETARY BROADSHEET WIT ★",
    },
    {
        "variant_key": "maxim",
        "title": "THE NEWSROOM DISPATCHES",
        "eyebrow": "Editorial Maxims & Composing-Room Apophthegms",
        "copy": (
            "★ COMPOSING-ROOM MAXIM NO. 14 ★: A headline without a primary-source citation is merely a rumour dressed in "
            "small-caps; a correction printed in full view is the highest badge of an honest press."
        ),
        "motto": "★ THE DAILY MUSE · STANDARDS & PROVENANCE DESK ★",
    },
    {
        "variant_key": "almanac",
        "title": "THE NEWSROOM DISPATCHES",
        "eyebrow": "Meteorological & Epistemic Almanac",
        "copy": (
            "★ EPISTEMIC BAROMETER ★: High pressure across primary scientific journals; scattered speculative fog in unverified "
            "social feedsCleared before dawn by Stage-3 Adversarial Gatekeepers."
        ),
        "motto": "★ THE DAILY MUSE · OBSERVATORY OF VERIFIED FACTS ★",
    },
]


class WhitespaceCreativeAgent:
    """
    Google ADK LlmAgent for Intelligent Blank-Space Content Creation
    (Spec §7 FR-039..FR-044, Story 11, Clarification Decisions #9..#12).

    Rules:
    - Balanced Cadence-Aware Allocation (Decision #10):
      Front pages & Section pages -> Topic-specific satirical comic jokes.
      Inside pages & Closing pages -> "Your Muse Brief" house ads or epigram wit.
    - Topic-Specific Satirical Commentary (Decision #12):
      Humor specifically lampoons the edition's researched topics (AI hype, clean tech, biotech, etc.).
    - Single Newspaper Identity & Escaping (Principle 4 & 6):
      All copy matches broadsheet style tokens and is safe for HTML rendering.
    - Resilience & Demo Cache Fallback (Principle 1):
      Deterministic fallback items guaranteed to fit size tiers without LLM failure.
    """

    def __init__(self) -> None:
        self.llm_client = get_muse_model(temperature=0.3)

    async def create_fillers_for_page(
        self,
        page_number: int,
        page_template: str,
        regions: List[WhitespaceRegion],
        edition_topics: List[str],
        used_variant_keys: Set[str],
    ) -> List[WhitespaceFillerItem]:
        """
        Creates context-aware, space-fitted filler items for all detected whitespace regions on a page.
        """
        fillers: List[WhitespaceFillerItem] = []
        tmpl = page_template.lower()

        for idx, region in enumerate(regions):
            filler = await self._generate_single_filler(
                page_number=page_number,
                page_template=tmpl,
                region=region,
                edition_topics=edition_topics,
                slot_index=idx,
                used_variant_keys=used_variant_keys,
            )
            if filler:
                orient = "horizontal" if (region.size_tier == "banner" or region.column_span >= 6 or region.aspect_ratio >= 1.5) else "vertical"
                filler = filler.model_copy(update={"layout_orientation": orient})
                fillers.append(filler)
                if filler.variant_key:
                    used_variant_keys.add(filler.variant_key)
                if filler.image_path:
                    used_variant_keys.add(filler.image_path)

        return fillers

    async def _generate_single_filler(
        self,
        page_number: int,
        page_template: str,
        region: WhitespaceRegion,
        edition_topics: List[str],
        slot_index: int,
        used_variant_keys: Set[str],
    ) -> WhitespaceFillerItem:
        # Decision #10: Balanced Cadence-Aware Allocation Policy
        # First primary slot on front/section/inside gets a satirical comic strip;
        # Second column/banner slot on the same page gets a 'Your Muse Brief' house ad;
        # Compact slots get Newsroom Curiosities & Wit epigrams.
        prefer_comic = (
            slot_index == 0
            and page_template in ("front", "section", "inside")
            and region.size_tier in ("column", "banner")
        )
        target_topic = edition_topics[slot_index % len(edition_topics)] if edition_topics else "Modern Technology"

        if region.size_tier == "compact":
            return self._create_epigram_wit(page_number, region, used_variant_keys)
        elif prefer_comic:
            return await self._create_comic_joke(page_number, region, target_topic, used_variant_keys)
        else:
            return self._create_muse_brief_ad(page_number, region, used_variant_keys)

    async def _create_comic_joke(
        self,
        page_number: int,
        region: WhitespaceRegion,
        topic: str,
        used_variant_keys: Set[str],
    ) -> WhitespaceFillerItem:
        # Fallback preset selector avoiding duplicate keys or image paths on the same page / edition
        available_presets = [
            p for p in COMIC_TOPIC_FALLBACKS
            if p["variant_key"] not in used_variant_keys and p["image_path"] not in used_variant_keys
        ]
        if not available_presets:
            available_presets = [p for p in COMIC_TOPIC_FALLBACKS if p["variant_key"] not in used_variant_keys]
        preset = available_presets[0] if available_presets else COMIC_TOPIC_FALLBACKS[page_number % len(COMIC_TOPIC_FALLBACKS)]
        inlined_uri = _encode_static_image_data_uri(preset["image_path"])

        fallback_item = WhitespaceFillerItem(
            filler_id=f"filler_comic_{region.region_id}",
            region_id=region.region_id,
            page_number=page_number,
            filler_type="comic_joke",
            size_tier=region.size_tier,
            title=preset["title"],
            subtitle_or_eyebrow=preset["subtitle"],
            dialogue_or_copy=preset["dialogue"],
            comic_dialogue_speaker=preset["speaker"],
            image_prompt=preset["prompt"],
            image_path=preset["image_path"],
            image_data_uri=inlined_uri,
            caption_or_motto=preset["motto"],
            variant_key=preset["variant_key"],
        )

        # In live mode with API key, prompt Meta Muse LLM for topic-specific broadsheet satire
        if settings.has_live_api_key and settings.DEMO_CACHE_MODE != "always":
            system_prompt = (
                "You are the Satirical Cartoonist & Punch-style Humorist for 'The Daily Muse' Victorian newspaper. "
                "Write a witty, high-contrast broadsheet comic joke featuring an Editor, an Automaton typesetter, "
                "or a strict Fact-Checker, directly referencing the user's news beat. Reply in valid JSON."
            )
            user_prompt = (
                f"Topic: {topic}. Space tier: {region.size_tier}. Format: 2 lines of dialogue between 2 characters. "
                f"Satirize the topic's hype or fact-checking dilemmas in Victorian newspaper style."
            )
            try:
                result = await self.llm_client.complete_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=GeneratedWhitespaceFiller,
                    fallback_factory=lambda: None,
                )
                if result and result.dialogue_or_copy:
                    return WhitespaceFillerItem(
                        filler_id=f"filler_comic_{region.region_id}",
                        region_id=region.region_id,
                        page_number=page_number,
                        filler_type="comic_joke",
                        size_tier=region.size_tier,
                        title=result.title or preset["title"],
                        subtitle_or_eyebrow=result.subtitle_or_eyebrow or f"NO. {40 + page_number}: {topic.upper()} & THE FACT-CHECKER",
                        dialogue_or_copy=result.dialogue_or_copy,
                        comic_dialogue_speaker=result.comic_dialogue_speaker or "The Editor & The Automaton",
                        image_prompt=result.image_prompt or preset["prompt"],
                        image_path=preset["image_path"],
                        image_data_uri=inlined_uri,
                        caption_or_motto=result.caption_or_motto or preset["motto"],
                        variant_key=preset["variant_key"],
                    )
            except Exception as e:
                logger.debug("Live comic generation error (%s), using curated preset", e)

        return fallback_item

    def _create_muse_brief_ad(
        self,
        page_number: int,
        region: WhitespaceRegion,
        used_variant_keys: Set[str],
    ) -> WhitespaceFillerItem:
        available_presets = [
            p for p in MUSE_BRIEF_AD_FALLBACKS
            if p["variant_key"] not in used_variant_keys and p["image_path"] not in used_variant_keys
        ]
        if not available_presets:
            available_presets = [p for p in MUSE_BRIEF_AD_FALLBACKS if p["variant_key"] not in used_variant_keys]
        preset = available_presets[0] if available_presets else MUSE_BRIEF_AD_FALLBACKS[page_number % len(MUSE_BRIEF_AD_FALLBACKS)]
        inlined_uri = _encode_static_image_data_uri(preset["image_path"])

        return WhitespaceFillerItem(
            filler_id=f"filler_ad_{region.region_id}",
            region_id=region.region_id,
            page_number=page_number,
            filler_type="muse_brief_ad",
            size_tier=region.size_tier,
            title=preset["title"],
            subtitle_or_eyebrow=preset["eyebrow"],
            dialogue_or_copy=preset["copy"],
            comic_dialogue_speaker=preset["tagline"],
            image_prompt=f"House advertisement illustration plate for The Muse Newz: {preset['tagline']}",
            image_path=preset["image_path"],
            image_data_uri=inlined_uri,
            caption_or_motto=preset["motto"],
            variant_key=preset["variant_key"],
        )

    def _create_epigram_wit(
        self,
        page_number: int,
        region: WhitespaceRegion,
        used_variant_keys: Set[str],
    ) -> WhitespaceFillerItem:
        available_presets = [p for p in CURIOSITIES_EPIGRAM_FALLBACKS if p["variant_key"] not in used_variant_keys]
        preset = available_presets[0] if available_presets else CURIOSITIES_EPIGRAM_FALLBACKS[page_number % len(CURIOSITIES_EPIGRAM_FALLBACKS)]

        return WhitespaceFillerItem(
            filler_id=f"filler_epigram_{region.region_id}",
            region_id=region.region_id,
            page_number=page_number,
            filler_type="epigram_wit",
            size_tier=region.size_tier,
            title=preset["title"],
            subtitle_or_eyebrow=preset["eyebrow"],
            dialogue_or_copy=preset["copy"],
            comic_dialogue_speaker=None,
            image_prompt=None,
            image_path=None,
            caption_or_motto=preset["motto"],
            variant_key=preset["variant_key"],
        )
