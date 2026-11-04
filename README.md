# 📰 The Muse Newz (Your Daily Muse)

> **Autonomous, Verification-First Personalized Broadsheet Newspaper**  
> *Built with Google Agent Development Kit (ADK) & Meta AI Models for the Meta Global AI Developer Hackathon.*

---

## 🏛️ Executive Summary

**The Muse Newz** re-imagines news consumption by replacing algorithmic engagement feeds with an authentic, personalized daily broadsheet newspaper. Readers select up to five editorial beats (e.g. *Frontier AI*, *Clean Energy*, *Crypto*, *Biotech*, *Semiconductors*) and a delivery rhythm. From then on, an autonomous multi-agent newsroom researches, writes, adversarially fact-checks, illustrates, and typesets complete multi-page editions without human intervention.

Every printed statement is traced to primary ground-truth sources (`[S1]`, `[S2]`), and claims that fail fact-checking are visibly corrected or struck from the record in a public **Verification Ledger**. Empty layout margins are analyzed using **Meta SAM 3** computer vision and filled with custom woodcut house advertisements for **The Muse Newz** and satirical newsroom comic strips.

---

## ⚙️ How The Muse Newz Works (The Multi-Agent Newsroom)

The system is organized into a deterministic, verification-gated autonomous pipeline:

```
[ Reader Beats & Schedule ]
             │
             ▼
┌──────────────────────────────────────────────────────────────────┐
│ STAGE 1: Parallel Beat Reporting (ParallelAgent)                │
│ • Live Google News RSS & direct web scraping                    │
│ • Parallel researchers extract dispatches & primary URLs        │
└─────────────────────────────────┬────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│ STAGE 1.5: 7-Day Anti-Duplication Filter (StoryDedupService)     │
│ • Normalizes URLs & checks 7-day lookback window                │
│ • Prevents repeat stories across editions                        │
└─────────────────────────────────┬────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│ STAGE 2: Editorial Synthesis & Manifest Assembly (EditorAgent)   │
│ • Cross-source clustering & mention_count scoring               │
│ • Centers biggest breaking story in Front-Page Lead             │
│ • Curates mandatory "Outside Your Usual Reading" serendipity    │
└─────────────────────────────────┬────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│ STAGE 3: Adversarial Verification Loop (LoopAgent + Gatekeeper)  │
│ • Writer drafts articles with strict [S#] citations              │
│ • Fact-Checker (temp=0.0) verifies atomic claims against sources │
│ • Failed claims stripped to Public Verification Ledger           │
└─────────────────────────────────┬────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│ STAGE 4: Authentic House Illustrations (IllustratorService)      │
│ • Generates 19th-century woodcut engravings via muse-image-1.0   │
│ • Strict perceptual hash deduplication per edition              │
└─────────────────────────────────┬────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│ STAGE 4b: SAM-3 Layout Whitespace Analysis & Creative Fillers    │
│ • Meta SAM-3 segments unallocated white paper margins            │
│ • WhitespaceCreativeAgent injects:                               │
│   - "The Muse Newz" house broadside advertisements               │
│   - Topic-specific Victorian satirical comic strips              │
└─────────────────────────────────┬────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│ STAGE 5: Typesetting & Broadsheet Publishing (FormatterService)  │
│ • 12-column responsive layout + print/PDF engine                 │
│ • Standalone single-file HTML compilation with Base64 assets     │
└──────────────────────────────────────────────────────────────────┘
```

### Key Newsroom Features:
* **The Verification Ledger:** Every edition displays an accounting of checked claims (e.g. *18 / 18 Claims Verified*). Readers can click into any article to inspect the adversarial audit trail and source quotes.
* **Balanced Cadence & Formats:**
  * **Bulletin:** 1 page, 3 articles (rapid 4-hour or 8-hour dispatch).
  * **Daily:** 2 pages, 8 articles (includes 1 outside-beat discovery piece).
  * **Weekly:** Up to 7 pages, 16 articles with full topic section folios.
* **The 7-Day No-Repeat Guardrail:** Stories published in the last 7 days are tracked in SQLite so the reader never receives duplicate news.
* **The Muse Newz House Ads & Comics:** Unallocated page whitespace is filled with satirical broadsheet comic strips (*"The Mechanical Muse"*) and house advertisement plates for **The Muse Newz** (*Gutenberg Press*, *Pocket Chronometer*, *Athena Fact-Checking Owl*).

---

## 🤖 Use of Meta Models & Technologies

*The Muse Newz* leverages a multi-modal suite of **Meta AI models and APIs** (`https://api.meta.ai/v1`) to power reasoning, automated reporting, computer vision layout segmentation, speech recognition, and editorial illustration:

### 1. Meta Muse Text & Reasoning Models (`muse-wonder-1.0` / Meta Llama 3)
* **Parallel Beat Reporters:** Deconstructs raw dispatches into verified atomic claims and source provenance.
* **Editor-in-Chief Agent:** Evaluates journalistic magnitude, ranks stories by cross-source mention volume, and resolves slot geometry.
* **Adversarial Fact-Checker:** Evaluates claim entailment at `temperature=0.0` against ground-truth evidence, enforcing zero hallucination.
* **Whitespace Creative Humorist:** Crafts topical Victorian satire, epigrams, and ad copy lampooning the edition's real news topics.

### 2. Meta Segment Anything Model (SAM 3 / SAM 3.1)
* **Visual Layout Segmentation:** Inspects rendered newspaper page layouts to distinguish printed text blocks from unallocated whitespace.
* **Tiered Geometry Classification:** Quantifies remaining empty regions into spatial tiers (`compact`, `column`, `banner`) with area thresholds ($\ge 8\%$) to prevent layout gaps or visual overflow.

### 3. Meta Muse Image Generation (`muse-image-1.0`)
* **Editorial Woodcut Engravings:** Produces high-contrast Victorian woodcut and copperplate plates for front-page leads, section features, and closing pieces.
* **Edition-Wide Deduplication:** Enforces perceptual hash tracking so no two articles or ads in the same edition ever share identical imagery.
* **Comic Art & House Ads:** Generates illustrations for newsroom automaton comics and house ads for **The Muse Newz**.

### 4. Meta Voice Transcribe ASR (`muse-voice-transcribe-1.0`)
* **Hands-Free Beat Curation:** Readers tap the microphone icon in the *"Topics, Region & Voice"* drawer to speak commands naturally (e.g. *"Swap crypto for robotics"*, *"Focus on Asia-Pacific"*). Audio is transcribed via `/v1/asr/transcribe` and parsed by the Topic Orchestrator.

---

## 📥 How to Download & Work With This Edition

The application offers multiple ways to read, archive, and export each edition:

### 1. View in Interactive Web Reader
* Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in any modern browser.
* Browse multi-page editions with authentic broadsheet serif typography and drop caps.
* Toggle between dark newsprint and daylight mode via the **🌓 Ink Mode** button.
* Expand the **Audit Drawer** below any article to inspect the underlying source links and verification status.

### 2. Download Standalone Single-File HTML
* In the top navigation bar, click **⬇️ Single-File HTML** (or navigate to `/api/editions/{edition_id}/download`).
* The system compiles a self-contained `.html` file where:
  * All stylesheets and design tokens are embedded.
  * All illustrations, house ads, and comic images are inlined as Base64 `data:image/png` URIs.
* You can open this file completely offline, email it as an attachment, or store it in your personal reading archive.

### 3. Print to Paper or Export to PDF
* Click the **🖨️ Print Paper** button in the toolbar (or press `Ctrl+P` / `Cmd+P`).
* The built-in `@media print` stylesheet strips all UI chrome, formats columns into a broadsheet grid, and formats each page cleanly to a single printed sheet.
* Select *"Save as PDF"* in your browser's print dialog to produce high-resolution digital print editions.

### 4. Switch or Revisit Editions in the Archive
* Click **🗂️ Archive** in the top toolbar to access up to 60 retained past editions across Bulletin, Daily, and Weekly formats.

---

## 🚀 Quickstart & Installation

### Prerequisites
* **Python 3.11+**
* Git
* A Meta Model API Key (`https://api.meta.ai/v1`) or use the built-in offline demo fixture.

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/your-username/your-daily-muse.git
cd your-daily-muse

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

### 3. Configure Environment Variables

Copy the example `.env` file:

```bash
cp .env.example .env
```

Edit `.env` with your Meta API credentials:

```ini
LLM_API_BASE_URL=https://api.meta.ai/v1
MODEL_API_KEY=your_meta_model_api_key_here
MUSE_TEXT_MODEL=muse-wonder-1.0
MUSE_IMAGE_MODEL=muse-image-1.0
MUSE_VOICE_MODEL=muse-voice-transcribe-1.0
MUSE_SAM_MODEL=sam-3.1
DEMO_CACHE_MODE=fallback
```

*(Note: If no API key is provided, `DEMO_CACHE_MODE=fallback` automatically uses the pre-recorded fixture cache so you can test and explore the full app offline).*

### 4. Start the Application

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser to: **`http://127.0.0.1:8000`**

---

## 🧪 Running Automated Tests

The repository includes a comprehensive unit and integration test suite:

```bash
pytest -v
```

All 25 automated tests verify:
* **Verification Loop & Gatekeeper:** Enforces zero hallucinations and claim stripping.
* **Layout Segmentation:** Validates SAM-3 whitespace analysis and comic/ad placement.
* **Anti-Duplication:** Validates 7-day story deduplication and image hash uniqueness.
* **Design Conformance:** Checks 12-column grid alignment, design tokens, and dark mode.
* **Scheduler Determinism:** Tests cadence intervals and catch-up runs against fake clocks.

---

## 📄 License & Attribution

Developed for the **Meta Global AI Developer Hackathon**. Built with the **Google Agent Development Kit (ADK)**, **Meta Muse Model API**, and **Meta Segment Anything (SAM 3.1)**. All broadsheet design tokens and editorial typography conform to authentic 19th-century newspaper printing specifications.

