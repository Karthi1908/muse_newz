from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from config.settings import settings
from app.models.schemas import CadenceType, FormatName


class FormatResolver:
    """
    Deterministic format & page-structure resolver driven by config/formats.json
    (Constitution Principle 2 & 7; Spec FR-014, FR-015, FR-016, SC-006).
    """

    def __init__(self, formats_path: Path | None = None) -> None:
        path = formats_path or (settings.CONFIG_DIR / "formats.json")
        self.config: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    def cadence_to_format_name(self, cadence: CadenceType) -> FormatName:
        mapping = self.config["cadence_to_format"]
        if cadence not in mapping:
            raise ValueError(f"Unsupported cadence: {cadence}")
        return mapping[cadence]  # type: ignore[return-value]

    def get_format_spec(self, format_name: FormatName) -> Dict[str, Any]:
        return self.config["formats"][format_name]

    def get_slot_spec(self, slot_kind: str) -> Dict[str, Any]:
        return self.config["slot_specs"][slot_kind]

    def compute_story_window(
        self,
        cadence: CadenceType,
        last_edition_at: datetime | None,
        now: datetime | None = None,
    ) -> Tuple[datetime, datetime]:
        """
        Computes (window_start, window_end) per Clarified FR-017:
        - Bulletin & Daily: time since previous edition (or cadence length on first run) + 2h buffer.
        - Weekly: past 7 days + 2h buffer.
        """
        ref_now = now or datetime.now(timezone.utc)
        format_name = self.cadence_to_format_name(cadence)
        fmt = self.get_format_spec(format_name)
        buffer_hours = int(fmt.get("window_buffer_hours", 2))

        if format_name == "weekly":
            days = int(fmt.get("fixed_window_days", 7))
            start = ref_now - timedelta(days=days, hours=buffer_hours)
            return start, ref_now

        if last_edition_at is not None:
            start = last_edition_at - timedelta(hours=buffer_hours)
        else:
            cadence_hours = int(self.config["cadence_hours"].get(cadence, 24))
            start = ref_now - timedelta(hours=cadence_hours + buffer_hours)
        return start, ref_now

    def build_page_and_slot_blueprint(
        self,
        format_name: FormatName,
        topics: List[str],
        story_counts_by_topic: Dict[str, int] | None = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Returns (pages_blueprint, reader_notices) for the given format and active topics.
        Enforces:
        - Bulletin: 1 page, 3 articles, 0 outside-topics.
        - Daily: 2 pages, 8 articles, 1 outside-topics.
        - Weekly: 3 to 7 pages (always > Daily's 2 pages for 1..5 topics, FR-015 & SC-006),
          shortening or omitting section pages for topics lacking material while never falling
          below 3 pages (FR-016).
        """
        fmt = self.get_format_spec(format_name)
        notices: List[str] = []

        if format_name in ("bulletin", "daily"):
            pages: List[Dict[str, Any]] = []
            topic_cycle = [t for t in topics if (story_counts_by_topic is None or story_counts_by_topic.get(t, 1) > 0)]
            if story_counts_by_topic is not None:
                for t in topics:
                    if story_counts_by_topic.get(t, 0) == 0:
                        notices.append(f"Topic '{t}' had no new stories in the current window.")
            if not topic_cycle:
                topic_cycle = list(topics)

            t_idx = 0
            for raw_page in fmt["pages"]:
                slots = []
                for s in raw_page["slots"]:
                    slot_copy = dict(s)
                    if slot_copy.get("outside_topics"):
                        slot_copy["topic"] = "Outside Your Usual Reading"
                    else:
                        slot_copy["topic"] = topic_cycle[t_idx % len(topic_cycle)]
                        t_idx += 1
                    slots.append(slot_copy)
                pages.append(
                    {
                        "page_number": raw_page["page_number"],
                        "template": raw_page["template"],
                        "section_flag": raw_page["section_flag"],
                        "slots": slots,
                    }
                )
            return pages, notices

        # Weekly Format (3 to 7 pages, always > Daily's 2 pages)
        pages = []
        active_topics_with_counts: List[Tuple[str, int]] = []
        for t in topics:
            cnt = 2 if story_counts_by_topic is None else story_counts_by_topic.get(t, 0)
            if cnt == 0:
                notices.append(
                    f"Section page for '{t}' was omitted because no new verified stories were found this week."
                )
            else:
                active_topics_with_counts.append((t, cnt))

        # Guarantee minimum 3 pages (Front + at least 1 Section Page + Closing Page, FR-015 / FR-016)
        if not active_topics_with_counts:
            fallback_topic = topics[0]
            active_topics_with_counts.append((fallback_topic, 1))
            notices.append(
                f"Quiet week across your topics; included a shortened section page for '{fallback_topic}' to maintain edition structure."
            )

        # 1. Front Page (Page 1: 5 top stories across topics)
        front_spec = fmt["front_page"]
        front_slots = []
        for idx, s in enumerate(front_spec["slots"]):
            slot_copy = dict(s)
            slot_copy["topic"] = active_topics_with_counts[idx % len(active_topics_with_counts)][0]
            front_slots.append(slot_copy)
        pages.append(
            {
                "page_number": 1,
                "template": front_spec["template"],
                "section_flag": front_spec["section_flag"],
                "slots": front_slots,
            }
        )

        # 2. Topic Section Pages (Pages 2 .. N+1)
        sec_spec = fmt["per_topic_section_page"]
        current_page_num = 2
        for t_idx, (topic_name, available_count) in enumerate(active_topics_with_counts, start=1):
            sec_slots = []
            # Feature slot is always included on an active section page
            feat_template = sec_spec["slots"][0]
            sec_slots.append(
                {
                    "slot_id": feat_template["slot_id_pattern"].format(topic_idx=t_idx),
                    "kind": feat_template["kind"],
                    "illustrated": feat_template["illustrated"],
                    "outside_topics": False,
                    "topic": topic_name,
                }
            )
            if available_count >= 2:
                brief_template = sec_spec["slots"][1]
                sec_slots.append(
                    {
                        "slot_id": brief_template["slot_id_pattern"].format(topic_idx=t_idx),
                        "kind": brief_template["kind"],
                        "illustrated": brief_template["illustrated"],
                        "outside_topics": False,
                        "topic": topic_name,
                    }
                )
            else:
                notices.append(
                    f"Section page for '{topic_name}' was shortened to 1 feature story due to limited weekly material."
                )

            pages.append(
                {
                    "page_number": current_page_num,
                    "template": sec_spec["template"],
                    "section_flag": f"Section: {topic_name}",
                    "slots": sec_slots,
                }
            )
            current_page_num += 1

        # 3. Closing Page (Final Page: Outside-Topics Feature + Week's Corrections + Sources)
        closing_spec = fmt["closing_page"]
        closing_slots = []
        for s in closing_spec["slots"]:
            slot_copy = dict(s)
            slot_copy["topic"] = "Outside Your Usual Reading"
            closing_slots.append(slot_copy)
        pages.append(
            {
                "page_number": current_page_num,
                "template": closing_spec["template"],
                "section_flag": closing_spec["section_flag"],
                "slots": closing_slots,
            }
        )

        return pages, notices
