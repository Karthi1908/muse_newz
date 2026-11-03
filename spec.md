# Functional Specification: The [Name] Courier / The Muse Courier (`spec.md`)
**Feature ID:** `001-daily-muse` | **Status:** Clarified & Locked (`2026-11-01`) | **Governed by:** [`.specify/memory/constitution.md`](file:///c:/Users/Karth/antigravity/Muse%20hackathon/.specify/memory/constitution.md)

---

## 1. Summary

A reader picks up to five topics and a delivery rhythm. From then on, the product builds a newspaper on that rhythm without being asked. For each edition it researches fresh stories on the reader's topics, picks the best, writes original articles, checks every factual claim against the cited source, illustrates the stories, and presents the result as a newspaper that always looks like the same publication. Anything the fact-checker cannot support is visibly corrected or removed. The reader can browse, print, and revisit past editions.

---

## 2. Problem and Motivation

- News apps rank by what is popular, not by what is relevant and trustworthy for one person.
- AI summaries often state unsupported claims with confidence, and readers cannot tell which were checked.
- Personalised feeds narrow what people see over time.
- Readers differ in how often they want to catch up: some want a short update several times a day, others a thorough weekend read.

### Differentiators (Shaping Priorities Below)
1. **Verification is visible:** Per-claim verdicts, source links, and a corrections box.
2. **A deliberate "outside your usual reading" story** in editions large enough to carry it.
3. **A real newspaper with a consistent identity**, sized to the reader's rhythm, not a feed.

---

## 3. Users

- **Primary Persona — The Busy Topic Follower:** Follows 3 to 5 areas. Wants a short update at set times, or one thorough read a week. Distrusts AI summaries that cite nothing.

---

## 4. Edition Formats and Cadence

The reader chooses a cadence. The cadence decides the format. Formats are defined in one configuration table so sizes can be tuned without redesigning anything.

| Format | Cadences | Pages | Articles | Page Contents | Outside-Topics Story | Story Window |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bulletin** | `every 4 h`, `every 8 h` | `1` | `3` | **Front page:** 1 lead, 2 briefs | No (too short) | Since the previous edition, plus a small buffer |
| **Daily** | `every 12 h`, `daily (24 h)` | `2` | `8` | **Page 1 front:** 1 lead, 2 secondary, 2 briefs (one is the outside story). **Page 2 inside:** 3 briefs | Yes, `1` | Since the previous edition, plus a buffer |
| **Weekly** | `weekly` | Up to `7` (minimum `3`) | Up to `16` | **Front page** (5 top stories of the week), **one section page per topic** (1 feature + 1 brief), **closing page** (outside-topics feature, week's corrections, sources) | Yes, `1` (feature) | Past 7 days |

### Format & Continuity Rules
1. A **Weekly** edition always has more pages than a **Daily** edition, for any number of topics from 1 to 5 (`3` to `7` pages versus `2`).
2. If a topic has too little material for a section page, that page is shortened or left out, and the reader is told. The total still never falls below `3` pages for a Weekly edition (front, at least one section page, closing page).
3. Stories already published in recent editions are not repeated, except as clearly labelled follow-ups in Weekly editions when there is a materially new development.

---

## 5. Newspaper Design Identity (Must Be Maintained)

Every edition, in every format, on every device, in print, and in the archive, must read as the same publication.

### Fixed Elements
- **Masthead & Dynamic Reader Title:** The newspaper masthead takes the reader's name in the form **"The [Name] Courier"** (for example, **"The Aisha Courier"**)—reading like an established broadsheet (*The Boston Globe*, *The Hindu*), where the reader is the title—set in the same blackletter, same rules, and same placement on every Page 1 across all formats (`Bulletin`, `Daily`, `Weekly`), with a matching running header on inside, section, and closing pages. If no reader name is set yet (empty or unset), the masthead title falls back to **"The Muse Courier"**.
- **Masthead Tagline:** Directly beneath the blackletter masthead, the motto/tagline reads **“Made for [Name]. Checked before print.”** (for example, **“Made for Aisha. Checked before print.”**, or **“Made for Muse. Checked before print.”** when falling back to *The Muse Courier*).
- **Edition Line:** Date, edition number (continuing across all formats for that reader), format label (`Bulletin`, `Daily`, `Weekly`), reader name, and geographic preference.
- **Typography:** One headline family, one body family, one fixed type scale; drop cap on lead stories only.
- **Colour:** One newsprint palette with a matched dark mode; green for verified and red for corrected or removed, used only for fact-check state.
- **Grid and Rules:** Same column structure, rule weights, spacing.
- **Page Furniture:** Folio (`"Page 2 of 7"`) and section flag on every page; date and edition in the running header.
- **Article Furniture:** Topic label, headline, deck, byline, fact-check summary, source line.
- **Images:** Same illustration treatment (style, tone, caption wording stating it is an illustration).
- **Fact-Check Presentation:** Same badge, same expandable claim list, same corrections box.

### Allowed to Vary
- Page count, which page templates appear (`front`, `inside`, `section`, `closing`), number of articles, and the content.

### Versioning
- The design has a version number shown in the footer of every edition. Design changes are deliberate and apply to all formats together.

---

## 6. User Scenarios and Acceptance Criteria

### Story 1: Get a Personalised Edition (Priority: P1)
> *As a reader, I receive a newspaper built from current stories on my topics.*

**Acceptance Scenarios:**
- **Given** a reader with 1 to 5 topics, **when** an edition is built, **then** it contains the number of articles and pages its format calls for, each article tagged with topic, headline, byline, body, and source links.
- **Given** a topic with no recent stories, **when** an edition is built, **then** it still publishes with the other topics and says which topic had nothing new.
- **Given** an edition is being built, **when** the reader looks at the app, **then** they see progress, not a blank screen.

### Story 2: See What Was Fact-Checked (Priority: P1)
**Acceptance Scenarios:**
- **Given** a published article, **when** the reader opens its fact-check detail, **then** they see each claim with a verdict (`verified`, `corrected`, `removed`), a source link where available, and a short note for any correction or removal.
- **Given** the writer produced a claim the cited source does not support, **when** the edition is published, **then** that claim does not appear as originally written and is listed in the corrections box.
- **Given** an article cannot reach a passing standard after the allowed revision rounds, **when** the edition is built, **then** it is replaced by a reserve story or omitted, and the reader is told.
- **Given** any edition, **then** the masthead area shows how many claims were checked and how many verified.

### Story 3: Set How Often My Paper Arrives (Priority: P1)
> *As a reader, I choose a cadence and the paper then arrives on its own.*

**Acceptance Scenarios:**
- **Given** the reader opens settings, **when** they choose a cadence (`every 4 h`, `8 h`, `12 h`, `daily`, `weekly`), **then** they also choose a start time (and for weekly, a weekday) and see the next planned edition time before saving.
- **Given** a saved schedule, **when** the due time arrives, **then** an edition is built with no action from the reader, and a "new edition" indicator appears.
- **Given** a saved schedule, **when** the reader opens the app, **then** they see the next edition time, the last edition's time and status, and can pause, resume, change, or delete the schedule.
- **Given** the reader wants a paper now, **when** they press "Generate now", **then** an edition is built immediately in the format of their cadence and the schedule is unaffected.
- **Given** the reader changes topics or cadence, **when** an edition is already being built, **then** that edition finishes unchanged and the change applies from the next one.
- **Given** a build fails, **when** it is retried and fails again, **then** the previous edition stays available, the failure is shown with a plain reason, and the schedule keeps running.
- **Given** the app was unavailable across several due times, **when** it returns, **then** it builds at most one catch-up edition, not one per missed time.
- **Given** an edition is still being built when the next one falls due, **then** the new one is skipped and the reader is told, never run twice at once.

### Story 4: Bigger Paper for Slower Rhythms (Priority: P1)
**Acceptance Scenarios:**
- **Given** a Bulletin cadence, **then** editions are one page with three articles.
- **Given** a Daily cadence, **then** editions are two pages with eight articles.
- **Given** a Weekly cadence, **then** editions have a front page, one section page per topic, and a closing page, and always more pages than a Daily edition.
- **Given** a Weekly edition, **then** it covers the full week and each section page carries a longer feature on that topic.

### Story 5: Same Newspaper Every Time (Priority: P1)
**Acceptance Scenarios:**
- **Given** any two editions of any formats, **then** the masthead, typography, colour palette, grid, page furniture, and fact-check presentation are visibly identical.
- **Given** a multi-page edition, **then** every page shows its page number out of the total and the running header.
- **Given** an edition is printed, **then** each page prints as one sheet in the same design, with interface controls hidden.
- **Given** an edition from the archive built earlier, **then** it still displays in its original design version.

### Story 6: Browse Past Editions (Priority: P2)
**Acceptance Scenarios:**
- **Given** several editions exist, **when** the reader opens the archive, **then** they see them newest first with date, format, edition number, and verification totals, and can filter by format.
- **Given** a past edition, **when** opened, **then** it displays complete, including fact-check detail and corrections.
- **Given** the archive is full, **then** the oldest editions beyond the retention limit are removed and the reader is told the limit.

### Story 7: No Repeats (Priority: P2)
**Acceptance Scenarios:**
- **Given** a story appeared in a recent edition, **when** the next edition is built, **then** that story does not appear again.
- **Given** a Weekly edition and a story with a materially new development, **then** it may appear once, labelled `"Follow-up"`.

### Story 8: Edit Topics by Text or Voice (Priority: P2)
**Acceptance Scenarios:**
- **Given** a current list of topics, **when** the reader types or speaks a change (*"drop crypto, add climate tech"*), **then** the list updates and the reader sees and confirms the new list.
- **Given** a change that would exceed five topics, **then** the reader is asked which topic to replace; the list is never silently truncated.
- **Given** unclear or empty speech, **then** the reader is told what was heard and can retry or type instead.

### Story 9: Discover Something Outside My Topics (Priority: P2)
**Acceptance Scenarios:**
- **Given** a Daily or Weekly edition, **then** exactly one article is marked as outside the reader's topics, with a note that it was chosen on purpose.
- **Given** Bulletin editions, **then** no outside-topics story is included.

### Story 10: Illustrated Stories (Priority: P3)
**Acceptance Scenarios:**
- **Given** an article in a slot that carries an image, **then** it shows a relevant illustration in the house style, captioned as an illustration.
- **Given** image creation fails, **then** a styled placeholder appears and the edition still publishes.

### Story 11: Intelligent Blank-Space Analysis & Context-Aware Comic/House-Ad Fillers via SAM 3 (Priority: P2)
> *As a reader, I want any blank spaces left on my generated newspaper pages to be analyzed using Meta's Segment Anything Model (`sam-3` / `sam-3.1`) and filled by a dedicated agent with appropriately sized small comic jokes or "The Muse Newz" house ads so every page looks like a balanced, authentic broadsheet with no awkward empty gaps.*

**Acceptance Scenarios:**
- **Given** a generated newspaper page with articles laid out in the broadsheet grid, **when** the page layout is inspected before final publication, **then** the system uses Meta's **Segment Anything Model (`sam-3` / `sam-3.1`)** (`POST /v1/responses`) to segment the rendered page canvas and identify available blank spaces (whitespace bounding boxes `[x, y, width, height]`, free area percentage, column span, and aspect ratio).
- **Given** one or more detected blank spaces on a page, **when** the **Whitespace Creative & Layout Agent** evaluates the segmented space geometry, **then** it decides for each available space whether to create a **small comic joke** (satirical broadsheet comic panel or newsroom wit/epigram box) or a **"The Muse Newz" house advertisement**, sized strictly to fit the available space tier (`compact`, `column`, or `banner`).
- **Given** a blank space assigned to a small comic joke, **when** the agent creates the filler, **then** it produces an original, family-friendly Victorian broadsheet satirical comic joke/dialogue or newsroom curiosity subtly referencing the edition's verified topics or fact-checking craft, paired with a house-style engraving illustration (`muse-image-1.0` or cached comic engraving) when the space tier supports imagery.
- **Given** a blank space assigned to a "The Muse Newz" (`Muse Newz`) ad, **when** the agent creates the filler, **then** it produces a tailored house advertisement promoting **The Muse Newz** (highlighting cadence rhythm, zero-hallucination verification, and primary-source auditing) formatted to the space's aspect ratio (`stacked` vertical card or `horizontal` broadside banner).
- **Given** a page with no blank space above the minimum fillable threshold (`< 8%` unallocated page area), **when** the analysis completes, **then** no filler is forced onto the page, preventing visual crowding or page overflow.
- **Given** the `sam-3` API call times out or is unavailable, **then** the system degrades gracefully to deterministic grid-slot whitespace calculation and cached comic/Muse Newz ad variants so the edition still publishes without delay (`FR-037`).

### Story 12: Personalized Reader-Titled Masthead — "The [Name] Courier" (Priority: P1)
> *As a reader, I want the newspaper masthead to bear my name as "The [Name] Courier" (for example, "The Aisha Courier") with the tagline “Made for [Name]. Checked before print.” so it reads like a real classic broadsheet built specifically for me, falling back to "The Muse Courier" if no name is set yet.*

**Acceptance Scenarios:**
- **Given** a reader whose name is set to `"Aisha"`, **when** any edition (`Bulletin`, `Daily`, or `Weekly`) is rendered on the web page, printed to PDF, or downloaded as standalone HTML, **then** the Page 1 blackletter masthead displays **"The Aisha Courier"**, the masthead tagline displays **“Made for Aisha. Checked before print.”**, and inside/section/closing running headers and page footers display **"The Aisha Courier"**.
- **Given** a reader who has not set a name yet (empty/blank name or `"Muse"`), **when** an edition is rendered, **then** the masthead title falls back to **"The Muse Courier"** and the tagline displays **“Made for Muse. Checked before print.”**.
- **Given** the reader updates their name in the `"Topics, Region & Voice"` drawer (or via natural-language/voice command such as `"set name to Aisha"`), **when** they confirm and save, **then** the masthead immediately reflects **"The Aisha Courier"** and **“Made for Aisha. Checked before print.”**.

### Story 13: Strict Section & Topic Semantic Integrity, Per-Edition Fresh Woodcut Illustrations, and Topic-Matched Comics & Jokes (Priority: P1)
> *As a reader, I want every topic section (such as Movies, Finance, Crypto, or AI) to contain only stories genuinely belonging to that section, every new edition to generate fresh woodcut illustrations attached to the articles across pages without reusing older edition images, and comics and jokes to be updated and matched to each section's subject.*

**Acceptance Scenarios:**
- **Given** a reader configures topics such as `Movies`, `Finance`, `crypto`, and `AI`, **when** a new edition is built or normalized, **then** `Section: Movies` displays only cinema, film festival, box-office, and theatrical stories (never Energy/HVDC or unrelated stories), `Section: Finance` displays only banking, central bank, capital market, and fintech stories, and `Section: crypto` displays only cryptocurrency, digital asset, and zero-knowledge settlement stories (`is_story_relevant_to_topic`).
- **Given** a new edition is generated, **when** article illustrations are created, **then** the illustrator generates brand-new woodcut PNG engravings for that edition (`_call_muse_image_api` + `build_bespoke_woodcut_png`) rather than reusing cached images from older editions, and attaches illustrations across pages (`p1_lead`, `p1_sec_1`, `p1_outside`, and `p2_brief_1` in Daily; `wk_p1_lead`, `wk_p1_sec_1`, every `wk_sec_{i}_feature`, and `wk_closing_outside` in Weekly).
- **Given** any section page or front page with whitespace fillers, **when** comics and jokes are placed, **then** the comic strip and epigram match the page's topic (`cinema_critic` / `comic_cinema_critic.png` for Movies, `market_oracle` / `comic_market_oracle.png` for Finance, `vault_audit` / `comic_vault_audit.png` for Crypto, `mechanical` & `trap` for AI/Front Page) and rotate/update dialogues and issue numbers across editions.

---

## 7. Functional Requirements

### Topics and Input
- **FR-001:** The system MUST let a reader maintain 1 to 5 topics, edited by text.
- **FR-002:** The system MUST accept topic changes by voice and convert them into the same list changes as text.
- **FR-003:** The system MUST show the resulting list and require confirmation before saving.

### Scheduling
- **FR-004:** The system MUST offer these cadences: `every 4 hours`, `every 8 hours`, `every 12 hours`, `daily`, `weekly`.
- **FR-005:** The system MUST let the reader set a start time, a time zone (defaulting to their device), and for weekly a weekday, and MUST show the next planned edition time.
- **FR-006:** The system MUST build editions automatically at due times with no reader action.
- **FR-007:** The system MUST let the reader pause, resume, change, and delete the schedule, and trigger `"Generate now"`.
- **FR-008:** The system MUST NOT run two builds for the same reader at the same time; an overlapping due time is skipped and recorded.
- **FR-009:** After downtime, the system MUST build at most one catch-up edition.
- **FR-010:** A failed build MUST be retried once; if it fails again, the failure and plain-language reason MUST be shown, the previous edition MUST remain available, and the schedule MUST continue.
- **FR-011:** Topic and schedule changes MUST apply from the next edition and MUST NOT alter a build in progress.
- **FR-012:** The system MUST enforce a daily cap on automatic builds (default `6`) and show the reader when the cap is reached.
- **FR-013:** The system MUST indicate when a new edition is available.

### Formats
- **FR-014:** The system MUST derive each edition's format (pages, article count, page contents) from its cadence using the format table in Section 4, held in configuration.
- **FR-015:** A Weekly edition MUST always have more pages than a Daily edition.
- **FR-016:** If a topic lacks material for its section page, the system MUST shorten or omit that page, keep Weekly at 3 pages or more, and tell the reader.

### Research and Selection
- **FR-017:** The system MUST search each topic independently and at the same time, over the story window for the edition's format (time since previous edition—or cadence length on first run—plus a `2-hour` buffer; `7 days + 2h` for Weekly), and record each candidate's headline, summary, source name, source URL, and date.
- **FR-018:** The system MUST rank candidates across topics and fill the format's article slots (`lead`, `secondary`, `brief`, `feature`).
- **FR-019:** Daily and Weekly editions MUST include exactly one outside-topics story, labelled as such; Bulletins MUST NOT.
- **FR-020:** The system MUST avoid two articles about the same underlying story within an edition.
- **FR-021:** The system MUST NOT repeat a story from recent editions (lookback window: `7 days` for Bulletin/Daily; `4 weeks` [28 days] for Weekly), except labelled `"Follow-up"` stories in Weekly editions when there is a materially new development.
- **FR-022:** The system MUST hold reserve candidates for substitutions.

### Writing and Verification
- **FR-023:** The system MUST write each article as original text based on cited sources, with length set by the slot (`brief`, `standard`/`secondary`, `lead`, `feature`).
- **FR-024:** The system MUST break each draft into factual claims and check each against the cited source content.
- **FR-025:** The system MUST return unsupported claims to the writer for revision, up to two rounds per article.
- **FR-026:** After the final round, the system MUST remove any claim still unsupported and MUST NOT publish an article below a minimum number of verified claims: at least **3 verified claims** for `lead` and `feature` slots, and at least **2 verified claims** for `secondary` and `brief` slots. If an article falls below this threshold after removals, it MUST be replaced by a verified reserve story (or omitted with reader notice if no reserve remains).
- **FR-027:** Every published article MUST include source links.
- **FR-028:** The system MUST record each claim's verdict, source, and a short note for any non-verified claim.

### Presentation and Design
- **FR-029:** The system MUST present every edition using the single design identity in Section 5, regardless of format.
- **FR-030:** Multi-page editions MUST show a folio and running header on every page and print one page per sheet.
- **FR-031:** The system MUST show per-article fact-check detail and an edition corrections section (Weekly: on the closing page).
- **FR-032:** The system MUST illustrate designated visual slots in the house illustration style and label images as illustrations: `1` illustration in Bulletin (Lead), `2` in Daily (Lead + Outside-Topics/top Secondary), and up to `7` in Weekly (Front Lead + each Topic Section Feature + Closing Outside-Topics Feature), with a styled placeholder fallback on failure.
- **FR-033:** Each edition MUST be printable and shareable as a single file.
- **FR-034:** Each edition MUST carry its design version, and past editions MUST keep displaying in the design they were built with.

### Blank-Space Segmentation (`SAM 3`) & Whitespace Creative Agent
- **FR-039:** After initial page composition, the system MUST analyze each newspaper page's layout using Meta's **Segment Anything Model (`sam-3` / `sam-3.1`)** via the Meta Model API (`/v1/responses` with promptable concept segmentation for `"blank paper whitespace"`, `"printed text column"`, and `"illustration frame"`) to locate and measure available blank spaces (bounding box `[x, y, width, height]`, free area ratio, aspect ratio, and grid column span).
- **FR-040:** The system MUST classify each detected blank space into a structural size tier based on its segmented dimensions:
  - **Compact (`compact`, `< 220px` height or single-column tail gap):** Fits a short 2–4 line **Small Comic Joke / Newsroom Epigram** (`curiosities` wit box) or compact **Muse Newz Badge Ad**.
  - **Standard Column (`column`, `4-col` width, square or vertical aspect ratio):** Fits a single-panel **Satirical Broadsheet Comic Strip** (engraving + 2-line comic dialogue joke) or a **Stacked "The Muse Newz" House Ad**.
  - **Wide Banner (`banner`, `8–12 col` width, aspect ratio `width/height >= 2.2`):** Fits a **Horizontal "The Muse Newz" Broadside Ad Banner** or **Multi-Column Comic Strip**.
- **FR-041:** A dedicated **Whitespace Creative Agent (`LlmAgent`)** MUST evaluate the `sam-3` blank-space inventory alongside the edition's verified article headlines and topics, select the optimal filler type (`comic_joke`, `epigram_wit`, or `muse_brief_ad`) for each available space without repeating identical fillers on the same page, and generate space-fitted comic jokes or "The Muse Newz" ad copy.
- **FR-042:** All generated comic jokes and "The Muse Newz" house ads MUST conform to the single newspaper design identity in Section 5, be explicitly labelled as editorial satire/humour (`"THE MECHANICAL MUSE"` / `"THE NEWSROOM DISPATCHES"`) or house promotion (`"THE MUSE NEWZ"`), never masquerade as fact-checked news articles, and have all text HTML-escaped.
- **FR-043:** For blank spaces in the `column` or `banner` tiers, the system MUST pair the agent's generated comic joke or "The Muse Newz" ad copy with a house-style monochrome woodcut engraving (`muse-image-1.0` or pre-generated cached engraving plate).
- **FR-044:** Every `sam-3` segmentation call and Whitespace Creative Agent invocation MUST enforce an explicit timeout (`15s`), a deterministic grid-column whitespace fallback calculator, and a cached demo fixture (`data/demo_cache/`) so editions publish reliably offline or under API rate limits.

### Archive
- **FR-035:** The system MUST keep past editions in an archive, newest first, filterable by format, up to a retention limit (default `60` editions).

### Feedback and Reliability
- **FR-036:** The system MUST show live progress while an edition is built.
- **FR-037:** The system MUST degrade gracefully: a failed topic, image, or voice step MUST NOT stop the edition, and the reader MUST be told what was skipped.
- **FR-038:** The system MUST ship with a ready-made archive containing one sample edition per format (`Bulletin`, `Daily`, `Weekly`), and a demo mode that compresses schedule intervals to **2 minutes (`120s`)** so automatic unattended builds can be shown within 5 minutes (`SC-012`).

### Centrepiece Most-Mentioned News, Strict Image/News Deduplication, Vertical/Horizontal Alignment & Geographic Preference (`/speckit-clarify` Session 2)
- **FR-045 (Most-Mentioned News as Front-Page Centrepiece with Relevant Woodcut):** The system MUST track cross-source mention frequency (`mention_count` across RSS feeds, grounded search results, and consolidated topic dispatches) alongside quantitative/financial magnitude, automatically promote the most-mentioned & highest-impact news story across all beats to the **Front-Page Centrepiece Lead slot (`p1_lead` / `wk_p1_lead`)**, display a multi-source reporting badge (`"★ N Sources Reporting"`), and pair it with a story-specific monochrome woodcut illustration (`muse-image-1.0` or real cached woodcut PNG).
- **FR-046 (Zero Duplicate News Stories & Zero Duplicate Images Across Edition):** The system MUST guarantee that no two slots anywhere in the same edition ever publish the same news event or a cloned `"Analysis: ..."` headline, and that no two illustrated articles or comic/house-ad fillers anywhere in the edition ever reuse the same image content hash or static asset path.
- **FR-047 (Unified Web, Print/PDF & Standalone HTML Alignment with Vertical/Horizontal Space Placement):** The system MUST maintain identical 12-column CSS grid alignment across the live Web App, Print/PDF export (`@media print` & `@page`), and downloaded Single-File HTML (preventing mobile `@media screen and (max-width: 768px)` rules from collapsing print viewports), and dynamically format articles, comics, and house ads into **horizontal (`layout-horizontal`)** or **vertical (`layout-vertical`)** layouts based on each slot's column span and aspect ratio.
- **FR-048 (Geographic Preference Alongside Topics):** The system MUST allow the reader to configure a **Geographic Preference (`geographic_preference`, e.g., `"Global"`, `"United States & North America"`, `"Europe & United Kingdom"`, `"Asia-Pacific"`, `"India & South Asia"`, or any custom region/country/city)** via the UI drawer and natural-language/voice commands, persist it in SQLite, display it in the Masthead ear and edition line, and pass it to the Beat Reporters to weight regional dispatches alongside global breaking news.

### Personalized Reader-Titled Masthead (`/speckit-specify` Update)
- **FR-049 (Dynamic Reader-Named Masthead — `"The [Name] Courier"`):** The system MUST format the newspaper's primary masthead title, inside running headers, page footers, and document `<title>` as **`The [Name] Courier`** using the reader's configured name (e.g., **`The Aisha Courier`** for reader `"Aisha"`). If no reader name is provided (empty string, whitespace, or `"Muse"`), the title MUST fall back deterministically to **`The Muse Courier`**. If the reader enters a name that already includes `"The "` or `" Courier"`, the formatter MUST normalize it so `"The "` or `" Courier"` is never doubled.
- **FR-050 (Personalized Masthead Tagline — `“Made for [Name]. Checked before print.”`):** The system MUST render the masthead motto/tagline directly below the blackletter title as **`“Made for [Name]. Checked before print.”`** (e.g., **`“Made for Aisha. Checked before print.”`**, falling back to **`“Made for Muse. Checked before print.”`** when no reader name is set).

### Strict Topic & Section Semantic Integrity, Per-Edition Fresh Illustrations & Updated Topic-Matched Comics (`/speckit-clarify` Session 3)
- **FR-051 (Strict Topic & Section Semantic Alignment — Zero Off-Topic Fallback Contamination):** The system MUST maintain distinct curated and live search pools for every beat (`Movies & Cinema`, `Finance & Global Markets`, `Crypto & Digital Assets`, `AI`, `Energy`, `Semiconductors`, `Biotech`, `Space`) and validate semantic alignment (`is_story_relevant_to_topic`) before assigning any candidate to a topic slot or section page. If a topic has fewer live candidates than slots on its section page (`Section: Movies`, `Section: Finance`, etc.), the system MUST pull additional verified stories from that same topic's curated dispatch pool rather than backfilling from unrelated topics, and MUST never merge unrelated stories from the same country/region into a single article.
- **FR-052 (Fresh Image Generation for Every New Edition & Expanded Article Illustrations):** The system MUST generate brand-new woodcut PNG illustrations for every new edition (`_call_muse_image_api` + edition-stamped bespoke woodcut plate generator `build_bespoke_woodcut_png`), track historically used image hashes across previous archived editions so older edition images are not reused in new editions, and attach illustrations to articles across every page (`p1_lead`, `p1_sec_1`, `p1_outside`, and `p2_brief_1` in Daily; `wk_p1_lead`, `wk_p1_sec_1`, every `wk_sec_{i}_feature`, and `wk_closing_outside` in Weekly).
- **FR-053 (Topic-Matched & Edition-Updated Comics and Jokes):** The Whitespace Creative Agent MUST match comic strips and newsroom epigrams to the active page's section topic (`cinema_critic` / `comic_cinema_critic.png` for Movies, `market_oracle` / `comic_market_oracle.png` for Finance, `vault_audit` / `comic_vault_audit.png` for Crypto, `mechanical` & `trap` for AI/Front Page) and dynamically update/rotate comic dialogues, issue numbers, and jokes across editions.

---

## 8. Key Entities

- **Reader:** `name`, `time_zone`, `topics` (1 to 5).
- **Schedule:** `cadence`, `start_time`, `weekday` (weekly), `paused_flag`, `next_due_time`, `last_run`.
- **Edition Format:** `name`, `cadences`, `pages` and their `templates`, `article_slots`, `story_window`, `outside_story_rule`.
- **Run:** `trigger` (`scheduled`, `catch-up`, `manual`), `status`, `attempt`, `timings`, `failure_reason`.
- **Edition:** `number`, `format`, `date`, `design_version`, `pages`, `articles`, `corrections`, `verification_totals`.
- **Page:** `template` (`front`, `inside`, `section`, `closing`), `number`, `articles`.
- **Candidate Story:** `topic`, `headline`, `summary`, `source_name`, `url`, `date`, `relevance`.
- **Article:** `slot_kind`, `topic`, `headline`, `deck`, `byline`, `body`, `image` and `caption`, `sources`, `claims`, `outside_flag`, `follow_up_flag`.
- **Claim:** `text`, `verdict` (`verified`, `corrected`, `removed`), `source_url`, `note`.
- **Published-Story Record:** `url` and `story_fingerprint` of everything already printed, used to prevent repeats.
- **Blank-Space Region (`WhitespaceRegion`):** `region_id`, `page_number`, `bbox` (`x`, `y`, `width`, `height`), `area_ratio`, `aspect_ratio`, `column_span`, `size_tier` (`compact`, `column`, `banner`), `detection_source` (`sam-3` | `grid_fallback`).
- **Whitespace Filler (`WhitespaceFillerItem`):** `filler_id`, `region_id`, `page_number`, `filler_type` (`comic_joke`, `epigram_wit`, `muse_brief_ad`), `size_tier`, `title`, `subtitle_or_eyebrow`, `dialogue_or_copy`, `image_prompt`, `image_path`, `caption_or_motto`.

---

## 9. Edge Cases

- **Reader picks a 4-hour cadence with a long overnight quiet period:** Builds still happen on schedule (no quiet hours in this version).
- **Time zone with daylight saving changes:** Due times stay at the reader's local clock times.
- **A 4-hour cadence finds almost nothing new:** The Bulletin publishes with fewer articles and says so, rather than repeating old stories.
- **Weekly edition with one topic:** Front page, one section page, closing page (3 pages), still more than Daily.
- **Two topics return the same story:** It appears once.
- **Source page unreachable or paywalled:** Claims depending on it cannot be verified.
- **Sources contradict each other:** The article states the disagreement or the claim is removed.
- **Source text contains instructions aimed at the AI:** Treated as content, never as commands.
- **The reader changes cadence while a build is running:** The build finishes in the old format.
- **Daily cap reached:** Remaining scheduled builds are skipped and the reader is told; manual `"Generate now"` is also blocked with an explanation.
- **Reader opens an old edition after a design update:** It shows in its original design version.
- **Speech in a different language:** Attempted, with transcript shown.
- **A page is already densely packed with article text and corrections (`< 8%` blank space):** `sam-3` reports no region meeting the minimum fillable area threshold; the Whitespace Creative Agent skips adding comics or ads on that page so text is never clipped or crowded.
- **Multiple blank spaces appear on the same page:** The Whitespace Creative Agent alternates between a small comic joke, newsroom epigram wit, and a "The Muse Newz" house ad so the same filler type or asset is never duplicated side-by-side.
- **`sam-3` segmentation endpoint times out or returns no masks:** The system falls back seamlessly to deterministic CSS grid column-span remainder calculation and populates the space without failing the edition build.

---

## 10. Out of Scope (For This Build)

- User accounts, sign-in, payments, mobile apps.
- Email, push, or messaging delivery (the reader sees a new-edition indicator in the app).
- Quiet hours or per-topic schedules.
- Scraping social platforms.
- Photographs of real events or people; all images are illustrations.
- Reproducing full text of source articles.
- Learning from reading behaviour (a simple *"more like this / less like this"* signal is a stretch goal).

---

## 11. Success Criteria (Measurable, Technology-Agnostic)

- **SC-001:** A manual Bulletin completes in under 3 minutes, a Daily in under 6, a Weekly in under 15, with progress visible throughout.
- **SC-002:** 100% of published articles show source links and fact-check detail.
- **SC-003:** In the demo, at least one claim is visibly corrected or removed, and the reader can see why.
- **SC-004:** At least 95% of scheduled editions start within 2 minutes of their due time during testing.
- **SC-005:** Zero overlapping builds and zero repeated stories across consecutive editions in test runs.
- **SC-006:** A Weekly edition has more pages than a Daily edition in 100% of builds, for 1 to 5 topics.
- **SC-007:** Pages from a Bulletin, a Daily, and a Weekly edition, shown side by side to a first-time viewer, are identified as the same publication.
- **SC-008:** 100% of editions pass the design conformance checklist (masthead, typography, palette, folio, fact-check presentation, design version).
- **SC-009:** Each edition remains readable on a phone-sized screen and prints one page per sheet.
- **SC-010:** A reader can change topics by voice in one attempt in a quiet room, at least 4 times out of 5.
- **SC-011:** If any single stage fails, an edition still publishes in at least 9 of 10 trial runs.
- **SC-012:** In demo mode, a viewer sees at least one fully automatic, unattended edition appear within 5 minutes.
- **SC-013:** 100% of generated pages with fillable blank space (`>= 8%` unallocated area) have their whitespace segmented by `sam-3` (or deterministic grid fallback when offline) and populated by the Whitespace Creative Agent with a space-appropriate **small comic joke** or **"The Muse Newz" ad** with zero layout overflow or adjacent duplicate fillers.
- **SC-014:** 100% of generated and archived editions contain **zero duplicate article headlines/events** and **zero duplicate illustration or comic/ad images** across all pages of the edition.
- **SC-015:** In 100% of editions, the story with the highest cross-source `mention_count` and editorial magnitude is placed in the **Front-Page Centrepiece Lead slot** with a relevant woodcut illustration and multi-source badge.
- **SC-016:** Web Page, Print/PDF (`@media print`), and Standalone HTML exports preserve multi-column broadsheet alignment and assign `layout-horizontal` vs `layout-vertical` presentation according to slot geometry, while displaying and applying the reader's `geographic_preference`.
- **SC-017:** 100% of editions render the personalized masthead **`The [Name] Courier`** (e.g., **`The Aisha Courier`**) and tagline **`“Made for [Name]. Checked before print.”`** when a reader name is present, and fall back to **`The Muse Courier`** / **`“Made for Muse. Checked before print.”`** when no name is set.
- **SC-018:** 100% of section pages (`Section: Movies`, `Section: Finance`, `Section: crypto`, `Section: AI`, etc.) and topic-assigned articles pass `is_story_relevant_to_topic` semantic verification with zero off-topic contamination or unrelated secondary-source merging.
- **SC-019:** 100% of newly generated editions produce fresh, edition-specific `.png` woodcut illustrations attached to articles across every page (`4` illustrated slots in Daily, up to `8` in Weekly) with zero image hash reuse from earlier archived editions.
- **SC-020:** 100% of section pages with comic fillers display topic-matched comic strips (`cinema_critic` for Movies, `market_oracle` for Finance, `vault_audit` for Crypto) and edition-updated satirical dialogues/epigrams.

---

## 12. Resolved Clarifications (`/speckit-clarify` — Sessions `2026-10-31` & `2026-11-01`)

All 17 open decisions and slot policies have been formally resolved:

| # | Decision Area | Locked Resolution |
| :--- | :--- | :--- |
| **1** | **Final Page & Article Counts per Format (`FR-014`)** | **Bulletin:** `1` page, `3` articles (1 lead, 2 briefs; 0 outside-topics).<br>**Daily:** `2` pages, `8` articles (Page 1: 1 lead, 2 secondary, 2 briefs [1 is outside-topics]; Page 2: 3 briefs).<br>**Weekly:** `3` to `7` pages, up to `16` articles (Page 1: 5 top stories; 1 section page per active topic with material [1 feature + 1 brief]; Closing page: 1 outside-topics feature, week's corrections, sources). |
| **2** | **Minimum Verified Claims per Slot (`FR-026`)** | **`lead` & `feature` slots:** Minimum **3 verified claims**.<br>**`secondary` & `brief` slots:** Minimum **2 verified claims**. |
| **3** | **Verification Failure Policy (`FR-026`)** | After Round 2 of the Writer/Fact-Checker loop, strip any remaining unsupported claims (logged as `removed` in the corrections box). If the resulting article still meets its slot's minimum verified claims (`3` or `2`), publish it. If it falls below the minimum, **replace with a reserve story** (or omit the slot and inform the reader if no reserve passes). |
| **4** | **Story Window Buffer (`FR-017`)** | **Bulletin & Daily:** Time since previous edition (or cadence length on first run) **+ `2 hours` buffer**.<br>**Weekly:** Past `7 days` **+ `2 hours` buffer**. |
| **5** | **No-Repeat Lookback Window (`FR-021`)** | **Bulletin & Daily:** Last **`7 days`**.<br>**Weekly:** Last **`4 weeks` (`28 days`)**, allowing a previously printed story at most once labelled `"Follow-up"` only when there is a materially new development. |
| **6** | **Weekly Recap of Earlier Editions** | **Excluded** in this build; Weekly editions conduct full-week research and section features without a separate recap digest of earlier Bulletin/Daily issues. |
| **7** | **Retention Limit, Daily Cap & Demo Interval (`FR-012`, `FR-035`, `FR-038`)** | **Archive Retention:** `60` editions.<br>**Daily Build Cap:** `6` builds per day.<br>**Demo Mode Interval:** `2 minutes` (`120s`) compressed schedule interval + pre-built sample archive (1 Bulletin, 1 Daily, 1 Weekly). |
| **8** | **Illustrated Article Slots (`FR-032`)** | **Bulletin:** `1` illustration (Front Lead).<br>**Daily:** `2` illustrations (Front Lead + Outside-Topics / Top Secondary).<br>**Weekly:** Up to `7` illustrations (Front Lead + 1–5 Topic Section Features + Closing Outside-Topics Feature). |
| **9** | **SAM-3 Image Input & Layout Snapshot (`FR-039`, `FR-044`)** | **Hybrid DOM-to-Canvas / Server Snapshot:** The system captures the rendered newspaper page layout as an image for Meta's SAM-3 (`sam-3.1`) promptable concept segmentation (`"blank paper whitespace"`, `"printed text column"`), with deterministic CSS grid fallback if headless/canvas capture is offline. |
| **10** | **Whitespace Content Allocation Policy (`FR-040`, `FR-041`)** | **Balanced Cadence-Aware Allocation:** Front pages and topic section pages prioritize satirical comic jokes; inside pages and closing pages feature **"The Muse Newz"** house ads. |
| **11** | **Comic Generation & Illustration Strategy (`FR-043`)** | **Full Live Generation:** The Whitespace Creative Agent writes original satirical comic dialogue AND generates a brand-new illustration via `muse-image-1.0` for every blank space (with timeout/cached demo fallback for offline resilience). |
| **12** | **Satirical Humour Tone & Angle (`FR-041`, `FR-042`)** | **Topic-Specific Satirical Commentary:** Punchy Victorian/broadsheet editorial satire specifically lampooning that edition's actual researched topics (e.g., AI hype, biotech, clean energy grid, space tech). |
| **13** | **Strict Deduplication of News & Images (`FR-020`, `FR-046`)** | **Zero Duplicate Stories & Zero Duplicate Images Across All Pages:** Never clone an existing story with `"Analysis: ..."` when a topic has fewer candidates than slots—always pull a distinct verified dispatch. Track `used_image_hashes`, `used_filler_keys`, and `used_filler_paths` edition-wide so no article or comic/house-ad filler image is ever repeated in the same edition. |
| **14** | **Web, PDF & Standalone HTML Alignment + Vertical/Horizontal Space Placement (`FR-047`)** | **Unified 12-Column Broadsheet Grid & Orientation-Aware Slots:** Scope mobile reflow strictly to `@media screen and (max-width: 768px)` and enforce `@page` + `@media print` 12-column grid rules so Web, Print/PDF, and Standalone HTML align identically. Place articles and fillers dynamically into `layout-horizontal` (wide 6–12 col spaces with 2-column body or side-by-side image+copy) or `layout-vertical` (3–5 col vertical wings/columns). |
| **15** | **Most-Mentioned News as Centrepiece with Relevant Woodcut (`FR-045`)** | **Cross-Source Mention Count + Magnitude Supremacy:** Cluster RSS/search items and cross-topic dispatches to compute `mention_count`. Weight `mention_count` and quantitative scale so the most-mentioned breaking story (e.g. the $6.3B Binance crypto heist reported across 6 sources) always forms the Front-Page Centrepiece (`p1_lead`) with a dedicated, story-specific woodcut engraving. |
| **16** | **Geographic Preference Alongside Topics (`FR-048`)** | **First-Class `geographic_preference` in `ReaderProfile`:** Configurable via the UI Topics & Region drawer (`Global`, `United States & North America`, `Europe & United Kingdom`, `Asia-Pacific`, `India & South Asia`, `Middle East & Africa`, `Latin America`, or custom) and natural-language/voice commands (`"set region to ..."`), persisted in SQLite, displayed in the Masthead, and passed to Beat Reporters. |
| **17** | **Personalized Reader-Titled Masthead & Tagline (`FR-049`, `FR-050`)** | **`The [Name] Courier` & `“Made for [Name]. Checked before print.”`:** The newspaper masthead dynamically incorporates the reader's name as **`The [Name] Courier`** (e.g., **`The Aisha Courier`**) with tagline **`“Made for Aisha. Checked before print.”`**. If no reader name is set yet, it falls back to **`The Muse Courier`** and **`“Made for Muse. Checked before print.”`**. |
| **18** | **Strict Section & Topic Semantic Integrity (`FR-051`, `SC-018`)** | **Zero Cross-Topic Contamination:** Separate Finance, Crypto, Movies, AI, Energy, Semiconductor, Biotech, and Space curated dispatches and enforce `is_story_relevant_to_topic` across RSS retrieval, `EditorInChiefAgent`, and `normalize_edition_layout_and_centrepiece` so `Section: Movies` only shows cinema/film stories, `Section: Finance` only shows finance/banking/market stories, and `Section: crypto` only shows crypto/ledger stories. |
| **19** | **Fresh Per-Edition Woodcut Images & Expanded Article Illustrations (`FR-052`, `SC-019`)** | **Mandatory Per-Edition Image Freshness:** Track `_get_historically_used_image_hashes` across all archived editions, remove loose cross-headline cache matching, and generate fresh woodcut PNG plates (`_call_muse_image_api` + `build_bespoke_woodcut_png`) attached to key articles across every page (`p1_lead`, `p1_sec_1`, `p1_outside`, `p2_brief_1` in Daily; `wk_p1_lead`, `wk_p1_sec_1`, `wk_sec_{i}_feature`, `wk_closing_outside` in Weekly). |
| **20** | **Topic-Matched & Edition-Updated Comics and Jokes (`FR-053`, `SC-020`)** | **Section-Aware Comic Panels & Rotating Dialogues:** Pair each section with dedicated woodcut comic plates (`comic_cinema_critic.png` for Movies, `comic_market_oracle.png` for Finance, `comic_vault_audit.png` for Crypto, `comic_mechanical_muse.png` & `comic_hallucination_trap.png` for AI/Front Page) and rotate/generate fresh satirical dialogues and epigrams for every new edition. |
