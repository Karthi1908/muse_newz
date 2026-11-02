# SpecKit Quality & Conformance Checklist: Your Daily Muse (`checklists/requirements.md`)
**Feature ID:** `001-daily-muse` | **Generated:** `2026-10-31`  
**Scope:** Pre-implementation quality gate validating [`constitution.md`](file:///c:/Users/Karth/antigravity/Muse%20hackathon/.specify/memory/constitution.md), [`spec.md`](file:///c:/Users/Karth/antigravity/Muse%20hackathon/.specify/specs/001-daily-muse/spec.md), and [`plan.md`](file:///c:/Users/Karth/antigravity/Muse%20hackathon/.specify/specs/001-daily-muse/plan.md).

---

## 1. Constitutional Compliance Checklist (Principles 1–8)

- [x] **CHK-C01 (Principle 1 — Demo Reliability):** Does every external call (Meta LLM, Meta Grounding/Search, URL Scraping, Meta Image, Meta STT) specify an explicit timeout, a deterministic fallback, and a cached demo fixture (`data/demo_cache/`)? *(Verified in `constitution.md` §4 G-4.1 & `plan.md` §1, §5)*
- [x] **CHK-C02 (Principle 2 — Deterministic Where Possible):** Are scheduling, format sizing, layout, schema validation, loop exit, claim stripping, and de-duplication handled in deterministic Python code rather than LLM output? *(Verified in `plan.md` §1, §6.2–§6.5)*
- [x] **CHK-C03 (Principle 3 — Agents Only Where Decisions Are Made):** Are Google ADK agents restricted strictly to Topic Editing, Beat Reporting, Editorial Selection, Writing, and Fact-Checking, while Images, Publishing, Speech (STT/TTS), and Scheduling are implemented as deterministic tools/services? *(Verified in `constitution.md` §3 & `plan.md` §1)*
- [x] **CHK-C04 (Principle 4 — Untrusted Content Stays Data):** Is all scraped web text stripped of HTML/scripts, wrapped in `<untrusted_source_text>` delimiters, excluded from instruction roles, and is all output HTML-escaped via `autoescape=True` / `html.escape`? *(Verified in `constitution.md` §4 G-2.1/G-2.2 & `plan.md` §6.3, §6.5)*
- [x] **CHK-C05 (Principle 5 — Structured Contracts Between Stages):** Does every pipeline stage read and write validated Pydantic v2 JSON models (`ReaderProfile`, `CandidateStory`, `EditionManifest`, `DraftIterationOutput`, `PublishedArticle`, `PublishedEdition`)? *(Verified in `plan.md` §4)*
- [x] **CHK-C06 (Principle 6 — One Design, Many Formats):** Does visual appearance come exclusively from a single versioned token set (`design/tokens.v1.json` $\rightarrow$ `tokens.v1.css`) and shared partials (`templates/partials/`), with zero custom colours/fonts/mastheads in format templates? *(Verified in `spec.md` §5 & `plan.md` §6.5)*
- [x] **CHK-C07 (Principle 7 — Formats Are Data):** Do page counts, article counts, slot types, and lookback windows live in declarative configuration (`config/formats.json`) with zero hardcoded format branches? *(Verified in `plan.md` §3)*
- [x] **CHK-C08 (Principle 8 — Small and Testable):** Can each stage run standalone via `scripts/run_stage.py` against mock JSON fixtures (`tests/fixtures/`), and does the scheduler accept an injectable fake clock? *(Verified in `plan.md` §1, §7)*

---

## 2. Requirements Completeness & Clarity Checklist (`FR-001` to `FR-038`)

### 2.1 Topics & Voice/Text Input (`FR-001` – `FR-003`)
- [x] **CHK-R01:** Topic count bounded strictly to `1..5` active topics (`FR-001`).
- [x] **CHK-R02:** Voice input via Meta `Muse Voice Transcribe` converts speech to the exact same `TopicEditProposal` contract as text input, showing the heard transcript on unclear/empty speech (`FR-002`, `Story 8`).
- [x] **CHK-R03:** Topic updates display the proposed list and require explicit reader confirmation before saving; attempts to add a 6th topic prompt the reader to choose which existing topic to replace (`FR-003`, `Story 8`).

### 2.2 Scheduling, Concurrency & Resilience (`FR-004` – `FR-013`)
- [x] **CHK-R04:** Supports all 5 cadences (`every_4h`, `every_8h`, `every_12h`, `daily`, `weekly`) with start time, DST-aware IANA time zone, weekday (for weekly), and next-run preview (`FR-004`, `FR-005`).
- [x] **CHK-R05:** Automatic unattended execution at due times, plus pause, resume, change, delete, and manual `"Generate now"` (`FR-006`, `FR-007`).
- [x] **CHK-R06:** Single-build concurrency lock prevents overlapping builds for the same reader; overlapping triggers are skipped and logged (`FR-008`, `SC-005`).
- [x] **CHK-R07:** Post-downtime recovery triggers at most **1** catch-up edition (`coalesce=True`) (`FR-009`).
- [x] **CHK-R08:** Failed builds retry automatically **once** (`attempt=2`); on second failure, plain-language reason is shown, previous edition stays readable, and schedule continues (`FR-010`).
- [x] **CHK-R09:** In-flight builds snapshot topics and cadence at start so mid-build setting edits apply only to subsequent builds (`FR-011`).
- [x] **CHK-R10:** Enforces daily build cap (`6 builds/day` default) across scheduled and manual builds with reader notice (`FR-012`).
- [x] **CHK-R11:** Displays a `"New edition available"` indicator upon build completion (`FR-013`).

### 2.3 Edition Formats & Weekly Page Invariant (`FR-014` – `FR-016`)
- [x] **CHK-R12:** Format sizing resolved strictly from `config/formats.json`: Bulletin (`1p, 3a`), Daily (`2p, 8a`), Weekly (`3..7p, up to 16a`) (`FR-014`).
- [x] **CHK-R13:** Weekly edition always produces strictly more pages than Daily (`3..7 pages` vs `2 pages`) for any topic count from `1` to `5` (`FR-015`, `SC-006`).
- [x] **CHK-R14:** Sparse topics on Weekly either shorten or omit their section page with an explicit reader notice while maintaining the `>= 3 pages` floor (`FR-016`).

### 2.4 Parallel Research, Outside-Topics & No-Repeat Rules (`FR-017` – `FR-022`)
- [x] **CHK-R15:** Parallel independent topic searches over the format's story window (`since previous edition + 2h buffer`; `7d + 2h` for Weekly) recording headline, summary, source name, URL, and date (`FR-017`).
- [x] **CHK-R16:** Cross-topic ranking fills `lead`, `secondary`, `brief`, and `feature` slots while holding `reserve_candidates` (`FR-018`, `FR-022`).
- [x] **CHK-R17:** Exactly `1` labelled outside-topics story in `Daily` and `Weekly` editions; `0` in `Bulletin` (`FR-019`, `Story 9`).
- [x] **CHK-R18:** Intra-edition de-duplication prevents two articles on the same underlying story (`FR-020`).
- [x] **CHK-R19:** Cross-edition no-repeat check via `published_story_records` (`7d` lookback for Bulletin/Daily; `28d` for Weekly, permitting `"Follow-up"` badge only on materially new developments) (`FR-021`, `SC-005`).

### 2.5 Adversarial Writing, Verification Loop & Gatekeeper (`FR-023` – `FR-028`)
- [x] **CHK-R20:** Original article drafting sized to slot word bounds with inline `[S#]` source citations (`FR-023`, `FR-027`).
- [x] **CHK-R21:** Claim decomposition and entailment verification against verbatim scraped source text inside a 2-round `LoopAgent` (`FR-024`, `FR-025`).
- [x] **CHK-R22:** Post-Round-2 deterministic Gatekeeper strips any remaining unsupported claims (`verdict="removed"`), enforces slot minimum verified claims (**3** for `lead`/`feature`, **2** for `secondary`/`brief`), and substitutes a verified reserve story (or omits with notice) if below threshold (`FR-026`).
- [x] **CHK-R23:** Per-claim verdict (`verified`, `corrected`, `removed`), source link, and explanatory note persisted for the expandable article audit view, masthead verification counter, and edition Corrections Box (`FR-028`, `FR-031`, `SC-002`, `SC-003`).

### 2.6 Newspaper Design Identity, Archive & Demo Reliability (`FR-029` – `FR-038`)
- [x] **CHK-R24:** Conformance to all fixed design elements in `spec.md` §5: blackletter `"Your Daily Muse"` masthead, edition line, single headline/body font pair, drop-cap on lead/feature only, newsprint + dark mode palette, green/red reserved strictly for fact-check state, folio (`"Page X of Y"`), running header, and design version footer (`FR-029`, `FR-030`, `FR-034`, `SC-007`, `SC-008`).
- [x] **CHK-R25:** House-style illustrations (`muse-image-1.0`) captioned as `"Illustration: ..."` on designated slots (`1` Bulletin, `2` Daily, `<=7` Weekly) with styled SVG fallback (`FR-032`, `Story 10`).
- [x] **CHK-R26:** Print stylesheet (`@media print` one page per sheet, UI controls hidden) and single-file self-contained HTML export preserving the edition's original `design_version` (`FR-030`, `FR-033`, `FR-034`, `SC-009`).
- [x] **CHK-R27:** Archive stores up to `60` editions newest-first, filterable by format (`FR-035`, `Story 6`).
- [x] **CHK-R28:** Live build progress indicator (`FR-036`), graceful stage degradation with reader notices (`FR-037`, `SC-011`), pre-seeded archive with 3 sample editions (`Bulletin`, `Daily`, `Weekly`), and `2-minute` compressed Demo Mode (`FR-038`, `SC-012`).

### 2.7 Blank-Space Segmentation (`SAM 3`) & Whitespace Creative Agent (`FR-039` – `FR-044`)
- [x] **CHK-R29:** Page layout blank spaces are captured via Hybrid DOM-to-Canvas / server snapshot and analyzed using Meta's Segment Anything Model (`sam-3` / `sam-3.1`) via `POST /v1/responses` with promptable concept segmentation (`"blank paper whitespace"`, `"printed text column"`), falling back to deterministic CSS grid remainder geometry when offline (`FR-039`, `Story 11`, Decision #9).
- [x] **CHK-R30:** Detected blank spaces are classified into `compact`, `column`, or `banner` tiers based on segmented dimensions, allocating satirical comics to Front/Section pages and "Your Muse Brief" ads to Inside/Closing pages; pages with `< 8%` free area skip filler injection (`FR-040`, `FR-041`, Decision #10).
- [x] **CHK-R31:** Dedicated `WhitespaceCreativeAgent` (`LlmAgent`) crafts topic-specific satirical comic commentary and dialogue lampooning the edition's researched topics or "Your Muse Brief" house ads without adjacent duplicate fillers (`FR-041`, `FR-042`, Decision #12).
- [x] **CHK-R32:** For column and banner spaces, the system performs full live generation of custom comic copy and brand-new woodcut illustrations via `muse-image-1.0`, backed by `15s` timeouts and cached demo fallbacks (`FR-043`, `FR-044`, `CHK-C01`, Decision #11).
