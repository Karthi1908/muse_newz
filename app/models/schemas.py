from __future__ import annotations
from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

CadenceType = Literal["every_4h", "every_8h", "every_12h", "daily", "weekly"]
FormatName = Literal["bulletin", "daily", "weekly"]
PageTemplate = Literal["front", "inside", "section", "closing"]
SlotKind = Literal["lead", "secondary", "brief", "feature"]
ClaimVerdict = Literal["verified", "corrected", "removed"]
WeekdayType = Literal["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def _extract_clean_reader_name(reader_name: Optional[str]) -> str:
    clean = (reader_name or "").strip()
    if clean.lower().startswith("the "):
        clean = clean[4:].strip()
    if clean.lower().endswith(" courier"):
        clean = clean[:-8].strip()
    return clean if clean else "Muse"


def compute_publication_title(reader_name: Optional[str]) -> str:
    """
    Returns 'The [Name] Courier' (e.g., 'The Aisha Courier'),
    falling back to 'The Muse Courier' if no name is set yet (FR-049, Decision #17).
    """
    name = _extract_clean_reader_name(reader_name)
    return f"The {name} Courier"


def compute_publication_tagline(reader_name: Optional[str]) -> str:
    """
    Returns '“Made for [Name]. Checked before print.”' (e.g., '“Made for Aisha. Checked before print.”'),
    falling back to '“Made for Muse. Checked before print.”' if no name is set yet (FR-050, Decision #17).
    """
    name = _extract_clean_reader_name(reader_name)
    return f"“Made for {name}. Checked before print.”"


class ReaderProfile(BaseModel):
    reader_name: str = Field(default="Aisha", max_length=60)
    time_zone: str = Field(default="UTC", description="IANA time zone string")
    geographic_preference: str = Field(
        default="Global",
        min_length=2,
        max_length=60,
        description="Geographic focus for news research (e.g. 'Global', 'United States', 'Europe & UK', 'Asia-Pacific', 'India & South Asia')",
    )
    topics: List[str] = Field(..., min_length=1, max_length=5)

    @property
    def display_reader_name(self) -> str:
        return _extract_clean_reader_name(self.reader_name)

    @property
    def publication_title(self) -> str:
        return compute_publication_title(self.reader_name)

    @property
    def publication_tagline(self) -> str:
        return compute_publication_tagline(self.reader_name)

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, v: List[str]) -> List[str]:
        cleaned = [t.strip() for t in v if t and t.strip()]
        if not (1 <= len(cleaned) <= 5):
            raise ValueError("Reader must maintain between 1 and 5 non-empty topics.")
        for topic in cleaned:
            if len(topic) < 2 or len(topic) > 80:
                raise ValueError(f"Topic '{topic}' must be between 2 and 80 characters.")
        return cleaned


class TopicEditProposal(BaseModel):
    transcript_or_input: str
    current_topics: List[str]
    proposed_topics: List[str] = Field(..., min_length=1, max_length=5)
    current_geographic_preference: str = "Global"
    proposed_geographic_preference: Optional[str] = None
    requires_replacement_choice: bool = False
    overflow_topic_candidate: Optional[str] = None
    assistant_message: str
    unclear_audio: bool = False


class ScheduleState(BaseModel):
    cadence: CadenceType = "daily"
    start_time_local: str = Field(default="07:00", pattern=r"^\d{2}:\d{2}$")
    weekly_weekday: Optional[WeekdayType] = "SUN"
    time_zone: str = "UTC"
    paused: bool = False
    next_due_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[Literal["completed", "failed", "running", "skipped"]] = None
    last_failure_reason: Optional[str] = None
    builds_today_count: int = 0
    daily_cap: int = 6
    demo_mode: bool = False
    new_edition_available: bool = False


class SourceDocument(BaseModel):
    source_id: str = Field(..., description="Citation tag, e.g., 'S1'")
    source_name: str
    url: str
    published_date: str
    verbatim_text: str = Field(..., min_length=300, max_length=8000)


class CandidateStory(BaseModel):
    candidate_id: str
    topic: str
    headline: str
    summary: str
    relevance_score: float = Field(default=8.0, ge=0.0, le=10.0)
    mention_count: int = Field(default=1, ge=1, description="Number of sources/dispatches mentioning this underlying event")
    story_fingerprint: str = Field(..., description="Deterministic hash of normalized entities + title shingles")
    is_outside_topic: bool = False
    outside_rationale: Optional[str] = None
    is_follow_up: bool = False
    sources: List[SourceDocument] = Field(..., min_length=1)


class CandidatePool(BaseModel):
    format_name: FormatName
    story_window_start: datetime
    story_window_end: datetime
    candidates_by_topic: dict[str, List[CandidateStory]]
    outside_candidates: List[CandidateStory] = Field(default_factory=list)
    empty_topics: List[str] = Field(default_factory=list)


class SlotAssignment(BaseModel):
    slot_id: str
    page_number: int
    page_template: PageTemplate
    section_flag: str
    slot_kind: SlotKind
    illustrated: bool
    outside_topics: bool
    topic: str
    assigned_candidate: CandidateStory
    reserve_candidates: List[CandidateStory] = Field(default_factory=list)


class EditionManifest(BaseModel):
    edition_number: int
    format_name: FormatName
    format_label: Literal["Bulletin", "Daily", "Weekly"]
    design_version: str = "1.0.0"
    reader_snapshot: ReaderProfile
    story_window_start: datetime
    story_window_end: datetime
    total_pages: int
    slot_assignments: List[SlotAssignment]
    omitted_topics_notices: List[str] = Field(default_factory=list)


class ClaimRecord(BaseModel):
    claim_id: str
    claim_text: str
    original_sentence: str
    verdict: ClaimVerdict
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    supporting_quote: Optional[str] = None
    note: Optional[str] = None


class DraftIterationOutput(BaseModel):
    slot_id: str
    iteration: int
    headline: str
    deck: str
    byline: str
    body_paragraphs: List[str]
    illustration_prompt: str
    claims: List[ClaimRecord]
    all_supported: bool


class PublishedArticle(BaseModel):
    slot_id: str
    page_number: int
    slot_kind: SlotKind
    topic: str
    headline: str
    deck: str
    byline: str
    body_paragraphs: List[str]
    sources: List[SourceDocument]
    claims: List[ClaimRecord]
    verified_claims_count: int
    corrected_claims_count: int
    removed_claims_count: int
    outside_flag: bool = False
    outside_note: Optional[str] = None
    follow_up_flag: bool = False
    image_path: Optional[str] = None
    image_data_uri: Optional[str] = None
    image_caption: Optional[str] = None
    used_placeholder_image: bool = False
    substituted_from_reserve: bool = False
    mention_count: int = 1
    layout_orientation: Literal["vertical", "horizontal"] = "vertical"


WhitespaceSizeTier = Literal["compact", "column", "banner"]
WhitespaceFillerType = Literal["comic_joke", "epigram_wit", "muse_brief_ad"]


class WhitespaceRegion(BaseModel):
    region_id: str
    page_number: int
    bbox: List[int] = Field(..., description="[x, y, width, height] in layout px")
    area_ratio: float = Field(..., ge=0.0, le=1.0, description="Free space ratio on page")
    aspect_ratio: float = Field(..., description="width / height")
    column_span: int = Field(default=4, ge=1, le=12)
    size_tier: WhitespaceSizeTier
    orientation: Literal["vertical", "horizontal"] = "vertical"
    detection_source: Literal["sam-3", "grid_fallback"] = "sam-3"


class WhitespaceFillerItem(BaseModel):
    filler_id: str
    region_id: str
    page_number: int
    filler_type: WhitespaceFillerType
    size_tier: WhitespaceSizeTier
    layout_orientation: Literal["vertical", "horizontal"] = "vertical"
    title: str
    subtitle_or_eyebrow: str
    dialogue_or_copy: str
    comic_dialogue_speaker: Optional[str] = None
    image_prompt: Optional[str] = None
    image_path: Optional[str] = None
    image_data_uri: Optional[str] = None
    caption_or_motto: Optional[str] = None
    variant_key: Optional[str] = None


class PageRenderModel(BaseModel):
    page_number: int
    total_pages: int
    template: PageTemplate
    section_flag: str
    articles: List[PublishedArticle]
    whitespace_fillers: List[WhitespaceFillerItem] = Field(default_factory=list)


class PublishedEdition(BaseModel):
    edition_id: str
    edition_number: int
    reader_name: str = ""
    geographic_preference: str = "Global"
    format_name: FormatName
    format_label: Literal["Bulletin", "Daily", "Weekly"]
    published_at: datetime
    design_version: str = "1.0.0"
    total_pages: int
    pages: List[PageRenderModel]
    corrections_box: List[ClaimRecord] = Field(default_factory=list)
    total_claims_checked: int
    total_claims_verified: int
    notices: List[str] = Field(default_factory=list)
    single_file_html_path: str = ""

    @property
    def display_reader_name(self) -> str:
        return _extract_clean_reader_name(self.reader_name)

    @property
    def publication_title(self) -> str:
        return compute_publication_title(self.reader_name)

    @property
    def publication_tagline(self) -> str:
        return compute_publication_tagline(self.reader_name)
