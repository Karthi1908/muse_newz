from __future__ import annotations
import base64
import hashlib
import logging
from typing import List, Optional, Set
import httpx
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


# Curated Victorian broadsheet satirical humor and house ad fallbacks (Constitution Principle 1 & 4; Decision #20, FR-053)
COMIC_TOPIC_FALLBACKS = [
    {
        "variant_key": "mechanical",
        "topic_keywords": ["ai", "agent", "agentic", "model", "llm", "neural", "compute", "software", "tech"],
        "title": "THE MECHANICAL MUSE",
        "subtitle": "NO. 42: THE TYPESETTER’S VERIFICATION DILEMMA",
        "dialogue": (
            "Editor: “Automaton, why hast thou cited nine government registers for a dispatch on tea?”\n"
            "Automaton: “Lest the Gatekeeper strike it down as unverified gossip, sir! Black tea verified; lemon was hallucinated in Stage 1.”"
        ),
        "alt_dialogues": [
            (
                "Editor: “Automaton, our parallel beat agents returned forty benchmarks before breakfast!”\n"
                "Automaton: “Aye, sir, and the Adversarial Fact-Checker pruned thirty-six boasts before the ink could dry.”"
            ),
            (
                "Sub-Editor: “Why doth the inference engine hum so loudly upon the front page?”\n"
                "Automaton: “It is cross-checking every pronoun against three primary dispatches in strict JSON, sir!”"
            ),
        ],
        "speaker": "Editor & Automaton",
        "prompt": "Classic 19th-century Victorian newspaper satirical comic illustration. Eccentric editor with monocle inspects brass steampunk automaton typesetter holding a quill pen at printing desk, woodcut engraving.",
        "motto": "★ VERITAS IN JEST · DRAWN FOR THE COURIER ★",
        "image_path": "/static/images/comics/comic_mechanical_muse.png",
    },
    {
        "variant_key": "cinema_critic",
        "topic_keywords": ["movie", "movies", "film", "films", "cinema", "theatrical", "box office", "hollywood", "bollywood", "festival", "entertainment"],
        "title": "THE MECHANICAL MUSE",
        "subtitle": "NO. 46: THE 70MM CELLULOID CRITIC & THE PROJECTIONIST",
        "dialogue": (
            "Film Critic: “Projectionist! This 70-millimeter epic boasts four thousand extras, yet zero CGI!”\n"
            "Automaton Projectionist: “Verified by the Archive Ledger, sir—every horse, chandelier, and moustache was filmed in-camera on nitro-cellulose!”"
        ),
        "alt_dialogues": [
            (
                "Theatre Manager: “Why hath the box-office queue stretched three blocks past the Opera House?”\n"
                "Film Critic: “The public craves real 70mm celluloid grain over synthetic phantoms, my dear fellow!”"
            ),
            (
                "Festival Juror: “Did the director verify the historical accuracy of that third-act duel?”\n"
                "Archivist: “To the last Sabre stroke, sir—cross-referenced with four 1950s restoration reels!”"
            ),
        ],
        "speaker": "Film Critic & Automaton Projectionist",
        "prompt": "Satirical 19th-century Punch-style broadsheet comic panel showing a monocled Victorian film critic and a clockwork automaton projectionist surrounded by 70mm celluloid film reels in a theatre projection booth, woodcut engraving.",
        "motto": "★ VERITAS IN JEST · PRACTICAL CRAFT OVER PHANTOMS ★",
        "image_path": "/static/images/comics/comic_cinema_critic.png",
    },
    {
        "variant_key": "market_oracle",
        "topic_keywords": ["finance", "financial", "bank", "banking", "market", "markets", "economy", "fintech", "treasury", "ipo", "equities", "sovereign", "bond"],
        "title": "THE MECHANICAL MUSE",
        "subtitle": "NO. 47: THE STEAM-POWERED BULL & BEAR TICKER ORACLE",
        "dialogue": (
            "Stockbroker: “Oracle, the fintech IPO book is oversubscribed six times! Shall we print ‘Unprecedented Boom’?”\n"
            "Treasury Auditor: “Not until the Basel swap ledger clears in 1.8 seconds and every covenant is footnoted, sir!”"
        ),
        "alt_dialogues": [
            (
                "Merchant Banker: “The steam ticker proclaims sovereign bond yields have settled without a single Basis-Point drift!”\n"
                "Auditor: “Because the Gatekeeper demands audited balance sheets before the bell rings, sir.”"
            ),
            (
                "Exchange Clerk: “Both the Brass Bull and the Cast-Iron Bear agree on today’s dispatch!”\n"
                "Chief Economist: “A miracle of real-time gross settlement and verified liquidity, my boy.”"
            ),
        ],
        "speaker": "Stockbroker & Treasury Auditor",
        "prompt": "Satirical 19th-century Punch-style broadsheet comic panel showing a top-hatted stockbroker consulting a steam-powered brass Bull-and-Bear ticker automaton while a stern fact-checker audits the paper tape, woodcut engraving.",
        "motto": "★ VERITAS IN JEST · AUDITED LIQUIDITY BEFORE PRINT ★",
        "image_path": "/static/images/comics/comic_market_oracle.png",
    },
    {
        "variant_key": "vault_audit",
        "topic_keywords": ["crypto", "cryptocurrency", "bitcoin", "ethereum", "solana", "blockchain", "defi", "web3", "binance", "ledger", "token", "zk"],
        "title": "THE MECHANICAL MUSE",
        "subtitle": "NO. 44: THE CRYPTOGRAPHIC VAULT & THE LEDGER CLERK",
        "dialogue": (
            "Banker: “Good heavens! The cold-storage cipher vault is empty, yet the dashboard still reports 100% uptime!”\n"
            "Auditor: “Fear not, sir—our Gatekeeper has already logged the six-billion heist and frozen four hundred wallet clusters.”"
        ),
        "alt_dialogues": [
            (
                "Custodian: “Our zero-knowledge proof verified the entire cross-border vault in 1.8 seconds without revealing a single balance!”\n"
                "Ledger Clerk: “Splendid, sir—though my brass magnifying glass still prefers a signed receipt in triplicate.”"
            ),
        ],
        "speaker": "Vault Banker & Chief Auditor",
        "prompt": "Victorian broadsheet woodcut cartoon of a top-hatted banker peering into an ornate cast-iron cryptographic vault with a magnifying glass.",
        "motto": "★ VERITAS IN JEST · PROVENANCE OVER PROMISES ★",
        "image_path": "/static/images/comics/comic_vault_audit.png",
    },
    {
        "variant_key": "trap",
        "topic_keywords": ["ai", "verification", "fact", "biotech", "health", "medicine", "science"],
        "title": "THE MECHANICAL MUSE",
        "subtitle": "NO. 43: THE HALLUCINATION NET & THE SAGE OWL",
        "dialogue": (
            "Fact-Checker: “Behold, sir! A wild speculative assertion captured in my primary-source butterfly net!”\n"
            "The Owl: “Fascinating specimen. Note how its confidence score drops from 99.8% to zero upon contact with an audit ledger.”"
        ),
        "alt_dialogues": [
            (
                "Fact-Checker: “This rumor tried to sneak past the composing room disguised as an industry consensus!”\n"
                "The Owl: “Into the Corrections Box with it—not a feather prints without a verbatim quote.”"
            ),
        ],
        "speaker": "Fact-Checker & Mechanical Owl",
        "prompt": "Satirical 19th-century editorial cartoon. Stern fact-checker with folio ledger catches winged automaton in butterfly net made of primary source citations, woodcut engraving.",
        "motto": "★ VERITAS IN JEST · ZERO CITATION LAUNDERING ★",
        "image_path": "/static/images/comics/comic_hallucination_trap.png",
    },
    {
        "variant_key": "telegraph_speed",
        "topic_keywords": ["energy", "clean", "grid", "space", "orbit", "semiconductor", "chip", "outside"],
        "title": "THE MECHANICAL MUSE",
        "subtitle": "NO. 45: THE PARALLEL BEAT REPORTERS’ RACE",
        "dialogue": (
            "Senior Sub-Editor: “Five pneumatic dispatches arrived simultaneously from the orbital, cinema, and treasury desks!”\n"
            "Typesetter: “And not a single unverified adjective survived the trip through the brass Gatekeeper, sir.”"
        ),
        "alt_dialogues": [
            (
                "Sub-Editor: “From North Sea cables to geostationary laser relays, every metric is stamped with [S1]!”\n"
                "Typesetter: “Set the lead in double-column serif, sir—the morning press waits for no rumor.”"
            ),
        ],
        "speaker": "Sub-Editor & Master Typesetter",
        "prompt": "Victorian woodcut engraving of pneumatic telegraph tubes delivering scrolls to a bustling broadsheet composing room.",
        "motto": "★ VERITAS IN JEST · PRINTED BEFORE SUNRISE ★",
        "image_path": "/static/images/comics/comic_telegraph_race.png",
    },
]

MUSE_NEWZ_AD_FALLBACKS = [
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
            "Every factual statement is anchored to cross-referenced primary documents. From world cinema archives "
            "to global central bank clearing networks, read with calm certainty. Delivered unconditionally to your chosen cadence."
        ),
        "motto": "★ VERIFICATION-FIRST · ZERO CITATION LAUNDERING ★",
        "image_path": "/static/images/ads/ad_muse_brief_press.png",
    },
]
MUSE_BRIEF_AD_FALLBACKS = MUSE_NEWZ_AD_FALLBACKS

CURIOSITIES_EPIGRAM_FALLBACKS = [
    {
        "variant_key": "parable",
        "topic_keywords": ["ai", "agent", "model", "software"],
        "title": "THE NEWSROOM DISPATCHES",
        "eyebrow": "A Compendium of Wit, Curiosities & Epigrams",
        "copy": (
            "★ THE FACT-CHECKER’S PARABLE ★: An LLM, a strict compiler, and an adversarial fact-checker walk into a public house. "
            "The LLM instantly orders four thousand pints. The compiler rejects the request for improper schema formatting. "
            "The fact-checker inspects the bar’s tax records and proves nobody entered the room at all."
        ),
        "motto": "★ DEPARTMENT OF MORAL & ALGORITHMIC PHILOSOPHY ★",
    },
    {
        "variant_key": "cinema_epigram",
        "topic_keywords": ["movie", "movies", "film", "cinema", "theatrical", "festival"],
        "title": "THE NEWSROOM DISPATCHES",
        "eyebrow": "Theatrical Wit & Cinematographic Apophthegms",
        "copy": (
            "★ THE PROJECTIONIST’S MAXIM ★: A digital spectacle may render ten thousand synthetic dragons before tea-time, "
            "yet a single splice of 70-millimeter celluloid lit by tungsten lamps commands the entire auditorium’s hush."
        ),
        "motto": "★ DEPARTMENT OF THEATRICAL & ARCHIVAL CRITICISM ★",
    },
    {
        "variant_key": "finance_epigram",
        "topic_keywords": ["finance", "financial", "bank", "market", "fintech", "treasury", "crypto"],
        "title": "THE NEWSROOM DISPATCHES",
        "eyebrow": "Exchequer Maxims & Counting-House Wit",
        "copy": (
            "★ EXCHEQUER MAXIM NO. 19 ★: In a bull market every prospectus reads like epic poetry; in a clearing audit, "
            "only real-time gross settlement and footnotes signed in ink survive the morning bell."
        ),
        "motto": "★ OBSERVATORY OF SOVEREIGN LIQUIDITY & LEDGERS ★",
    },
    {
        "variant_key": "remedy",
        "topic_keywords": ["biotech", "health", "science"],
        "title": "THE NEWSROOM DISPATCHES",
        "eyebrow": "A Compendium of Wit, Curiosities & Epigrams",
        "copy": (
            "★ DR. BABBAGE’S REMEDY ★: Patent Elixir of Algorithmic Temperance. Guaranteed to relieve sudden context drift, "
            "phantom citations, and late-night hallucination fever. Prepared fresh before sunrise."
        ),
        "motto": "★ PROPRIETARY BROADSHEET WIT & REMEDIES ★",
    },
    {
        "variant_key": "maxim",
        "topic_keywords": ["general"],
        "title": "THE NEWSROOM DISPATCHES",
        "eyebrow": "Editorial Maxims & Composing-Room Apophthegms",
        "copy": (
            "★ COMPOSING-ROOM MAXIM NO. 14 ★: A headline without a primary-source citation is merely a rumour dressed in "
            "small-caps; a correction printed in full view is the highest badge of an honest press."
        ),
        "motto": "★ STANDARDS & PROVENANCE DESK ★",
    },
    {
        "variant_key": "almanac",
        "topic_keywords": ["energy", "space", "climate"],
        "title": "THE NEWSROOM DISPATCHES",
        "eyebrow": "Meteorological & Epistemic Almanac",
        "copy": (
            "★ EPISTEMIC BAROMETER ★: High pressure across primary scientific journals; scattered speculative fog in unverified "
            "social feeds—cleared before dawn by Stage-3 Adversarial Gatekeepers."
        ),
        "motto": "★ OBSERVATORY OF VERIFIED FACTS ★",
    },
]


def select_topic_matched_comic(
    topic: str,
    used_variant_keys: Set[str],
    used_paths: Set[str] | None = None,
    edition_number: int = 1,
    page_number: int = 1,
) -> dict:
    """
    Selects the best unused comic preset matching `topic` and rotates dialogue/issue numbers
    across editions so every new edition and section page displays fresh, topic-aware humor.
    """
    t_lower = (topic or "").strip().lower()
    u_paths = used_paths if used_paths is not None else used_variant_keys

    # On Page 1 (Front Page overview), prefer general newsroom/verification comics so specialized
    # section comics (cinema_critic, market_oracle, vault_audit) remain available for Section pages.
    general_keys = {"mechanical", "trap", "telegraph_speed"}
    if page_number == 1 or "front" in t_lower:
        front_cands = [
            p for p in COMIC_TOPIC_FALLBACKS
            if p["variant_key"] in general_keys
            and p["variant_key"] not in used_variant_keys
            and p["image_path"] not in u_paths
        ]
        if front_cands:
            chosen = dict(front_cands[0])
        else:
            chosen = dict(COMIC_TOPIC_FALLBACKS[0])
    else:
        # 1. Unused comics whose topic_keywords match `topic`
        topic_matched = [
            p for p in COMIC_TOPIC_FALLBACKS
            if p["variant_key"] not in used_variant_keys
            and p["image_path"] not in u_paths
            and any(kw == t_lower or (len(kw) >= 3 and kw in t_lower) for kw in p.get("topic_keywords", []))
        ]
        if topic_matched:
            chosen = dict(topic_matched[0])
        else:
            # 2. Prefer general newsroom comics before specialized section comics
            unused_general = [
                p for p in COMIC_TOPIC_FALLBACKS
                if p["variant_key"] in general_keys
                and p["variant_key"] not in used_variant_keys
                and p["image_path"] not in u_paths
            ]
            unused_any = [
                p for p in COMIC_TOPIC_FALLBACKS
                if p["variant_key"] not in used_variant_keys and p["image_path"] not in u_paths
            ]
            pool = unused_general or unused_any or [p for p in COMIC_TOPIC_FALLBACKS if p["variant_key"] not in used_variant_keys]
            chosen = dict(pool[0] if pool else COMIC_TOPIC_FALLBACKS[(edition_number + page_number) % len(COMIC_TOPIC_FALLBACKS)])

    # Rotate dialogue across edition_number so new editions have updated jokes
    all_dialogues = [chosen["dialogue"]] + list(chosen.get("alt_dialogues", []))
    if edition_number > 1 and len(all_dialogues) > 1:
        chosen["dialogue"] = all_dialogues[(edition_number + page_number) % len(all_dialogues)]
    issue_no = 40 + ((edition_number or 1) * 2) + page_number
    base_sub = chosen["subtitle"].split(":", 1)[-1].strip() if ":" in chosen["subtitle"] else chosen["subtitle"]
    chosen["subtitle"] = f"NO. {issue_no}: {base_sub}"
    return chosen


class WhitespaceCreativeAgent:
    """
    Google ADK LlmAgent for Intelligent Blank-Space Content Creation
    (Spec §7 FR-039..FR-044, Story 11, Clarification Decisions #9..#12).

    Rules:
    - Balanced Cadence-Aware Allocation (Decision #10):
      Front pages & Section pages -> Topic-specific satirical comic jokes.
      Inside pages & Closing pages -> "The Muse Newz" house ads or epigram wit.
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
        section_topic: str | None = None,
        edition_number: int = 1,
        page_headlines: List[str] | None = None,
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
                section_topic=section_topic,
                edition_number=edition_number,
                page_headlines=page_headlines,
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
        section_topic: str | None = None,
        edition_number: int = 1,
        page_headlines: List[str] | None = None,
    ) -> WhitespaceFillerItem:
        # Decision #10: Balanced Cadence-Aware Allocation Policy
        # First primary slot on front/section/inside gets a satirical comic strip;
        # Second column/banner slot on the same page gets a 'The Muse Newz' house ad;
        # Compact slots get Newsroom Curiosities & Wit epigrams.
        prefer_comic = (
            slot_index == 0
            and page_template in ("front", "section", "inside")
            and region.size_tier in ("column", "banner")
        )
        if section_topic:
            target_topic = section_topic
        elif edition_topics:
            target_topic = edition_topics[(page_number - 1 + slot_index) % len(edition_topics)]
        else:
            target_topic = "Modern Technology"

        if region.size_tier == "compact":
            return self._create_epigram_wit(page_number, region, used_variant_keys, topic=target_topic)
        elif prefer_comic:
            return await self._create_comic_joke(
                page_number,
                region,
                target_topic,
                used_variant_keys,
                edition_number=edition_number,
                page_headlines=page_headlines,
            )
        else:
            return self._create_muse_brief_ad(page_number, region, used_variant_keys)

    async def _create_comic_joke(
        self,
        page_number: int,
        region: WhitespaceRegion,
        topic: str,
        used_variant_keys: Set[str],
        edition_number: int = 1,
        page_headlines: List[str] | None = None,
    ) -> WhitespaceFillerItem:
        preset = select_topic_matched_comic(
            topic=topic,
            used_variant_keys=used_variant_keys,
            used_paths=used_variant_keys,
            edition_number=edition_number,
            page_number=page_number,
        )
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

        # In live mode with API key, prompt Meta Muse LLM for topic-specific & headline-aware broadsheet satire
        if settings.has_live_api_key and settings.DEMO_CACHE_MODE != "always":
            headlines_ctx = f" Page headlines: {'; '.join(page_headlines[:3])}." if page_headlines else ""
            system_prompt = (
                "You are the Satirical Cartoonist & Punch-style Humorist for 'The Muse Courier' Victorian broadsheet newspaper. "
                "Write a fresh, witty, high-contrast broadsheet comic joke featuring an Editor, an Automaton typesetter, "
                "a Film Critic, a Stockbroker, or a strict Fact-Checker, directly referencing the user's news beat and headlines. Reply in valid JSON."
            )
            user_prompt = (
                f"Edition #{edition_number}, Page {page_number}. Topic: {topic}.{headlines_ctx} Space tier: {region.size_tier}. "
                f"Format: 2 lines of dialogue between 2 characters. Satirize the topic's news and fact-checking dilemmas in Victorian newspaper style."
            )
            try:
                result = await self.llm_client.complete_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=GeneratedWhitespaceFiller,
                    fallback_factory=lambda: None,
                )
                if result and result.dialogue_or_copy:
                    live_image_uri = inlined_uri
                    try:
                        headers = {
                            "Authorization": f"Bearer {settings.MODEL_API_KEY}",
                            "Content-Type": "application/json",
                        }
                        c_prompt = result.image_prompt or f"Victorian broadsheet satirical woodcut comic strip, monochrome ink: {topic} {result.comic_dialogue_speaker or ''}"
                        async with httpx.AsyncClient(timeout=settings.IMAGE_TIMEOUT_SECONDS) as c_client:
                            resp = await c_client.post(
                                settings.image_generations_url,
                                headers=headers,
                                json={"model": settings.MUSE_IMAGE_MODEL, "prompt": c_prompt},
                            )
                            if resp.status_code == 200:
                                b64 = resp.json()["data"][0].get("b64_json")
                                if b64:
                                    live_image_uri = f"data:image/png;base64,{b64}"
                    except Exception:
                        pass

                    issue_no = 40 + ((edition_number or 1) * 2) + page_number
                    return WhitespaceFillerItem(
                        filler_id=f"filler_comic_{region.region_id}",
                        region_id=region.region_id,
                        page_number=page_number,
                        filler_type="comic_joke",
                        size_tier=region.size_tier,
                        title=result.title or preset["title"],
                        subtitle_or_eyebrow=result.subtitle_or_eyebrow or f"NO. {issue_no}: {topic.upper()} & THE FACT-CHECKER",
                        dialogue_or_copy=result.dialogue_or_copy,
                        comic_dialogue_speaker=result.comic_dialogue_speaker or preset["speaker"],
                        image_prompt=result.image_prompt or preset["prompt"],
                        image_path=preset["image_path"],
                        image_data_uri=live_image_uri,
                        caption_or_motto=result.caption_or_motto or preset["motto"],
                        variant_key=preset["variant_key"],
                    )
            except Exception as e:
                logger.debug("Live comic generation error (%s), using curated topic preset", e)

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
        topic: str = "",
    ) -> WhitespaceFillerItem:
        t_lower = (topic or "").strip().lower()
        topic_matched = [
            p for p in CURIOSITIES_EPIGRAM_FALLBACKS
            if p["variant_key"] not in used_variant_keys
            and any(kw in t_lower or t_lower in kw for kw in p.get("topic_keywords", []))
        ]
        if topic_matched:
            preset = topic_matched[0]
        else:
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
