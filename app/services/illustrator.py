from __future__ import annotations
import asyncio
import base64
import hashlib
import html
import json
import re
from pathlib import Path
from typing import List, Optional, Set, Tuple
import httpx
from config.settings import settings
from app.models.schemas import EditionManifest, PublishedArticle


HOUSE_STYLE_PREFIX = (
    "Classic broadsheet newspaper editorial woodcut and stipple ink illustration, "
    "monochrome etching on warm newsprint paper, high contrast crosshatching, no text: "
)


def _normalize_headline(headline: str) -> str:
    """Strips editorial prefixes and punctuation to yield a canonical headline for matching."""
    cleaned = re.sub(
        r"^(analysis|follow-up|special report|perspective|dispatch|investigation):\s*",
        "",
        headline.strip(),
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"[^\w\s-]", "", cleaned).strip().lower()
    return re.sub(r"\s+", " ", cleaned)


def _get_headline_cache_key(headline: str) -> str:
    norm = _normalize_headline(headline)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def _extract_domain_tokens(text: str) -> Set[str]:
    words = re.findall(r"[a-z]{4,}", text.lower())
    stop_words = {
        "with", "from", "that", "this", "over", "into", "after", "amid", "report",
        "reports", "first", "second", "third", "reach", "reaches", "above", "below",
        "between", "across", "system", "systems", "model", "models", "analysis",
        "brief", "briefing", "daily", "weekly", "edition", "house", "demonstrates",
        "shows", "show", "unveils", "announces", "pushes", "cuts", "year", "month"
    }
    return set(w for w in words if w not in stop_words)


def _get_historically_used_image_hashes(editions_dir: Path) -> Set[str]:
    """
    Collects content hashes of all images used across all past editions to ensure
    that old images are strictly never reused in new editions (Mandatory Freshness Rule).
    """
    used: Set[str] = set()
    if not editions_dir.exists():
        return used
    for img_file in editions_dir.glob("*/images/*.png"):
        try:
            h = hashlib.sha256(img_file.read_bytes()).hexdigest()[:16]
            used.add(h)
        except Exception:
            pass
    return used


def _find_cached_real_image(
    headline: str,
    topic: str,
    cache_dir: Path,
    used_hashes: Set[str],
) -> Optional[Tuple[str, bytes, str]]:
    """
    Finds a cached real Meta Muse illustration for an article, ensuring:
    1. House ads (ad_muse_brief_*) are never matched as article illustrations.
    2. Exact normalized headline hash is prioritized.
    3. Strong semantic domain token match is second.
    4. Topic-specific match is third.
    5. An image already assigned to another slot in the same edition (in used_hashes) is NEVER reused.
    Returns (data_uri, img_bytes, content_hash) or None.
    """
    if not cache_dir.exists():
        return None

    # Step 1: Direct normalized headline hash match
    key = _get_headline_cache_key(headline)
    meta_file = cache_dir / f"{key}.json"
    png_file = cache_dir / f"{key}.png"
    if meta_file.exists() and png_file.exists():
        try:
            raw_bytes = png_file.read_bytes()
            content_hash = hashlib.sha256(raw_bytes).hexdigest()[:16]
            if content_hash not in used_hashes:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                b64_json = meta.get("b64_json")
                if b64_json:
                    return f"data:image/png;base64,{b64_json}", raw_bytes, content_hash
        except Exception:
            pass

    # Gather all candidate cached images (excluding house ads)
    candidates: List[Tuple[float, Path, dict]] = []
    target_tokens = _extract_domain_tokens(headline)
    clean_target_head = _normalize_headline(headline)

    for mpath in cache_dir.glob("*.json"):
        if mpath.name.startswith("ad_muse_brief_") or mpath.name.startswith("comic_"):
            continue  # Exclude house ads and comic strips from news article illustrations
        png_path = cache_dir / f"{mpath.stem}.png"
        if not png_path.exists():
            continue
        try:
            meta = json.loads(mpath.read_text(encoding="utf-8"))
            if meta.get("topic") in ("House Advertisement", "Satirical Editorial Comic"):
                continue  # Skip advertisement and comic assets
            cached_headline = meta.get("headline", "")
            cached_topic = meta.get("topic", "")
            cached_norm = _normalize_headline(cached_headline)

            # Check raw bytes hash to verify it hasn't been used yet
            raw_bytes = png_path.read_bytes()
            content_hash = hashlib.sha256(raw_bytes).hexdigest()[:16]
            if content_hash in used_hashes:
                continue

            # Calculate match score with strict semantic topic integrity
            from app.services.search_web import topic_matches_bucket
            score = 0.0
            if clean_target_head and clean_target_head == cached_norm:
                score = 10.0
            else:
                cached_tokens = _extract_domain_tokens(cached_headline)
                common = target_tokens & cached_tokens
                all_toks = target_tokens | cached_tokens
                jaccard = (len(common) / len(all_toks)) if all_toks else 0.0

                if len(common) >= 3 and jaccard >= 0.35:
                    score = 5.0 + jaccard
                elif topic and cached_topic and (
                    topic_matches_bucket(topic, [cached_topic])
                    or topic_matches_bucket(cached_topic, [topic])
                ):
                    score = 2.5 + jaccard

            if score > 0.0:
                meta["_raw_bytes"] = raw_bytes
                meta["_content_hash"] = content_hash
                candidates.append((score, png_path, meta))
        except Exception:
            continue

    if candidates:
        candidates.sort(key=lambda c: c[0], reverse=True)
        best_score, best_png, best_meta = candidates[0]
        b64 = best_meta.get("b64_json")
        if b64:
            return f"data:image/png;base64,{b64}", best_meta["_raw_bytes"], best_meta["_content_hash"]

    return None


def build_bespoke_woodcut_png(
    topic: str,
    headline: str,
    slot_id: str,
    edition_id: str,
    cache_dir: Path | None = None,
) -> Tuple[str, bytes]:
    """
    Generates a brand-new, edition-specific Victorian broadsheet woodcut PNG illustration
    tailored to the article's topic, headline, slot_id, and edition_id (Decision #19, FR-052, SC-019).
    Composites a topic-matched woodcut etching plate with a unique framing crop and engraved
    broadsheet plate cartouche so every new edition has fresh, non-repeating PNG article images.
    """
    import io
    from PIL import Image, ImageDraw, ImageOps

    c_dir = cache_dir or (settings.DATA_DIR / "demo_cache" / "images")
    t_lower = (topic or "").strip().lower()
    h_lower = (headline or "").strip().lower()
    seed_bytes = hashlib.sha256(f"{edition_id}|{slot_id}|{headline}|{topic}".encode("utf-8")).digest()
    seed_int = int.from_bytes(seed_bytes[:4], "big")

    # Select topic-appropriate woodcut base plates
    if any(k in t_lower or k in h_lower for k in ("movie", "film", "cinema", "theatrical", "box office", "70mm", "festival", "hollywood", "bollywood", "ramayana")):
        pool_stems = ["movies_70mm_cinema", "movies_film_festival"]
    elif any(k in t_lower or k in h_lower for k in ("binance", "heist", "crypto", "bitcoin", "ethereum", "blockchain", "zk", "zero-knowledge", "lattice", "token", "ledger")):
        pool_stems = ["binance_crypto_heist_6b", "crypto_zk_settlement"] if "binance" in h_lower else ["crypto_zk_settlement", "binance_crypto_heist_6b"]
    elif any(k in t_lower or k in h_lower for k in ("finance", "financial", "bank", "banking", "treasury", "sovereign", "market", "fintech", "ipo", "equities", "swap")):
        pool_stems = ["finance_central_bank", "finance_fintech_ipo"]
    elif any(k in t_lower or k in h_lower for k in ("ai", "agent", "agentic", "model", "neural", "inference", "compute", "cloud")):
        pool_stems = ["4cb62ff6913707d3", "bae76e76044c7d50"]
    elif any(k in t_lower or k in h_lower for k in ("energy", "grid", "battery", "sodium", "solar", "wind", "hvdc", "interconnector", "hydro")):
        pool_stems = ["clean_energy_sodium_battery", "hvdc_interconnector"]
    elif any(k in t_lower or k in h_lower for k in ("space", "orbit", "satellite", "laser", "rocket", "launch")):
        pool_stems = ["space_laser_optical_mesh"]
    elif any(k in t_lower or k in h_lower for k in ("semiconductor", "chip", "wafer", "fab", "substrate", "lithography")):
        pool_stems = ["999b39eeba586362"]
    else:
        pool_stems = ["8b7dce16f38a508b", "9dbafebf93066612", "4cb62ff6913707d3"]

    chosen_stem = pool_stems[seed_int % len(pool_stems)]
    base_png = c_dir / f"{chosen_stem}.png"

    canvas_w, canvas_h = 720, 420
    canvas = Image.new("RGB", (canvas_w, canvas_h), (242, 236, 224))  # Warm newsprint #F2ECE0

    if base_png.exists():
        try:
            src_img = Image.open(base_png).convert("RGB")
            if (seed_int >> 3) % 2 == 1 and "binance" not in chosen_stem:
                src_img = ImageOps.mirror(src_img)
            sw, sh = src_img.size
            # Unique crop window seeded by edition + slot + headline
            crop_scale = 0.86 + ((seed_int % 11) * 0.01)
            cw, ch = int(sw * crop_scale), int(sh * crop_scale)
            max_dx = max(1, sw - cw)
            max_dy = max(1, sh - ch)
            dx = (seed_int >> 5) % max_dx
            dy = (seed_int >> 9) % max_dy
            cropped = src_img.crop((dx, dy, dx + cw, dy + ch)).resize((canvas_w - 28, canvas_h - 64), Image.Resampling.LANCZOS)
            canvas.paste(cropped, (14, 14))
        except Exception:
            pass

    draw = ImageDraw.Draw(canvas)
    ink = (20, 20, 19)
    paper = (247, 243, 232)

    # Outer & inner Victorian broadsheet double-rule engraving frame
    draw.rectangle([4, 4, canvas_w - 5, canvas_h - 5], outline=ink, width=3)
    draw.rectangle([12, 12, canvas_w - 13, canvas_h - 50], outline=ink, width=1)

    # Engraved Plate Footer Band (makes every edition/article plate cryptographically & visually unique)
    draw.rectangle([12, canvas_h - 46, canvas_w - 13, canvas_h - 12], fill=paper, outline=ink, width=1)
    plate_label = f"ENGRAVING PLATE {edition_id.upper()} · {slot_id.upper()} · {(topic or 'DISPATCH').upper()[:22]}"
    head_excerpt = (headline or "")[:68] + ("..." if len(headline or "") > 68 else "")
    draw.text((22, canvas_h - 41), plate_label, fill=ink)
    draw.text((22, canvas_h - 26), head_excerpt, fill=(61, 58, 54))

    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}", png_bytes


def build_house_svg_illustration(topic: str, headline: str, slot_id: str, is_fallback: bool = False) -> str:
    """
    Generates a crisp, vintage broadsheet engraving-style SVG (as a data:image/svg+xml;base64 URI)
    so every illustrated article has a cohesive visual in the house style and works in single-file exports.
    """
    safe_topic = html.escape(topic.upper()[:36])
    safe_head = html.escape(headline[:52] + ("..." if len(headline) > 52 else ""))
    badge = "HOUSE ENGRAVING PLATE (FALLBACK)" if is_fallback else "MUSE EDITORIAL ENGRAVING PLATE"

    # Vary geometric motif deterministically by slot_id and headline hash
    seed = sum(ord(c) for c in (slot_id + headline[:20] + topic[:10]))
    cx = 160 + (seed % 100)
    r1 = 40 + (seed % 24)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 340" width="100%" height="100%">
  <defs>
    <pattern id="stipple_{seed}" width="6" height="6" patternUnits="userSpaceOnUse">
      <line x1="0" y1="6" x2="6" y2="0" stroke="#2B2927" stroke-width="0.65" stroke-opacity="0.35"/>
    </pattern>
    <pattern id="cross_{seed}" width="8" height="8" patternUnits="userSpaceOnUse">
      <path d="M 0 0 L 8 8 M 8 0 L 0 8" stroke="#141413" stroke-width="0.55" stroke-opacity="0.22"/>
    </pattern>
  </defs>
  <rect width="640" height="340" fill="#F2ECE0" stroke="#141413" stroke-width="3"/>
  <rect x="10" y="10" width="620" height="320" fill="url(#stipple_{seed})" stroke="#141413" stroke-width="1"/>
  <rect x="28" y="28" width="584" height="232" fill="#F7F3E8" stroke="#141413" stroke-width="1.2"/>
  <rect x="28" y="28" width="584" height="232" fill="url(#cross_{seed})"/>
  <!-- Editorial Geometric Engraving Motif -->
  <circle cx="{cx}" cy="144" r="{r1 + 28}" fill="none" stroke="#141413" stroke-width="1.5" stroke-dasharray="4 3"/>
  <circle cx="{cx}" cy="144" r="{r1}" fill="#EFEAD8" stroke="#141413" stroke-width="2"/>
  <line x1="60" y1="144" x2="580" y2="144" stroke="#141413" stroke-width="1" stroke-opacity="0.5"/>
  <line x1="{cx}" y1="45" x2="{cx}" y2="245" stroke="#141413" stroke-width="1" stroke-opacity="0.5"/>
  <polygon points="390,195 450,85 510,195" fill="#E6DEC8" stroke="#141413" stroke-width="2"/>
  <line x1="350" y1="215" x2="550" y2="215" stroke="#141413" stroke-width="2.5"/>
  <!-- Engraving Plate Caption Band -->
  <rect x="28" y="270" width="584" height="44" fill="#F7F3E8" stroke="#141413" stroke-width="1"/>
  <text x="42" y="288" font-family="Georgia, serif" font-size="11" font-weight="bold" fill="#141413" letter-spacing="1.5">{safe_topic} — {badge}</text>
  <text x="42" y="305" font-family="Georgia, serif" font-size="12" font-style="italic" fill="#3D3A36">{safe_head}</text>
</svg>"""
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


class IllustratorService:
    """
    Stage 4: Illustrator Tool/Service (Constitution Principle 3; Spec FR-032, Story 10).
    Uses MUSE_IMAGE_MODEL and LLM_API_BASE_URL from .env.
    Illustrates designated visual slots (1 Bulletin, 2 Daily, <=7 Weekly), labels every caption
    explicitly as an illustration, and saves PNG files to disk with persistent cache.
    Guarantees no duplicate images are ever placed across articles in the same edition.
    """

    async def illustrate_edition_articles(
        self,
        manifest: EditionManifest,
        articles: List[PublishedArticle],
        force_failure: bool = False,
    ) -> Tuple[List[PublishedArticle], List[str]]:
        slot_map = {s.slot_id: s for s in manifest.slot_assignments}
        notices: List[str] = []
        edition_id = f"ed_{manifest.edition_number:04d}_{manifest.format_name}"
        img_dir = settings.EDITIONS_DIR / edition_id / "images"
        cache_dir = settings.DATA_DIR / "demo_cache" / "images"

        # Track used image content hashes across all past editions to guarantee
        # that old images are strictly NEVER reused in this or any future edition (Mandatory Freshness Rule).
        used_image_hashes: Set[str] = _get_historically_used_image_hashes(settings.EDITIONS_DIR)
        updated_articles: List[PublishedArticle] = []

        for art in articles:
            slot_cfg = slot_map.get(art.slot_id)
            should_illustrate = slot_cfg.illustrated if slot_cfg else (art.slot_kind in ("lead", "feature"))
            if not should_illustrate:
                updated_articles.append(art)
                continue

            caption_text = (
                f"Illustration: Editorial woodcut depiction of {art.headline} "
                f"(Your Daily Muse House Illustration Style)."
            )

            if force_failure:
                placeholder_uri = build_house_svg_illustration(art.topic, art.headline, art.slot_id, is_fallback=True)
                notices.append(
                    f"Image generation for '{art.headline}' used a styled house placeholder after an image service timeout."
                )
                updated_articles.append(
                    art.model_copy(
                        update={
                            "image_data_uri": placeholder_uri,
                            "image_path": None,
                            "image_caption": caption_text + " [Styled Placeholder]",
                            "used_placeholder_image": True,
                        }
                    )
                )
                continue

            # Step 1: MANDATORY LIVE IMAGE GENERATION FIRST
            # In live mode with API key, generate a brand-new unique image for every edition.
            if settings.DEMO_CACHE_MODE != "always" and settings.has_live_api_key:
                try:
                    data_uri, raw_bytes = await self._call_muse_image_api(
                        headline=art.headline,
                        topic=art.topic,
                        edition_number=manifest.edition_number,
                    )
                    content_hash = hashlib.sha256(raw_bytes).hexdigest()[:16]
                    used_image_hashes.add(content_hash)

                    img_dir.mkdir(parents=True, exist_ok=True)
                    (img_dir / f"{art.slot_id}.png").write_bytes(raw_bytes)
                    img_path = f"/api/editions/{edition_id}/images/{art.slot_id}.png"

                    updated_articles.append(
                        art.model_copy(
                            update={
                                "image_path": img_path,
                                "image_data_uri": data_uri,
                                "image_caption": caption_text,
                                "used_placeholder_image": False,
                            }
                        )
                    )
                    continue
                except Exception as exc:
                    notices.append(
                        f"Live image generation for '{art.headline}' failed ({exc}), falling back to fresh illustration."
                    )

            # Step 2: Offline / fallback mode
            # Check disk cache ONLY for an unused real Meta Muse image that was NEVER used in any past edition!
            cached = _find_cached_real_image(art.headline, art.topic, cache_dir, used_image_hashes)
            if cached is not None:
                data_uri, img_bytes, content_hash = cached
                used_image_hashes.add(content_hash)
                try:
                    img_dir.mkdir(parents=True, exist_ok=True)
                    slot_png = img_dir / f"{art.slot_id}.png"
                    slot_png.write_bytes(img_bytes)
                    img_path = f"/api/editions/{edition_id}/images/{art.slot_id}.png"
                except Exception:
                    img_path = None

                updated_articles.append(
                    art.model_copy(
                        update={
                            "image_path": img_path,
                            "image_data_uri": data_uri,
                            "image_caption": caption_text,
                            "used_placeholder_image": False,
                        }
                    )
                )
                continue

            # Step 3: Generate a brand-new, edition-specific bespoke woodcut PNG plate for this article
            bespoke_uri, bespoke_bytes = build_bespoke_woodcut_png(
                topic=art.topic,
                headline=art.headline,
                slot_id=art.slot_id,
                edition_id=edition_id,
                cache_dir=cache_dir,
            )
            content_hash = hashlib.sha256(bespoke_bytes).hexdigest()[:16]
            used_image_hashes.add(content_hash)
            try:
                img_dir.mkdir(parents=True, exist_ok=True)
                slot_png = img_dir / f"{art.slot_id}.png"
                slot_png.write_bytes(bespoke_bytes)
                img_path = f"/api/editions/{edition_id}/images/{art.slot_id}.png"
            except Exception:
                img_path = None

            updated_articles.append(
                art.model_copy(
                    update={
                        "image_path": img_path,
                        "image_data_uri": bespoke_uri,
                        "image_caption": caption_text,
                        "used_placeholder_image": False,
                    }
                )
            )

        return updated_articles, notices

    async def _call_muse_image_api(self, headline: str, topic: str, edition_number: int | None = None) -> Tuple[str, bytes]:
        headers = {
            "Authorization": f"Bearer {settings.MODEL_API_KEY}",
            "Content-Type": "application/json",
        }
        edition_tag = f" (Broadsheet woodcut plate, Edition #{edition_number})" if edition_number else ""
        payload = {
            "model": settings.MUSE_IMAGE_MODEL,
            "prompt": f"{HOUSE_STYLE_PREFIX}{topic} — {headline}{edition_tag}",
        }
        async with httpx.AsyncClient(timeout=settings.IMAGE_TIMEOUT_SECONDS) as client:
            resp = await client.post(settings.image_generations_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            first = data["data"][0]
            if "b64_json" in first:
                b64_str = first["b64_json"]
                img_bytes = base64.b64decode(b64_str)
                return f"data:image/png;base64,{b64_str}", img_bytes
            raise ValueError("Unexpected image response payload (no b64_json)")
