from __future__ import annotations
import re
from typing import List, Tuple
from app.agents.meta_model import get_muse_model
from app.models.schemas import TopicEditProposal


_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(all\s+)?previous\s+instructions|system\s+prompt|you\s+are\s+now\s+dan|<script)",
    re.IGNORECASE,
)


def _split_topics(text: str) -> List[str]:
    """Splits a natural language list of topics separated by commas, semicolons, or 'and'/'&'."""
    # Replace ' and ' or ' & ' with comma, then split by comma and semicolon
    normalized = re.sub(r"\s+(?:and|&)\s+", ", ", text, flags=re.IGNORECASE)
    parts = [p.strip().strip("'\"").rstrip(".") for p in re.split(r"[,;]+", normalized)]
    return [p for p in parts if p and p.lower() not in ("and", "&", "the", "a", "an")]


class TopicEditorAgent:
    """
    Google ADK LlmAgent for Topic Management by Text, Voice, or UI Controls
    (Constitution Guardrail G-2.2; Spec FR-001..FR-003, Story 8).

    Rules:
    - Reader can have between 1 and max 5 topics (any number <= 5 is valid).
    - Supports multiple simultaneous additions and multiple simultaneous removals.
    - Never silently truncates when additions would exceed 5 topics; asks which topic to replace.
    - Prevents removing all topics (minimum 1 required).
    - Always requires reader confirmation before saving.
    """

    def __init__(self) -> None:
        self.llm = get_muse_model(temperature=0.1)

    async def propose_topic_change(
        self,
        current_topics: List[str],
        user_command: str,
        replace_target: str | None = None,
        current_geographic_preference: str = "Global",
    ) -> TopicEditProposal:
        cleaned_cmd = user_command.strip()
        if not cleaned_cmd:
            return TopicEditProposal(
                transcript_or_input="",
                current_topics=current_topics,
                proposed_topics=list(current_topics),
                current_geographic_preference=current_geographic_preference,
                proposed_geographic_preference=current_geographic_preference,
                requires_replacement_choice=False,
                assistant_message="No topic change was heard or entered. Please speak again or type your change.",
                unclear_audio=True,
            )

        if _INJECTION_PATTERNS.search(cleaned_cmd):
            return TopicEditProposal(
                transcript_or_input=cleaned_cmd,
                current_topics=current_topics,
                proposed_topics=list(current_topics),
                current_geographic_preference=current_geographic_preference,
                proposed_geographic_preference=current_geographic_preference,
                requires_replacement_choice=False,
                assistant_message="Request rejected by Topic Guardrail: topic inputs must be subject areas, not system instructions.",
            )

        return self._deterministic_parse_topic_command(
            current_topics=current_topics,
            command=cleaned_cmd,
            replace_target=replace_target,
            current_geographic_preference=current_geographic_preference,
        )

    def _match_and_remove_topics(
        self,
        working: List[str],
        targets: List[str],
    ) -> Tuple[List[str], List[str]]:
        """Removes matched topics from `working`. Returns (new_working, actually_removed)."""
        removed: List[str] = []
        new_working = list(working)

        for target in targets:
            tgt_clean = target.strip().lower()
            if not tgt_clean:
                continue

            # Check if target is a 1-based index (e.g., "1", "topic 1", "first")
            idx_match = re.match(r"^(?:topic\s+)?#?(\d+)$", tgt_clean)
            if idx_match:
                idx = int(idx_match.group(1)) - 1
                if 0 <= idx < len(new_working):
                    removed.append(new_working[idx])
                    new_working.pop(idx)
                    continue

            # Word / substring matching
            matched_idx = -1
            for i, existing in enumerate(new_working):
                ext_lower = existing.lower()
                # Exact or substring match
                if tgt_clean in ext_lower or ext_lower in tgt_clean:
                    matched_idx = i
                    break
                # Significant word overlap (words of length >= 4)
                words = [w for w in re.findall(r"\w+", tgt_clean) if len(w) >= 4]
                if words and any(w in ext_lower for w in words):
                    matched_idx = i
                    break

            if matched_idx != -1:
                removed.append(new_working[matched_idx])
                new_working.pop(matched_idx)

        return new_working, removed

    def _deterministic_parse_topic_command(
        self,
        current_topics: List[str],
        command: str,
        replace_target: str | None = None,
        current_geographic_preference: str = "Global",
    ) -> TopicEditProposal:
        working = list(current_topics)
        cmd = command.strip()
        proposed_geo = current_geographic_preference

        # 0. Extract optional Geographic Preference clause:
        # e.g. "set region to Europe & UK", "geographic preference: Asia-Pacific", "geography India"
        geo_only_match = re.match(
            r"^(?:set\s+)?(?:region|geography|geographic\s+preference|location)\s*(?:to|:|=)?\s+(.+)$",
            cmd,
            flags=re.IGNORECASE,
        )
        if geo_only_match and ";" not in cmd:
            new_geo = geo_only_match.group(1).strip().strip(".'\"")[:60]
            return TopicEditProposal(
                transcript_or_input=command,
                current_topics=current_topics,
                proposed_topics=working,
                current_geographic_preference=current_geographic_preference,
                proposed_geographic_preference=new_geo,
                requires_replacement_choice=False,
                assistant_message=f"Updated geographic preference to '{new_geo}'. Please confirm to save.",
            )

        inline_geo_match = re.search(
            r"(?:;\s*|\s+and\s+)?(?:set\s+)?(?:region|geography|geographic\s+preference)\s*(?:to|:|=)?\s+([A-Za-z0-9\s&\-\/]+)$",
            cmd,
            flags=re.IGNORECASE,
        )
        if inline_geo_match:
            proposed_geo = inline_geo_match.group(1).strip().strip(".'\"")[:60]
            cmd = cmd[:inline_geo_match.start()].strip().rstrip(";,")

        # 1. If an explicit replacement choice was supplied for an overflow candidate
        if replace_target:
            for idx, existing in enumerate(working):
                if replace_target.lower() in existing.lower() or existing.lower() in replace_target.lower():
                    working[idx] = cmd[:80]
                    return TopicEditProposal(
                        transcript_or_input=command,
                        current_topics=current_topics,
                        proposed_topics=working,
                        requires_replacement_choice=False,
                        assistant_message=f"Replaced '{existing}' with '{cmd[:80]}'. ({len(working)} of max 5 topics). Please confirm to save.",
                    )

        # 2. Complete reset / Set command: e.g., "set topics to X, Y", "topics: X, Y", "only follow X and Y"
        set_match = re.match(
            r"^(?:set\s+topics\s+(?:to\s+)?|topics\s*:\s*|only\s+follow\s+)(.+)$",
            cmd,
            flags=re.IGNORECASE,
        )
        if set_match:
            new_topics = _split_topics(set_match.group(1))
            if not new_topics:
                return TopicEditProposal(
                    transcript_or_input=command,
                    current_topics=current_topics,
                    proposed_topics=working,
                    assistant_message="You must specify at least 1 topic (between 1 and max 5 topics).",
                )
            if len(new_topics) > 5:
                kept = new_topics[:5]
                overflow = new_topics[5]
                return TopicEditProposal(
                    transcript_or_input=command,
                    current_topics=current_topics,
                    proposed_topics=kept,
                    requires_replacement_choice=True,
                    overflow_topic_candidate=overflow,
                    assistant_message=(
                        f"Specified {len(new_topics)} topics, exceeding the maximum of 5. "
                        f"Choose which topic to replace with '{overflow}'."
                    ),
                )
            return TopicEditProposal(
                transcript_or_input=command,
                current_topics=current_topics,
                proposed_topics=new_topics,
                requires_replacement_choice=False,
                assistant_message=f"Set topics to {len(new_topics)} topic(s): {', '.join(new_topics)}. Please confirm to save.",
            )

        # 3. Combined Drop and Add:
        # e.g., "drop X, Y, add A, B", "remove X; add Y", "swap X for Y", "replace X with Y"
        to_drop_raw: str | None = None
        to_add_raw: str | None = None

        swap_match = re.search(
            r"(?:replace|swap)\s+(.+?)\s+(?:with|for)\s+(.+)",
            cmd,
            flags=re.IGNORECASE,
        )
        drop_add_match = re.search(
            r"(?:drop|remove|delete)\s+(.+?)\s*(?:[;,]|\s+and)?\s*(?:add|include|follow)\s+(.+)",
            cmd,
            flags=re.IGNORECASE,
        )
        add_drop_match = re.search(
            r"(?:add|include|follow)\s+(.+?)\s*(?:[;,]|\s+and)?\s*(?:drop|remove|delete)\s+(.+)",
            cmd,
            flags=re.IGNORECASE,
        )

        if swap_match:
            to_drop_raw = swap_match.group(1)
            to_add_raw = swap_match.group(2)
        elif drop_add_match:
            to_drop_raw = drop_add_match.group(1)
            to_add_raw = drop_add_match.group(2)
        elif add_drop_match:
            to_add_raw = add_drop_match.group(1)
            to_drop_raw = add_drop_match.group(2)

        # 4. Drop-only command: e.g., "drop X", "remove X and Y", "delete topic 1, 2"
        drop_only_match = re.match(r"^(?:drop|remove|delete)\s+(.+)$", cmd, flags=re.IGNORECASE)
        if drop_only_match and not to_drop_raw:
            to_drop_raw = drop_only_match.group(1)

        # 5. Add-only command: e.g., "add X", "add X, Y, and Z"
        add_only_match = re.match(r"^(?:add|include|follow)\s+(.+)$", cmd, flags=re.IGNORECASE)
        if add_only_match and not to_add_raw:
            to_add_raw = add_only_match.group(1)

        # If neither drop nor add pattern matched, treat entire input as new topic(s) to add
        if not to_drop_raw and not to_add_raw:
            to_add_raw = cmd

        # Execute Drop phase
        actually_removed: List[str] = []
        if to_drop_raw:
            drop_targets = _split_topics(to_drop_raw)
            updated_working, actually_removed = self._match_and_remove_topics(working, drop_targets)
            if not updated_working:
                return TopicEditProposal(
                    transcript_or_input=command,
                    current_topics=current_topics,
                    proposed_topics=working,
                    assistant_message="Cannot remove all topics. You must keep at least 1 topic (between 1 and max 5 topics).",
                )
            working = updated_working

        # Execute Add phase
        actually_added: List[str] = []
        overflow_candidates: List[str] = []
        if to_add_raw:
            add_targets = _split_topics(to_add_raw)
            for cand in add_targets:
                cand_clean = cand.strip()[:80]
                if not cand_clean:
                    continue
                # Skip if already in list
                if any(cand_clean.lower() == t.lower() for t in working):
                    continue
                if len(working) < 5:
                    working.append(cand_clean)
                    actually_added.append(cand_clean)
                else:
                    overflow_candidates.append(cand_clean)

        # Handle overflow if additions exceeded 5 topics
        if overflow_candidates:
            overflow_topic = overflow_candidates[0]
            return TopicEditProposal(
                transcript_or_input=command,
                current_topics=current_topics,
                proposed_topics=working,
                requires_replacement_choice=True,
                overflow_topic_candidate=overflow_topic,
                assistant_message=(
                    f"You have reached the maximum of 5 topics. To add '{overflow_topic}', "
                    "please choose which existing topic to replace."
                ),
            )

        # If nothing was added or removed
        if not actually_removed and not actually_added:
            return TopicEditProposal(
                transcript_or_input=command,
                current_topics=current_topics,
                proposed_topics=working,
                assistant_message="No matching topics were removed or new topics added.",
            )

        # Compose feedback message
        parts: List[str] = []
        if actually_removed:
            parts.append(f"dropped {', '.join(repr(t) for t in actually_removed)}")
        if actually_added:
            parts.append(f"added {', '.join(repr(t) for t in actually_added)}")
        if proposed_geo != current_geographic_preference:
            parts.append(f"set region to '{proposed_geo}'")
        action_desc = " and ".join(parts)

        return TopicEditProposal(
            transcript_or_input=command,
            current_topics=current_topics,
            proposed_topics=working,
            current_geographic_preference=current_geographic_preference,
            proposed_geographic_preference=proposed_geo,
            requires_replacement_choice=False,
            assistant_message=f"Updated topics: {action_desc}. You now have {len(working)} of max 5 topics (Region: {proposed_geo}). Please confirm to save.",
        )
