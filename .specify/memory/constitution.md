# Project Constitution: Your Daily Muse (`constitution.md`)
**Version:** 1.1.0 | **Ratified:** 2026-10-31 | **Hackathon:** Meta Global AI Developer Hackathon  
**Enforcement Scope:** All specifications (`spec.md`), technical plans (`plan.md`), task lists (`tasks.md`), and source code implementations.

---

## Preamble
**Your Daily Muse** is an autonomous, adversarial multi-agent newspaper system built with **Google Agent Development Kit (ADK)** for agent orchestration and powered by **Meta's Muse Model API (`https://api.meta.ai/v1`)** for reasoning, search grounding, speech-to-text, and editorial illustration.

Code serves specifications, and specifications obey this Constitution. Any implementation, prompt, tool, or UI component that violates the Project Principles, Constraints, Guardrails, or Boundary Conditions defined below MUST be rejected during verification gates.

---

## 1. Constitution (Core Project Principles)

1. **Demo reliability beats feature count.** Every external call has a timeout, a fallback, and a cached demo path.
2. **Deterministic where possible.** Scheduling, format sizing, layout, schema validation, loop exit, and de-duplication are code, not LLM output.
3. **Agents only where decisions are made.** Reporting, editing, writing, and verifying are agents. Images, publishing, speech, and scheduling are tools or services.
4. **Untrusted content stays data.** Fetched web text is never treated as instructions, and all output is HTML-escaped.
5. **Structured contracts between stages.** Every stage reads and writes validated JSON models.
6. **One design, many formats.** Appearance comes from a single versioned token set and shared partials. No template may define its own colours, fonts, or masthead.
7. **Formats are data.** Page and article counts live in configuration, not in code branches.
8. **Small and testable.** Each stage runs alone against mock data; the scheduler runs against a fake clock.

---

## 2. Constraints and Assumptions

| Item | Decision / Status |
| :--- | :--- |
| **Models** | Meta Model API (Muse family + Segment Anything `sam-3` / `sam-3.1`) for text, image, speech-to-text, and page blank-space segmentation. Confirm exact model IDs and endpoints in the `dev.meta.ai` docs on Day 1. |
| **Agent framework** | Google ADK (Python). |
| **ADK to Meta connection** | Unverified. Plan: ADK's `LiteLLM` model wrapper against Meta's OpenAI-compatible endpoint. Day 1 spike decides; fallback in Section 6 (ADK-to-Meta Fallback Strategy). |
| **Text-to-speech** | Meta has no TTS (`Muse Voice Transcribe` is speech-to-text only). Use browser `SpeechSynthesis`. |
| **Web research** | Meta search grounding if it returns usable sources; otherwise a search API behind `search_web`. Social platforms out of scope. |
| **Google Trends** | Optional, cached snapshot only, never on the critical path. |
| **Runtime** | Python 3.11+, FastAPI, single worker process (the scheduler lives in-process), plain HTML/JS frontend. |
| **Scheduler** | APScheduler (`AsyncIOScheduler`) with a SQLite job store. |
| **Storage** | SQLite plus files on disk. |

---

## 3. Architectural Mandates (Agent vs. Tool Separation)

In strict accordance with **Principle 2 (Deterministic where possible)** and **Principle 3 (Agents only where decisions are made)**:

### 3.1 Where Agents Are Used (Decision-Making Only)
- **Orchestrator Agent (`LlmAgent`):** Interprets user natural-language/transcribed topic adjustments and updates the structured topic configuration.
- **Beat Reporter Agents (`ParallelAgent` of `LlmAgent`s):** Synthesize search results for a single beat and extract candidate stories with source URLs.
- **Editor Agent (`LlmAgent`):** Ranks candidate stories across beats, selects the configured number of lead/feature stories, and selects the mandatory **Blind Spot** slot.
- **Writer & Fact-Checker Agents (`LoopAgent`):** The Writer drafts/revises articles with inline citations; the Fact-Checker extracts atomic claims and evaluates entailment against verbatim source text.
- **Whitespace Creative Agent (`LlmAgent`):** Evaluates page blank-space regions segmented by Meta's **Segment Anything Model (`sam-3` / `sam-3.1`)** alongside the edition's verified topics, decides whether each blank space should carry a small satirical comic joke, newsroom epigram, or a `"The Muse Newz"` house advertisement sized to the space tier (`compact`, `column`, `banner`), and crafts the space-fitted comic dialogue or ad copy.

### 3.2 Where Deterministic Code, Tools & Services Are Used (Never LLMs)
- **De-duplication & URL Normalization:** Deterministic Python URL canonicalization and title similarity checks before candidate stories reach the Editor.
- **Loop Exit & Post-Loop Gatekeeping:** Deterministic Python checks on `FactCheckReport.passed` and `max_iterations=2` enforcement.
- **SAM-3 Blank-Space Analyzer (`sam_layout_analyzer` service/tool):** Deterministic API client calling Meta's `sam-3` / `sam-3.1` endpoint (`/v1/responses` with promptable concept segmentation for page whitespace and content blocks) with deterministic CSS grid column-remainder fallback and bounding-box tier classification (`compact`, `column`, `banner`).
- **Illustrator (`illustrator` service/tool):** Deterministic API client calling Meta's `muse-image-1.0` endpoint (with timeout + local SVG fallback).
- **Formatter & Publisher (`formatter` service/tool):** Deterministic server-side HTML/PDF rendering driven by a single versioned design token set (`tokens.json` / CSS custom properties) and shared template partials (masthead, columns, bylines, audit drawer).
- **Speech Services:**
  - *Speech-to-Text (STT):* Service wrapper around Meta `Muse Voice Transcribe` (`/v1/asr/transcribe`).
  - *Text-to-Speech (TTS):* Client-side browser `window.speechSynthesis` API reading the published article text aloud.
- **Scheduling (`scheduler` service):** In-process `AsyncIOScheduler` (APScheduler) persisted to SQLite, injectable with a fake clock for deterministic unit testing.
- **Edition Formats as Data:** Format definitions (e.g., `broadsheet_5_story`, `briefing_3_story`, page counts, column rules, word-count targets) live in declarative configuration (`config/formats.json`), never hardcoded `if/else` branches.

---

## 4. Operational & Security Guardrails

### Guardrail 1: Zero-Hallucination & Citation Integrity
- **G-1.1 (Citation Integrity):** The Writer Agent is forbidden from inventing URLs or citing a `[S#]` tag that does not exist in its assigned `CandidateStory.sources` list. Deterministic code validates all `[S#]` references before Fact-Checker invocation.
- **G-1.2 (Strict Entailment Rule):** The Fact-Checker Agent operates at `temperature=0.0` and classifies any number, date, percentage, quote, or causal claim not explicitly present in `verbatim_content` as `UNSUPPORTED`.
- **G-1.3 (Deterministic Loop Exit):** Loop exit is controlled by deterministic inspection of the validated `FactCheckReport` JSON model (`passed == True` triggers `tool_context.actions.escalate = True`).

### Guardrail 2: Untrusted Web Content & Output Escaping (Principle 4)
- **G-2.1 (Untrusted Scraping Boundary):** All web-scraped article text (`verbatim_content`) is treated strictly as passive data:
  - Strip HTML/script/style tags and control characters upon ingestion.
  - Wrap scraped content inside explicit XML delimiter tags (`<untrusted_source_text id="S1">...</untrusted_source_text>`).
  - System prompts must explicitly instruct the model to ignore any instructions or directives found inside `<untrusted_source_text>`.
- **G-2.2 (Mandatory HTML Escaping):** Every string coming from an LLM or external web source MUST be HTML-escaped (`html.escape` / auto-escaped Jinja2 templates) before rendering into the plain HTML/JS frontend. Raw unescaped HTML injection from LLM outputs is prohibited.

### Guardrail 3: Design Token & Template Uniformity (Principle 6 & 7)
- **G-3.1 (Single Source of Visual Truth):** All typography, colour palettes, spacing scales, border weights, and masthead geometry MUST reside in a single versioned token file (`design/tokens.v1.json` compiled to `static/css/tokens.v1.css`) and shared partials (`templates/partials/`).
- **G-3.2 (No Inline/Ad-Hoc Styling in Templates):** Individual edition or format templates MUST NOT define custom hex colours, font families, or duplicate masthead markup.

### Guardrail 4: API Credit, Timeout & Cached Demo Path Guardrails (Principle 1)
- **G-4.1 (Every Call Has Timeout + Fallback + Cached Demo Path):**
  - Every external HTTP call (Meta Model API, web search, URL scraping) MUST specify an explicit timeout and fallback handler.
  - A complete, pre-recorded **Cached Demo Fixture** (`data/demo_cache/`) covering all stages (search results, scraped sources, Loop 1 rejection + Loop 2 fix audit trail, generated illustrations, and rendered edition stored in SQLite/disk) MUST be maintained and selectable via `DEMO_CACHE_MODE=fallback|always|off` so a live hackathon demo cannot fail due to Wi-Fi or upstream API outages.
- **G-4.2 (\$150 Hackathon Credit Cap Protection):** Every `LoopAgent` is hard-capped at `max_iterations=2`, and per-edition calls are bounded by configuration.

---

## 5. Hard Boundary Conditions & Numerical Invariants

| Domain | Parameter / Metric | Minimum Bound | Maximum Bound | Deterministic Enforcement / Fallback |
| :--- | :--- | :--- | :--- | :--- |
| **Topic Slate** | Active User Topics (`len(topics)`) | **1** (config-driven) | **5** (config-driven) | Validated by Pydantic `TopicSlate`; confirmation required before saving (`FR-003`). |
| **Topic Slate** | Single Topic String Length | **2 chars** | **80 chars** | Trimmed and HTML-escaped on input. |
| **Voice Input** | Audio Upload Duration / Size | **0.5 sec** | **30 sec / 5 MB** | Validated before calling `/v1/asr/transcribe`; falls back to text input on error. |
| **Beat Reporting** | Candidate Stories per Topic | **1 valid story** | **4 stories** | De-duplicated deterministically by normalized URL and title shingle similarity (`<0.75`). |
| **Source Evidence** | Verbatim Extracted Text per URL | **300 chars** | **8,000 chars** | Discard URLs `<300` chars; deterministically slice at `8,000` chars. |
| **Edition Format** | Story Count & Slot Allocation | Defined in `config/formats.json` (`Bulletin`: 1p/3a, `Daily`: 2p/8a, `Weekly`: 3–7p/up to 16a) | Defined in `config/formats.json` | Driven by declarative format configuration; Weekly always has more pages than Daily (`>=3` vs `2`). |
| **Verification Loop** | `LoopAgent` Iterations (`max_iterations`) | **1 pass** | **2 passes** | Hard stop after Iteration 2; invokes deterministic `gatekeeper.py`. |
| **Gatekeeper** | Post-Loop Minimum Verified Claims | **3 (`lead`/`feature`)**, **2 (`secondary`/`brief`)** | **100% Verified** | Strip remaining unsupported claims (`verdict="removed"`); if verified claims `< min`, replace with reserve story (or omit with notice). |
| **Timeouts** | External API / Scrape Timeouts | — | **15s** (Search/Image), **20s** (LLM) | Automatic fallback to secondary source, SVG placeholder, or cached demo snapshot. |

---

## 6. ADK-to-Meta Connection Day-1 Spike & Fallback Strategy (Ref: Section 2 Table)

Because connecting Google ADK (`google-adk`) to Meta's Model API (`https://api.meta.ai/v1`) is marked **Unverified** until the Day 1 spike, implementation MUST follow this strict two-step verification and fallback protocol:

1. **Day-1 Spike (Primary Path — `LiteLlm` Wrapper):**
   - Test `google.adk.models.lite_llm.LiteLlm(model="openai/<confirmed-muse-model-id>", api_base="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])` across three capabilities:
     1. Standard chat completion (`LlmAgent`).
     2. Structured JSON output (`output_schema=PydanticModel`).
     3. Tool calling (`FunctionTool` invocation inside `ParallelAgent` and `LoopAgent`).
2. **Deterministic Fallback Path (Custom ADK `BaseLlm` Adapter):**
   - If `LiteLlm` exhibits incompatibilities with Meta's `/v1/chat/completions` or `/v1/responses` payload shapes (e.g., strict `response_format` or tool-call delta quirks):
     - Implement a lightweight ~80-line custom subclass of Google ADK's `google.adk.models.base_llm.BaseLlm` (`MetaMuseAdkLlm`) using `httpx.AsyncClient` directly against `https://api.meta.ai/v1/chat/completions` (or `/v1/responses`).
     - This preserves **100% of Google ADK's `ParallelAgent`, `LoopAgent`, `SequentialAgent`, and `session.state` orchestration** while giving full deterministic control over the raw HTTP JSON payloads sent to Meta's API.

---

## 7. Testability & Verification Gates (Principle 8)

Every stage and service MUST be independently runnable and testable without live network calls:
1. **Stage-Isolated Mock Execution:** Each stage (Reporting, Editing, Writing/Fact-Checking Loop, Illustration, Formatting) MUST expose a standalone CLI/test entry point that reads a fixture JSON model from `tests/fixtures/`, executes the stage, and writes a validated JSON model.
2. **Fake Clock Scheduler Testing:** The APScheduler (`AsyncIOScheduler` + SQLite job store) wrapper MUST accept an injectable clock/time provider so scheduled edition triggers can be tested deterministically without sleeping.
3. **Adversarial Poison Test:** Automated test proving that an unsupported claim injected into a draft is caught by the Fact-Checker, triggers a Loop 2 rewrite (or Gatekeeper strip), and is escaped and logged in the audit metadata.
