from __future__ import annotations
import asyncio
import logging
from typing import List, Optional
import httpx
from config.settings import settings
from app.models.schemas import WhitespaceRegion, WhitespaceSizeTier

logger = logging.getLogger(__name__)


def classify_whitespace_tier(
    width: int,
    height: int,
    column_span: int,
    area_ratio: float,
) -> WhitespaceSizeTier:
    """
    Classifies a detected whitespace bounding box into structural size tiers:
    - 'compact': < 220px height or single-column tail gap (< 3 col span).
    - 'banner': wide aspect ratio (width / height >= 2.2) or >= 8 column span.
    - 'column': standard 4-column vertical/square broadsheet slot.
    """
    aspect = width / max(height, 1)
    if column_span >= 8 or (aspect >= 2.1 and width >= 500):
        return "banner"
    if height < 220 or (column_span <= 3 and height < 320):
        return "compact"
    return "column"


def compute_grid_fallback_regions(
    template: str,
    page_number: int,
    articles_count: int,
    format_name: str,
) -> List[WhitespaceRegion]:
    """
    Deterministic CSS grid remainder geometry calculator.
    Used when SAM-3 endpoint is offline, times out, or when running in cached demo mode.
    Guarantees page layout is mathematically balanced with no awkward empty whitespace.
    """
    regions: List[WhitespaceRegion] = []
    tmpl = template.lower()

    if tmpl == "front":
        if articles_count >= 4:
            # 3-Column Broadsheet Front Page (Left Wing 3 cols | Centrepiece 6 cols | Right Wing 3 cols):
            # - Right wing needs a Comic Strip + Compact Epigram to match Centrepiece height.
            # - Left wing needs a House Ad below sec_1 + brief_1 to match Centrepiece height.
            regions.append(
                WhitespaceRegion(
                    region_id=f"ws_p{page_number}_front_right_comic",
                    page_number=page_number,
                    bbox=[900, 420, 280, 420],
                    area_ratio=0.14,
                    aspect_ratio=280 / 420,
                    column_span=3,
                    size_tier="column",
                    detection_source="grid_fallback",
                )
            )
            regions.append(
                WhitespaceRegion(
                    region_id=f"ws_p{page_number}_front_left_ad",
                    page_number=page_number,
                    bbox=[40, 680, 280, 380],
                    area_ratio=0.12,
                    aspect_ratio=280 / 380,
                    column_span=3,
                    size_tier="column",
                    detection_source="grid_fallback",
                )
            )
            regions.append(
                WhitespaceRegion(
                    region_id=f"ws_p{page_number}_front_right_wit",
                    page_number=page_number,
                    bbox=[900, 860, 280, 210],
                    area_ratio=0.09,
                    aspect_ratio=280 / 210,
                    column_span=3,
                    size_tier="compact",
                    detection_source="grid_fallback",
                )
            )
        else:
            # Bulletin Front Page (Centrepiece 7 cols | Right Dispatch Column 5 cols)
            regions.append(
                WhitespaceRegion(
                    region_id=f"ws_p{page_number}_front_col",
                    page_number=page_number,
                    bbox=[700, 520, 460, 440],
                    area_ratio=0.16,
                    aspect_ratio=460 / 440,
                    column_span=5,
                    size_tier="column",
                    detection_source="grid_fallback",
                )
            )
            regions.append(
                WhitespaceRegion(
                    region_id=f"ws_p{page_number}_front_lead_wit",
                    page_number=page_number,
                    bbox=[40, 820, 640, 190],
                    area_ratio=0.09,
                    aspect_ratio=640 / 190,
                    column_span=7,
                    size_tier="compact",
                    detection_source="grid_fallback",
                )
            )
    elif tmpl == "inside":
        # Inside Page: 12-column grid with 3 briefs per row (4 cols each).
        rem = articles_count % 3
        if rem == 1:
            # 1 brief in last row -> 8 columns open -> 1 column slot (4 cols) + 1 compact slot (4 cols)
            regions.append(
                WhitespaceRegion(
                    region_id=f"ws_p{page_number}_inside_col4",
                    page_number=page_number,
                    bbox=[400, 600, 360, 420],
                    area_ratio=0.14,
                    aspect_ratio=360 / 420,
                    column_span=4,
                    size_tier="column",
                    detection_source="grid_fallback",
                )
            )
            regions.append(
                WhitespaceRegion(
                    region_id=f"ws_p{page_number}_inside_compact4",
                    page_number=page_number,
                    bbox=[780, 600, 360, 200],
                    area_ratio=0.09,
                    aspect_ratio=360 / 200,
                    column_span=4,
                    size_tier="compact",
                    detection_source="grid_fallback",
                )
            )
        elif rem == 2:
            # 2 briefs in last row -> 4 columns open -> 1 column slot
            regions.append(
                WhitespaceRegion(
                    region_id=f"ws_p{page_number}_inside_col4",
                    page_number=page_number,
                    bbox=[780, 600, 360, 420],
                    area_ratio=0.14,
                    aspect_ratio=360 / 420,
                    column_span=4,
                    size_tier="column",
                    detection_source="grid_fallback",
                )
            )
        else:
            # Full row of 3 briefs -> Side-by-side Comic Strip (6 cols) + The Muse Newz Ad (6 cols) before corrections
            regions.append(
                WhitespaceRegion(
                    region_id=f"ws_p{page_number}_inside_banner",
                    page_number=page_number,
                    bbox=[40, 640, 550, 320],
                    area_ratio=0.14,
                    aspect_ratio=550 / 320,
                    column_span=6,
                    size_tier="banner",
                    detection_source="grid_fallback",
                )
            )
            regions.append(
                WhitespaceRegion(
                    region_id=f"ws_p{page_number}_inside_ad_half",
                    page_number=page_number,
                    bbox=[610, 640, 550, 320],
                    area_ratio=0.14,
                    aspect_ratio=550 / 320,
                    column_span=6,
                    size_tier="column",
                    detection_source="grid_fallback",
                )
            )
    elif tmpl == "section":
        # Section Page: 1 Feature (7 cols) + 1 Brief (5 cols), right column stacks Comic + Epigram to match feature height.
        regions.append(
            WhitespaceRegion(
                region_id=f"ws_p{page_number}_sec_col",
                page_number=page_number,
                bbox=[700, 440, 460, 420],
                area_ratio=0.15,
                aspect_ratio=460 / 420,
                column_span=5,
                size_tier="column",
                detection_source="grid_fallback",
            )
        )
        regions.append(
            WhitespaceRegion(
                region_id=f"ws_p{page_number}_sec_wit",
                page_number=page_number,
                bbox=[700, 880, 460, 200],
                area_ratio=0.09,
                aspect_ratio=460 / 200,
                column_span=5,
                size_tier="compact",
                detection_source="grid_fallback",
            )
        )
    elif tmpl == "closing":
        # Closing Page: Feature + Corrections + Sources index, with horizontal banner space.
        regions.append(
            WhitespaceRegion(
                region_id=f"ws_p{page_number}_closing_banner",
                page_number=page_number,
                bbox=[40, 580, 1120, 220],
                area_ratio=0.15,
                aspect_ratio=1120 / 220,
                column_span=12,
                size_tier="banner",
                detection_source="grid_fallback",
            )
        )

    # Density guard: filter out any region below 8% page area ratio (FR-040)
    out_regions: List[WhitespaceRegion] = []
    for r in regions:
        if r.area_ratio >= 0.08:
            orient = "horizontal" if (r.size_tier == "banner" or r.column_span >= 6 or r.aspect_ratio >= 1.35) else "vertical"
            out_regions.append(r.model_copy(update={"orientation": orient}))
    return out_regions


class SamLayoutAnalyzer:
    """
    Meta Segment Anything Model (SAM-3 / SAM-3.1) Page Whitespace Analyzer.
    (Spec §7 FR-039..FR-044, Story 11, SC-013, Constitution Principle 1 & 2).
    """

    def __init__(self, timeout: float | None = None) -> None:
        self.timeout = timeout or settings.SAM_TIMEOUT_SECONDS

    async def analyze_page_whitespace(
        self,
        page_number: int,
        template: str,
        format_name: str,
        articles_count: int,
        layout_image_b64: Optional[str] = None,
    ) -> List[WhitespaceRegion]:
        """
        Analyzes the unallocated whitespace regions of a newspaper page canvas.
        Attempts promptable concept segmentation via SAM-3 (POST /v1/responses).
        If offline, timed out, or image is unavailable, falls back gracefully
        to deterministic CSS grid remainder calculations.
        """
        if settings.has_live_api_key and layout_image_b64:
            try:
                headers = {
                    "Authorization": f"Bearer {settings.MODEL_API_KEY}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": settings.MUSE_SAM_MODEL,
                    "prompt": (
                        "Detect and segment all blank paper whitespace, empty editorial columns, "
                        "and unallocated advertisement boxes on this newspaper page layout. "
                        "Return bounding boxes in [x, y, width, height] format."
                    ),
                    "input_image": layout_image_b64,
                }
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(settings.responses_url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        regions = self._parse_sam_response(data, page_number)
                        if regions:
                            logger.info(
                                "SAM-3 successfully segmented %d whitespace region(s) on page %d",
                                len(regions),
                                page_number,
                            )
                            return regions
            except Exception as exc:
                logger.warning(
                    "SAM-3 segmentation failed for page %d (%s), using deterministic grid fallback: %s",
                    page_number,
                    type(exc).__name__,
                    exc,
                )

        # Fallback to deterministic grid geometry (Principle 1 & 2, FR-044)
        return compute_grid_fallback_regions(
            template=template,
            page_number=page_number,
            articles_count=articles_count,
            format_name=format_name,
        )

    def _parse_sam_response(self, data: dict, page_number: int) -> List[WhitespaceRegion]:
        """Parses SAM-3 /sam-3.1 response JSON for detected whitespace bounding boxes."""
        parsed: List[WhitespaceRegion] = []
        boxes = []

        if isinstance(data, dict):
            if "regions" in data and isinstance(data["regions"], list):
                boxes = data["regions"]
            elif "data" in data and isinstance(data["data"], list):
                boxes = data["data"]
            elif "output" in data and isinstance(data["output"], dict):
                boxes = data["output"].get("bounding_boxes", [])

        # Typical reference canvas size for desktop broadsheet: 1200 x 1600 px
        canvas_area = 1200 * 1600

        for idx, item in enumerate(boxes):
            bbox = None
            if isinstance(item, dict) and "bbox" in item:
                bbox = item["bbox"]
            elif isinstance(item, list) and len(item) == 4:
                bbox = item

            if bbox and len(bbox) == 4:
                x, y, w, h = [int(v) for v in bbox]
                area = w * h
                area_ratio = round(area / canvas_area, 3)

                # Density guard: ignore tiny slivers (< 8% page area)
                if area_ratio < 0.08:
                    continue

                col_span = max(1, min(12, int(round((w / 1200) * 12))))
                tier = classify_whitespace_tier(w, h, col_span, area_ratio)
                aspect = round(w / max(h, 1), 2)
                orient = "horizontal" if (tier == "banner" or col_span >= 6 or aspect >= 1.35) else "vertical"

                parsed.append(
                    WhitespaceRegion(
                        region_id=f"ws_sam3_p{page_number}_{idx}",
                        page_number=page_number,
                        bbox=[x, y, w, h],
                        area_ratio=area_ratio,
                        aspect_ratio=aspect,
                        column_span=col_span,
                        size_tier=tier,
                        orientation=orient,
                        detection_source="sam-3",
                    )
                )

        return parsed
