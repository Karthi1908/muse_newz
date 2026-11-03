from __future__ import annotations
import re
from typing import Dict, List, Set, Tuple
from urllib.parse import urlparse, urlunparse
from app.models.schemas import CandidatePool, CandidateStory, FormatName


def canonicalize_url(url: str) -> str:
    """Normalizes URLs for deterministic duplicate detection (Principle 2)."""
    parsed = urlparse(url.strip().lower())
    clean_path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme or "https", parsed.netloc, clean_path, "", "", ""))


def title_shingles(headline: str) -> Set[str]:
    tokens = re.findall(r"[a-z0-9]{3,}", headline.lower())
    stop = {
        "the", "and", "for", "with", "from", "into", "over", "after", "new",
        "report", "shows", "reports", "alleged", "amid", "says", "tied",
    }
    filtered = [t for t in tokens if t not in stop]
    return set(filtered)


def extract_event_signature(story: CandidateStory) -> Tuple[Set[str], Set[str], Set[str]]:
    """
    Extracts (proper_entities, numeric_magnitudes, event_categories) from a candidate story
    so two articles covering the exact same real-world event (e.g. '$6.3B Binance hack tied to North Korea'
    vs 'TRM Labs reports $6.36B Binance theft') are recognized as the same event across topics.
    """
    combined_text = f"{story.headline} {story.summary}"
    lower = combined_text.lower()

    # 1. Extract normalized billion/million scale markers (e.g. "$6.3 billion", "$6.36B" -> "6b")
    magnitudes: Set[str] = set()
    for match in re.finditer(r"\$?\s*(\d+(?:\.\d+)?)\s*(billion|trillion|million|b\b|m\b|t\b)", lower):
        val = float(match.group(1))
        unit = match.group(2)[0]  # 'b', 't', 'm'
        bucket = int(round(val))
        magnitudes.add(f"{bucket}{unit}")

    # 2. Extract high-impact event categories
    event_categories: Set[str] = set()
    category_map = {
        "cyber_heist": {"hack", "hackers", "hacked", "theft", "steal", "stolen", "heist", "breach", "exploit", "withdrawals", "ransomware"},
        "geopolitics_law": {"fbi", "sanctions", "indictment", "lawsuit", "pentagon", "treasury", "north", "korea", "lazarus"},
        "clinical_trial": {"phase", "clinical", "trial", "fda", "patients", "placebo", "cohort"},
        "grid_storage": {"gigawatt", "megawatt", "subsea", "interconnector", "sodium", "hydro"},
    }
    words = set(re.findall(r"[a-z0-9]{3,}", lower))
    for cat, kw_set in category_map.items():
        if words & kw_set:
            event_categories.add(cat)

    # 3. Extract distinctive entity/subject tokens from the headline (excluding geographic & generic terms)
    generic_news_words = {
        "the", "and", "for", "with", "from", "into", "over", "after", "new", "report", "reports",
        "shows", "alleged", "amid", "says", "tied", "launches", "announces", "releases", "global",
        "system", "systems", "models", "model", "company", "market", "industry", "update", "follow",
        "analysis", "study", "data", "first", "major", "record", "billion", "million", "trillion",
        "crypto", "hackers", "steal", "theft", "suspends", "withdrawals", "india", "indian",
        "south", "asia", "asian", "north", "central", "east", "west", "america", "american",
        "europe", "european", "united", "states", "kingdom", "world", "international", "national",
        "regional", "region", "across", "brings", "action", "strategic", "establishes", "largest",
    }
    headline_tokens = set(re.findall(r"[a-z]{4,}", story.headline.lower())) - generic_news_words
    return headline_tokens, magnitudes, event_categories


def is_same_underlying_event(a: CandidateStory, b: CandidateStory) -> bool:
    """
    Returns True if candidate stories `a` and `b` describe the same underlying news event,
    even if phrased differently by different outlets or filed under different beats.
    """
    sh_a = title_shingles(a.headline)
    sh_b = title_shingles(b.headline)
    if jaccard_similarity(sh_a, sh_b) >= 0.60:
        return True

    ent_a, mag_a, cat_a = extract_event_signature(a)
    ent_b, mag_b, cat_b = extract_event_signature(b)

    shared_entities = ent_a & ent_b
    shared_magnitudes = mag_a & mag_b
    shared_categories = cat_a & cat_b

    # Same named entity + same numeric scale (e.g. "binance" + "6b")
    if shared_entities and shared_magnitudes:
        return True
    # Same named entity + same high-impact event category + at least 2 shared title shingles
    if shared_entities and shared_categories and len(sh_a & sh_b) >= 2:
        return True
    # Same numeric scale (e.g. "6b") + same event category (e.g. "cyber_heist") in same topic domain
    if shared_magnitudes and shared_categories and ("cyber_heist" in shared_categories):
        return True
    # 3+ distinctive non-geographic headline entities in common with meaningful title overlap
    if len(shared_entities) >= 3 and jaccard_similarity(sh_a, sh_b) >= 0.30:
        return True

    return False


def jaccard_similarity(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class DeduplicationService:
    """
    Deterministic Intra-Edition & Cross-Edition No-Repeat Filter
    (Constitution Principle 2; Spec FR-020, FR-021, Story 7, SC-005).
    """

    def filter_candidate_pool(
        self,
        pool: CandidatePool,
        recent_records: List[Dict[str, str]],
        allow_weekly_follow_ups: bool = False,
    ) -> Tuple[CandidatePool, List[str]]:
        """
        1. Removes intra-edition duplicate stories across topics (FR-020).
        2. Removes stories already published in recent editions (7d Bulletin/Daily, 28d Weekly, FR-021).
        3. In Weekly editions, allows a previously published story ONLY if it has a materially new
           development (newer date or updated facts) and marks `is_follow_up = True` (Story 7).
        """
        seen_urls: Set[str] = set()
        seen_fingerprints: Set[str] = set()
        seen_shingles: List[Set[str]] = []
        kept_all_stories: List[CandidateStory] = []
        dropped_reasons: List[str] = []

        history_by_url = {canonicalize_url(r["canonical_url"]): r for r in recent_records}
        history_by_fp = {r["story_fingerprint"]: r for r in recent_records}
        history_shingles = [(r, title_shingles(r.get("headline", ""))) for r in recent_records]

        filtered_by_topic: Dict[str, List[CandidateStory]] = {}

        for topic, stories in pool.candidates_by_topic.items():
            kept: List[CandidateStory] = []
            for story in stories:
                primary_url = canonicalize_url(story.sources[0].url)
                shingles = title_shingles(story.headline)

                # Step 1: Intra-edition duplicate & same-event consolidation check (FR-020)
                matching_existing = next(
                    (prev_s for prev_s in kept_all_stories if is_same_underlying_event(story, prev_s)),
                    None,
                )
                if (
                    primary_url in seen_urls
                    or story.story_fingerprint in seen_fingerprints
                    or any(jaccard_similarity(shingles, prev) >= 0.65 for prev in seen_shingles)
                    or matching_existing is not None
                ):
                    if matching_existing is not None:
                        existing_urls = {canonicalize_url(s.url) for s in matching_existing.sources}
                        for src in story.sources:
                            if canonicalize_url(src.url) not in existing_urls and len(matching_existing.sources) < 4:
                                new_sid = f"S{len(matching_existing.sources) + 1}"
                                matching_existing.sources.append(src.model_copy(update={"source_id": new_sid}))
                                existing_urls.add(canonicalize_url(src.url))
                        matching_existing.mention_count = getattr(matching_existing, "mention_count", 1) + getattr(story, "mention_count", 1)
                        matching_existing.relevance_score = round(min(9.95, matching_existing.relevance_score + 0.35), 2)
                    dropped_reasons.append(f"Collapsed duplicate intra-edition story: '{story.headline}'")
                    continue

                # Step 2: Cross-edition no-repeat check (FR-021)
                prior_record = history_by_url.get(primary_url) or history_by_fp.get(story.story_fingerprint)
                if not prior_record:
                    for hist_rec, hist_sh in history_shingles:
                        if jaccard_similarity(shingles, hist_sh) >= 0.65:
                            prior_record = hist_rec
                            break

                if prior_record is not None:
                    is_new_dev = self._has_materially_new_development(story, prior_record)
                    if allow_weekly_follow_ups and is_new_dev:
                        story.is_follow_up = True
                        if not story.headline.lower().startswith("follow-up:"):
                            story.headline = f"Follow-up: {story.headline}"
                    elif allow_weekly_follow_ups and prior_record.get("format_name") != "weekly" and not kept:
                        # Guarantee Weekly edition maintains at least 1 follow-up story per topic to preserve section structure (FR-015/016)
                        story.is_follow_up = True
                        if not story.headline.lower().startswith("follow-up:"):
                            story.headline = f"Follow-up: {story.headline}"
                    else:
                        dropped_reasons.append(
                            f"Filtered repeat story from Edition #{prior_record.get('edition_number')}: '{story.headline}'"
                        )
                        continue

                seen_urls.add(primary_url)
                seen_fingerprints.add(story.story_fingerprint)
                seen_shingles.append(shingles)
                kept_all_stories.append(story)
                kept.append(story)

            filtered_by_topic[topic] = kept

        # Also deduplicate outside-topic candidates
        kept_outside: List[CandidateStory] = []
        for out_story in pool.outside_candidates:
            out_url = canonicalize_url(out_story.sources[0].url)
            out_sh = title_shingles(out_story.headline)
            if (
                out_url in seen_urls
                or out_story.story_fingerprint in seen_fingerprints
                or out_url in history_by_url
                or out_story.story_fingerprint in history_by_fp
                or any(jaccard_similarity(out_sh, prev) >= 0.65 for prev in seen_shingles)
                or any(is_same_underlying_event(out_story, prev_s) for prev_s in kept_all_stories)
            ):
                continue
            seen_urls.add(out_url)
            seen_fingerprints.add(out_story.story_fingerprint)
            seen_shingles.append(out_sh)
            kept_all_stories.append(out_story)
            kept_outside.append(out_story)

        empty_topics = [t for t, items in filtered_by_topic.items() if len(items) == 0]
        return (
            CandidatePool(
                format_name=pool.format_name,
                story_window_start=pool.story_window_start,
                story_window_end=pool.story_window_end,
                candidates_by_topic=filtered_by_topic,
                outside_candidates=kept_outside,
                empty_topics=empty_topics,
            ),
            dropped_reasons,
        )

    @staticmethod
    def _has_materially_new_development(candidate: CandidateStory, prior_record: Dict[str, str]) -> bool:
        """
        Determines whether a Weekly story has a materially new development compared to its prior appearance:
        e.g., explicitly updated headline/follow-up markers or newer source publication date.
        """
        prior_date = (prior_record.get("published_at") or "")[:10]
        cand_date = (candidate.sources[0].published_date or "")[:10]
        if cand_date > prior_date or "follow-up" in candidate.headline.lower() or "update" in candidate.headline.lower():
            return True
        if candidate.is_follow_up:
            return True
        return False
