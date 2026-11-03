# Implementation Task Breakdown: Your Daily Muse (`tasks.md`)
**Feature ID:** `001-daily-muse` | **Generated:** `2026-10-31` | **Status:** Active  
**Governed by:** [`constitution.md`](file:///c:/Users/Karth/antigravity/Muse%20hackathon/.specify/memory/constitution.md) | **Spec:** [`spec.md`](file:///c:/Users/Karth/antigravity/Muse%20hackathon/.specify/specs/001-daily-muse/spec.md) | **Plan:** [`plan.md`](file:///c:/Users/Karth/antigravity/Muse%20hackathon/.specify/specs/001-daily-muse/plan.md)

> Canonical SpecKit location: [`.specify/specs/001-daily-muse/tasks.md`](file:///c:/Users/Karth/antigravity/Muse%20hackathon/.specify/specs/001-daily-muse/tasks.md)

---

## Phase 1: Day-1 Meta API Spike, Project Setup & Declarative Configurations

- [x] **T001** Initialize Python 3.11+ project structure (`pyproject.toml`, `.env.example`, `.gitignore`) with dependencies: `google-adk`, `litellm`, `fastapi`, `uvicorn`, `pydantic>=2.0`, `httpx`, `trafilatura`, `jinja2`, `apscheduler`, `sqlalchemy`, and `pytest`.
- [x] **T002** [Constitution §2, §6] Build and execute `scripts/spike_meta_adk.py` to verify exact model IDs on `https://api.meta.ai/v1` (`muse-spark`, `muse-image-1.0`, `muse-voice-transcribe-1.0`) and test Google ADK `LiteLlm` with `LlmAgent`, `ParallelAgent`, `LoopAgent`, `output_schema`, and `FunctionTool`.
- [x] **T003** [Constitution §6] Implement `app/agents/meta_model.py` providing `get_muse_model()` with primary ADK `LiteLlm` driver and the Section 15 fallback `MetaMuseBaseLlm(BaseLlm)` adapter controlled by `ADK_META_DRIVER` in `config/settings.py`.
- [x] **T004** [P] [FR-014, FR-015, FR-032] Create declarative format configuration `config/formats.json` defining `bulletin` (`1p/3a`), `daily` (`2p/8a`), and `weekly` (`3..7p/up to 16a`), slot word budgets, minimum verified claims (`3` for `lead`/`feature`, `2` for `secondary`/`brief`), story windows (`+2h` buffer), no-repeat lookback days (`7d` / `28d`), and illustrated slot caps (`1` / `2` / `7`).
- [x] **T005** [P] [FR-029, FR-034] Create single versioned design token file `design/tokens.v1.json` (blackletter masthead font, headline/body serif families, fixed type scale, newsprint light & dark palettes, green/red verification semantic colours, column rule weights) and a deterministic build helper (`app/services/token_compiler.py`) that outputs `app/static/css/tokens.v1.css`.
- [x] **T006** [P] [FR-012, FR-035, FR-038] Implement `config/settings.py` loading LLM API path (`LLM_API_BASE_URL`) and model IDs (`MUSE_TEXT_MODEL`, `MUSE_IMAGE_MODEL`, `MUSE_VOICE_MODEL`) strictly from `.env`, plus constitutional timeouts (`15s` search/image/STT, `20s` LLM), retention limit (`60`), daily build cap (`6`), compressed Demo Mode interval (`120s`), and `DEMO_CACHE_MODE` (`fallback|always|off`).

---

## Phase 2: Foundational Contracts, SQLite Storage & Format Resolver

- [x] **T007** [Principle 5] Implement all stage-boundary Pydantic v2 JSON schemas in `app/models/schemas.py` (`ReaderProfile`, `TopicEditProposal`, `ScheduleState`, `SourceDocument`, `CandidateStory`, `SlotAssignment`, `EditionManifest`, `ClaimRecord`, `DraftIterationOutput`, `PublishedArticle`, `PageRenderModel`, `PublishedEdition`).
- [x] **T008** [FR-001, FR-035] Implement SQLite persistence layer in `app/services/storage.py` (`data/your_daily_muse.db`) creating tables `reader_profile`, `schedule_config`, `build_runs`, `editions`, and `published_story_records`, including the `60-edition` retention pruner and on-disk edition directory manager (`data/editions/`).
- [x] **T009** [FR-014, FR-015, FR-016, US4] Implement `app/services/format_resolver.py` to map reader cadence to `config/formats.json`, compute story lookback windows (`previous_edition + 2h` buffer), and dynamically construct the `3..7` page Weekly layout (guaranteeing `pages >= 3` even for 1 topic or sparse topics, adding reader notices when a topic section page is shortened or omitted).
- [x] **T010** [P] [Principle 8] Create mock JSON stage fixtures in `tests/fixtures/` (`sample_candidates.json`, `sample_draft_poisoned.json`) and implement `scripts/run_stage.py` CLI so every stage can be executed standalone against fixture files.
- [x] **T011** [P] [US4, SC-006] Write unit test `tests/test_format_resolver.py` asserting Bulletin = 1 page / 3 articles, Daily = 2 pages / 8 articles, and Weekly = 3 to 7 pages (strictly `> Daily` across 1 to 5 topics and sparse-topic edge cases).

---

## Phase 3: Stage 1 & 1.5 — Parallel Beat Reporting, Untrusted Content Sanitizer & No-Repeat Dedup (`US1`, `US7`, `US9`)

- [x] **T012** [FR-017, Principle 4] Implement `app/services/search_web.py` supporting Meta `/v1/responses` search grounding with fallback search API, full-text article extraction (`300..8,000` chars), HTML/script stripping, `<untrusted_source_text id="S#">` XML isolation, and curated demo fallback.
- [x] **T013** [FR-017, FR-019, US1, US9] Implement `app/agents/reporters.py` (`ParallelNewsroomReporters`) to run 1 `BeatReporter` per reader topic concurrently, plus the `OutsideTopicsScout` (active on `Daily` and `Weekly`, disabled on `Bulletin`) using optional cached `data/google_trends_snapshot.json` off the critical path.
- [x] **T014** [FR-020, FR-021, US7] Implement deterministic de-duplication and no-repeat filtering in `app/services/dedup.py`:
  - Intra-edition deduplication via canonicalized URL and title/entity shingle Jaccard similarity (`< 0.65`).
  - Cross-edition filtering against SQLite `published_story_records` (`7 days` for Bulletin/Daily; `28 days` for Weekly, allowing `"Follow-up"` flag on Weekly only when new developments exist).
- [x] **T015** [P] [US7, SC-005] Write unit test `tests/test_dedup_and_norepeat.py` verifying duplicate stories from two topics collapse to one, recent stories within 7d/28d are blocked, and Weekly follow-ups are properly flagged.

---

## Phase 4: Stage 2 — Editor-in-Chief Agent & Reserve Queue (`US1`, `US4`, `US9`)

- [x] **T016** [FR-018, FR-019, FR-022, US1, US9] Implement `app/agents/editor.py` (`EditorInChiefAgent`) to rank deduplicated `CandidateStory` items across topics, populate all format slots (`lead`, `secondary`, `feature`, `brief`, and the `outside_topics` slot with its deliberate-choice note), and attach `reserve_candidates` to each slot.
- [x] **T017** [P] [FR-016, FR-037] Add deterministic post-Editor validation in `app/services/format_resolver.py` ensuring that if any topic returned 0 usable stories, the edition still proceeds with remaining topics and appends a plain-language notice to `EditionManifest.omitted_topics_notices`.

---

## Phase 5: Stage 3 — Adversarial Writer–Fact-Checker Loop & Deterministic Gatekeeper (`US2` — Technical Centerpiece)

- [x] **T018** [FR-023, FR-027] Implement the `WriterAgent` logic inside `app/agents/verification_loop.py` to write original journalistic copy adhering to the slot's word-count target (`config/formats.json`), citing `[S#]` sources inline, and incorporating revision instructions on Round 2.
- [x] **T019** [FR-024, FR-025, FR-028] Implement the `FactCheckerAgent` (`temperature=0.0`) and deterministic `approve_article_and_exit_loop` (`tool_context.actions.escalate = True`) inside `app/agents/verification_loop.py` to extract every atomic factual claim, verify entailment strictly against `<untrusted_source_text>`, handle inter-source contradictions (requiring the Writer to state the disagreement or removing the claim per `spec.md` §9), mark claims `verified` / `corrected` / `removed` with notes, and run all slot loops concurrently.
- [x] **T020** [FR-026, FR-028, FR-031, US2] Implement the post-loop deterministic Gatekeeper in `app/services/gatekeeper.py`:
  - Validates that every cited `[S#]` exists in `assigned_candidate.sources`.
  - Strips any sentence containing a claim still unsupported after Round 2, sets `verdict="removed"` with a note, and appends all `corrected` and `removed` claims to `edition.corrections_box`.
  - Enforces minimum verified claims (**3** for `lead`/`feature`, **2** for `secondary`/`brief`); if an article falls short, triggers verification on `slot.reserve_candidates[0]` (or omits the slot with a reader notice if no reserve passes).
- [x] **T021** [P] [US2, SC-002, SC-003] Write `tests/test_gatekeeper_and_loop.py` (including the **Adversarial Poison Test** where an unsupported claim is injected into Round 1, verified as caught/corrected in Round 2 or stripped by the Gatekeeper, listed in `corrections_box`, and reserve substitution triggers when verified claims `< 3` on a Lead slot).

---

## Phase 6: Stage 4 & 5 — Muse Image Illustrator & Unified Multi-Page Publisher (`US5`, `US10`)

- [x] **T022** [FR-032, US10] Implement `app/services/illustrator.py` calling Meta `muse-image-1.0` (`/v1/images/generations`) concurrently for designated illustrated slots (`1` Bulletin, `2` Daily, `<=7` Weekly) using the house engraving/editorial style prompt, prefixing captions with `"Illustration: ..."`, and falling back to a styled house SVG placeholder on timeout (`15s`) or error.
- [x] **T023** [FR-029, FR-030, FR-031, US5] Create shared Jinja2 partials (`app/templates/partials/masthead.html`, `running_header.html`, `article_block.html`, `corrections_box.html`) and the 4 page templates (`app/templates/pages/front.html`, `inside.html`, `section.html`, `closing.html`) using auto-escaping and consuming only `tokens.v1.css`.
- [x] **T024** [P] [FR-029, FR-030, SC-007, SC-009] Create `app/static/css/newspaper.css` implementing the multi-column broadsheet grid, blackletter masthead rules, lead/feature drop-caps, matched dark mode, mobile single-column reflow, and `@media print` rules (hiding UI chrome and printing 1 `.newspaper-page` per physical/PDF sheet).
- [x] **T025** [FR-033, FR-034, US5] Implement `app/services/formatter.py` to render multi-page editions, compute masthead verification totals (`total_claims_checked`, `total_claims_verified`), and generate a self-contained single-file export (`edition_<number>_standalone.html`) with inlined versioned CSS and base64 images so archived editions permanently retain their original `design_version`.
- [x] **T026** [P] [US5, SC-008] Write `tests/test_design_conformance.py` verifying that rendered Bulletin, Daily, and Weekly HTML outputs contain identical mastheads, folios (`"Page X of Y"`), running headers, design version footers, escaped untrusted strings, and print page-break rules.

---

## Phase 7: Autonomous Scheduler, Voice/Text Topic Desk, Archive & Frontend (`US3`, `US6`, `US8`)

- [x] **T027** [FR-001, FR-002, FR-003, US8] Implement `app/services/stt.py` (Meta `Muse Voice Transcribe` `/v1/asr/transcribe` client) and `app/agents/topic_agent.py` (`TopicEditorAgent`) returning `TopicEditProposal` with explicit confirmation workflow and replacement prompt when exceeding 5 topics.
- [x] **T028** [FR-004..013, FR-038, US3] Implement `app/services/scheduler.py` wrapping `AsyncIOScheduler` + SQLite state with:
  - DST-aware `ZoneInfo` local time calculations and next-run preview.
  - Single-build concurrency lock (`FR-008`), post-downtime `coalesce=True` single catch-up (`FR-009`), retry-once (`FR-010`), mid-build config isolation (`FR-011`), `6 builds/day` cap (`FR-012`), and `120s` compressed Demo Mode (`FR-038`).
  - Injectable `clock_fn` for deterministic fake-clock testing.
- [x] **T029** [FR-036, FR-037] Implement `app/services/runner.py` and FastAPI endpoints in `app/main.py` (`GET /`, `GET /api/status`, `GET /api/editions`, `GET /api/editions/{id}`, `GET /api/editions/{id}/download`, `POST /api/editions/generate-now`, `POST /api/topics/propose`, `POST /api/topics/confirm`, `POST /api/topics/voice`, `POST /api/schedule/preview`, `POST /api/schedule`).
- [x] **T030** [P] [FR-013, FR-035, FR-036, US6] Build plain HTML/JS frontend (`app/templates/app_shell.html`, `app/static/js/app.js`, `app/static/js/voice.js`, `app/static/js/tts.js`) providing live build progress, `"New edition available"` banner, Topic & Voice editor with confirmation/replacement modal, Schedule & Demo Mode controls, Archive drawer filterable by format, and Browser `SpeechSynthesis` TTS reader.
- [x] **T031** [P] [US3, SC-004, SC-005, SC-012] Write `tests/test_scheduler_fake_clock.py` testing `scheduler.py` against a fake clock across DST changes, overlapping due times (0 double builds), multi-slot downtime (at most 1 catch-up), retry-once on failure, 6-build daily cap block, and 2-minute Demo Mode auto-trigger.

---

## Phase 8: Sample Archive Seeding & End-to-End Reliability Verification (`FR-038`, `SC-001..012`)

- [x] **T032** [FR-038, SC-003, SC-007] Implement `scripts/seed_sample_archive.py` populating 3 complete, realistic sample editions (**1 Bulletin**, **1 Daily**, **1 Weekly**) including verified claims, Round-2 correction/removal in the Corrections Box (`SC-003`), house illustrations, and standalone HTML exports.
- [x] **T033** [SC-001..012] Run full verification test suite (`pytest`) and verify automatic archive seeding, side-by-side Bulletin/Daily/Weekly design identity parity, voice topic confirmation, and Demo Mode scheduling.

---

## Phase 9: SAM-3 Blank-Space Segmentation & Whitespace Creative Agent (`FR-039` – `FR-044`, `Story 11`, `SC-013`)

- [x] **T034** [P] [FR-039, FR-040, Principle 5] Extend `app/models/schemas.py` to define `WhitespaceSizeTier` (`compact`, `column`, `banner`), `WhitespaceFillerType` (`comic_joke`, `epigram_wit`, `muse_brief_ad`), `WhitespaceRegion`, and `WhitespaceFillerItem` Pydantic models, and update `PageRenderModel` to carry `whitespace_fillers: List[WhitespaceFillerItem]`.
- [x] **T035** [FR-039, FR-040, FR-044, Principle 2] Implement `app/services/sam_layout_analyzer.py` (`SamLayoutAnalyzer`):
  - Ingests page layout canvas or layout render snapshot.
  - Calls Meta SAM-3 (`sam-3.1`) via `POST /v1/responses` with promptable concept segmentation (`"blank paper whitespace"`, `"printed text column"`).
  - Classifies detected whitespace into size tiers (`compact`, `column`, `banner`) with aspect ratio, column span, and `< 8%` density guard.
  - Implements deterministic CSS grid remainder fallback (`12 - sum(column_spans)`) when offline or on timeout (`15s`).
- [x] **T036** [FR-041, FR-042, FR-043, Principle 3] Implement `app/agents/whitespace_agent.py` (`WhitespaceCreativeAgent`):
  - Uses Google ADK `LlmAgent` + `MUSE_TEXT_MODEL` (`muse-spark`).
  - Evaluates page blank spaces with Balanced Cadence-Aware Allocation (Front & Section -> comic jokes; Inside & Closing -> Muse Newz house ads).
  - Generates topic-specific satirical comic commentary lampooning the edition's researched topics (*The Mechanical Muse* / *The Newsroom Dispatches*) or "The Muse Newz" ad copy.
  - Coordinates live generation of satirical monochrome woodcut engravings via `muse-image-1.0` with cached demo fallback (`data/demo_cache/images/`).
- [x] **T037** [FR-041, FR-042, FR-043, Principle 6] Wire Stage 4b (SAM-3 analysis) and Stage 4c (Whitespace Creative Agent) into `app/services/runner.py` pipeline and update `app/services/formatter.py` + Jinja2 templates (`front.html`, `inside.html`, `section.html`, `closing.html`, `comic_strip_box.html`, `house_ad_box.html`, `curiosities_box.html`) to render dynamic whitespace fillers without layout overflow.
- [x] **T038** [P] [SC-013, Principle 8] Write unit and integration test suite in `tests/test_sam3_whitespace_agent.py`:
  - Validates SAM-3 promptable concept segmentation response parsing and bounding-box size-tier classification.
  - Tests CSS grid remainder fallback when SAM-3 endpoint is offline or times out.
  - Verifies topic-specific satirical comic copy generation and Muse Newz ad copy generation.
  - Validates that no duplicate filler items are placed adjacently and that `< 8%` whitespace pages are left uncluttered.
- [x] **T039** [FR-044, CHK-C01, Principle 1] Update `scripts/generate_comic_assets.py` and ensure `data/demo_cache/` contains pre-generated topic-specific and newsroom woodcut engravings for live hackathon demo resilience under `DEMO_CACHE_MODE=fallback`.

---

## Phase 10: Centrepiece Most-Mentioned News, Zero Duplicate News/Images, Web/PDF/HTML Alignment & Geographic Preference (`FR-045`–`FR-048`, Decisions #13–#16)

- [x] **T040** [FR-045, FR-048, Decision #15 & #16] Extend `ReaderProfile`, `PublishedEdition`, `TopicEditProposal`, `CandidateStory`, `PublishedArticle`, `WhitespaceRegion`, and `WhitespaceFillerItem` in `app/models/schemas.py` with `geographic_preference`, `mention_count`, and `layout_orientation` / `orientation`, and migrate SQLite `reader_profile` in `app/services/storage.py`.
- [x] **T041** [FR-045, Decision #15] Implement multi-source `mention_count` clustering in `app/services/search_web.py` and `app/services/dedup.py`, weight `mention_count` in `score_editorial_newsworthiness` (`app/agents/editor.py`) and `normalize_edition_layout_and_centrepiece` (`app/services/formatter.py`), and generate/register the dedicated `$6.3B Binance Crypto Heist` woodcut illustration (`data/demo_cache/images/binance_crypto_heist_6b.png`) + unique comic plates (`comic_vault_audit.png`, `comic_telegraph_race.png`).
- [x] **T042** [FR-046, Decision #13] Eliminate duplicate news stories (replacing `"Analysis: ..."` clones with unused curated dispatches) and enforce edition-wide image & filler deduplication (`used_hashes`, `used_filler_keys`, `used_filler_paths`) in `app/agents/editor.py`, `app/agents/whitespace_agent.py`, and `app/services/formatter.py`.
- [x] **T043** [FR-047, Decision #14] Align Web, Print/PDF (`@media print` & `@page`), and Standalone HTML 12-column grids in `app/static/css/newspaper.css`, `app/templates/pages/front.html`, `app/templates/pages/inside.html`, `app/templates/partials/article_block.html`, `app/templates/partials/comic_strip_box.html`, and `app/templates/partials/house_ad_box.html` with `layout-horizontal` and `layout-vertical` space formatting.
- [x] **T044** [FR-048, Decision #16] Wire `geographic_preference` end-to-end across `app/agents/topic_agent.py`, `app/agents/reporters.py`, `app/services/runner.py`, `app/main.py`, `app/templates/partials/masthead.html`, `app/templates/app_shell.html`, and `app/static/js/app.js`, and verify all 4 stored editions and automated tests.
- [x] **T045** [FR-049, FR-050, SC-017, Decision #17] Implement dynamic reader-named newspaper masthead (`The [Name] Courier`, fallback `The Muse Courier`) and tagline (`“Made for [Name]. Checked before print.”`, fallback `“Made for Muse. Checked before print.”`) across `app/models/schemas.py`, `app/templates/partials/masthead.html`, `app/templates/partials/running_header.html`, `app/templates/pages/*.html`, `app/templates/edition_standalone.html`, `app/templates/app_shell.html`, `app/main.py`, and tests.
- [x] **T046** [FR-051, SC-018, Decision #18] Enforce strict topic and section semantic integrity (`is_story_relevant_to_topic`), separate `Finance & Global Markets`, `Crypto & Digital Assets`, and `Movies & Cinema` curated dispatch pools (`4` stories each) in `app/services/search_web.py`, prevent cross-topic fallback contamination in `app/agents/editor.py` and `app/services/formatter.py`, and tighten `app/services/dedup.py` to prevent country-only false merges.
- [x] **T047** [FR-052, SC-019, Decision #19] Generate fresh per-edition Victorian woodcut PNG illustrations via `build_bespoke_woodcut_png` and `_get_historically_used_image_hashes` in `app/services/illustrator.py`, expand illustrated article slots in `config/formats.json` (`p1_lead`, `p1_sec_1`, `p1_outside`, `p2_brief_1` in Daily; `wk_p1_lead`, `wk_p1_sec_1`, `wk_sec_{i}_feature`, `wk_closing_outside` in Weekly), and install new woodcut plates (`movies_70mm_cinema.png`, `movies_film_festival.png`, `finance_central_bank.png`, `finance_fintech_ipo.png`, `crypto_zk_settlement.png`).
- [x] **T048** [FR-053, SC-020, Decision #20] Add topic-matched comic strips (`comic_cinema_critic.png`, `comic_market_oracle.png`, `comic_vault_audit.png`) and rotating per-edition dialogues/epigrams (`select_topic_matched_comic`) in `app/agents/whitespace_agent.py`, `app/services/runner.py`, and `app/services/formatter.py`, and upgrade all stored editions in `data/editions/` and `data/your_daily_muse.db`.
