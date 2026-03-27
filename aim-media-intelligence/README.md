# AIM Media House – YouTube Intelligence System

An automated, multi-agent pipeline that extracts, processes, and analyzes video transcripts from the **AIM Media House** (Analytics India Magazine) YouTube channel — transforming raw content into structured intelligence.

---

## What This System Does

Given the AIM Media House YouTube channel (1,230 videos), this system:

1. **Collects** all video metadata and transcripts via YouTube APIs
2. **Cleans** transcripts — removes timestamps, filler words, and ASR noise
3. **Analyzes** each video for entities (people, companies, tools), topic categories, and sentiment — all powered by Gemini
4. **Generates** cross-video insights: viral content patterns, content gaps, and channel evolution
5. **Reports** with ~1000-word annual summaries per year in HTML format
6. **Presents** everything through a 9-page interactive Streamlit dashboard

---

## Architecture

```
YouTube Channel (AIM Media House — 1,230 videos)
      │
      ▼
┌────────────────────────────────────────────────────┐
│  OrchestratorAgent  (Plan → Execute → Observe → Reflect)
│  • Queries DB state, asks Gemini what to run next  │
│  • Quality-checks each agent's output (0–10 score) │
│  • Retries on low quality, rotates models on quota │
│  • MessageBus for inter-agent pub/sub events       │
└──────────────────────┬─────────────────────────────┘
                       │
      ┌────────────────┼────────────────┐
      ▼                ▼                ▼
┌───────────┐   ┌───────────┐   ┌──────────────────────┐
│ Agent 1   │   │ Agent 2   │   │ Agent 3              │
│ Data      │   │ Transcript│   │ Analysis             │
│ Collector │   │ Processor │   │ (Gemini 2.5 Flash)   │
│           │   │           │   │                      │
│ YouTube   │   │ Strip     │   │ Entity extraction    │
│ Data API  │   │ timestamps│   │ Topic classification │
│ +Transcript   │ Filler    │   │ Sentiment analysis   │
│ API (8x   │   │ words     │   │ Relationship mapping │
│ parallel) │   │ Normalize │   │ 10 videos / call     │
└───────────┘   └───────────┘   └──────────────────────┘
                        │
                 ┌──────▼──────┐
                 │  SQLite DB  │
                 └──────┬──────┘
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌─────────────────────┐
│  Agent 4     │ │  Agent 5     │ │  Dashboard          │
│  Insights    │ │  Report      │ │  (Streamlit, 9 pages)
│              │ │  Generator   │ │                     │
│ Viral pattern│ │ 1000-word    │ │ Overview, Entities  │
│ Content gaps │ │ yearly       │ │ Topics, Trends      │
│ Channel evo  │ │ summaries    │ │ Sentiment, KG       │
│              │ │ HTML report  │ │ Insights, Reports   │
└──────────────┘ └──────────────┘ │ Q&A Chat            │
                                   └─────────────────────┘
```

---

## Setup

### 1. Clone & install

```bash
git clone <repo-url>
cd aim-media-intelligence
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
```

Edit `.env`:
```
YOUTUBE_API_KEY=your_youtube_data_api_v3_key
GEMINI_API_KEY=your_gemini_api_key
```

**Getting API keys:**

**YouTube Data API v3:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Enable **YouTube Data API v3** for your project
3. Create an API key under Credentials
4. In the key settings → Application Restrictions: **None** → API Restrictions: **Don't restrict key**

> If you see `"Requests to this API are blocked"`, the key has restrictions enabled. Remove them in Cloud Console.

**Gemini API:**
- Get a free key at [Google AI Studio](https://aistudio.google.com/)
- The system automatically detects which Gemini model is available for your key and rotates through the pool if one hits its daily quota

### 3. Run the pipeline

**Fully autonomous (recommended):**
```bash
python main.py --mode auto
```
The OrchestratorAgent uses Gemini to plan and drive the pipeline with quality checks and reflection.

**Full pipeline (sequential stages):**
```bash
python main.py --mode full
```

**Individual stages:**
```bash
python main.py --mode collect    # fetch video metadata + transcripts
python main.py --mode process    # clean transcripts
python main.py --mode analyze    # entity / topic / sentiment analysis
python main.py --mode insights   # viral patterns, content gaps, evolution
python main.py --mode report     # generate annual HTML report
python main.py --mode dashboard  # launch Streamlit dashboard
```

> **Incremental by design:** Every stage is safe to re-run. Already-processed videos are skipped automatically. You can run `--mode analyze` at any point and it will pick up only unprocessed transcripts.

### 4. Generate architecture diagram

```bash
python generate_architecture.py
# Output: data/outputs/architecture_diagram.png
```

### 5. Launch dashboard

```bash
streamlit run dashboard/app.py
```
Open `http://localhost:8501`

---

## Channel & Data Facts

| Property | Value |
|---|---|
| Channel | AIM Media House (Analytics India Magazine) |
| Channel ID | `UCh7cV9a7zfACq8f00hJIdSg` |
| Total videos | 1,230 |
| Videos with transcripts | 307 (~25%) |
| Videos analyzed | 155 (50% of transcribed) |
| Unique entities extracted | 910 |
| Relationships mapped | 725 |
| Years in dataset | 2023 – 2026 |

**Why only 307 transcripts?** AIM Media House publishes many conference event recordings (MachineCon, MLDS, etc.) which are short clips without auto-generated captions. Only full-length videos with English captions yield transcripts.

---

## Analysis Results (from 155 videos)

**Top Entities:**
- AI, LLMs, GenAI, Google, ChatGPT, OpenAI, Agentic AI, Microsoft, NVIDIA

**Top Topics:**
- GenAI (103 videos), Industry News (87), Data Science (47), Career & Education (45), Cloud & Infrastructure (40), Startups (35)

**Sentiment:**
- Positive: 73% | Neutral: 20% | Critical: 7%

**Key Insight:**
> The channel pivoted significantly toward GenAI content in 2025. MLOps for deploying GenAI in the Indian enterprise context is the largest underserved topic gap.

---

## Multi-Agent Design

The system implements a **Plan → Execute → Observe → Reflect** agentic loop:

1. **OrchestratorAgent** queries current DB state and asks Gemini which agents need to run
2. Agents communicate via a **MessageBus** (pub/sub) — fully decoupled
3. After each agent, a **quality assessor** scores output (0–10); low scores trigger retries
4. On Gemini quota exhaustion, the system **automatically rotates** to the next available model in the pool: `gemini-2.5-flash-lite → gemini-3-flash-preview → gemini-3.1-flash-lite-preview → gemini-flash-lite-latest`
5. Post-pipeline **reflection** step where Gemini evaluates overall quality and confidence

Run `--mode auto` to see the full agentic loop in action.

---

## LLM Strategy & Rate Limiting

| Setting | Value |
|---|---|
| Primary model | `gemini-2.5-flash-lite` |
| Fallback pool | 4 models (auto-rotated on quota) |
| Rate limit | 28 RPM (token bucket) |
| Batch size | 10 videos per Gemini call |
| Token efficiency | InsightsAgent uses pre-aggregated DB data only |

**Free tier note:** Gemini free tier has per-model daily limits (typically 20–50 RPD). The model rotation pool ensures the pipeline continues even when individual models are exhausted. Run `--mode analyze` across multiple sessions if needed — already-analyzed videos are never re-processed.

---

## Known Limitations

- **~75% of videos have no transcript** — AIM Media House event clips lack auto-captions. Speech-to-Text (e.g. Whisper) could recover these but requires significant compute.
- **Analysis covers 2023–2026 only** — videos before 2023 have no transcripts in the current dataset.
- **Gemini free tier daily limits** — processing all 307 transcripts takes ~3 API sessions across different days or models. The model rotation and incremental design handle this automatically.
- **PDF export** requires system-level dependencies: `brew install pango libffi` (macOS). HTML report works without any extra dependencies.

---

## Project Structure

```
aim-media-intelligence/
├── main.py                          ← Entry point (--mode auto/full/collect/...)
├── config.py                        ← API keys, model pool, settings
├── requirements.txt
├── .env.example                     ← Copy to .env, add keys
├── generate_architecture.py         ← Generates architecture_diagram.png
├── README.md
│
├── agents/
│   ├── orchestrator.py              ← Master agent: Plan→Execute→Observe→Reflect
│   ├── message_bus.py               ← Inter-agent pub/sub communication
│   ├── base_agent.py                ← Gemini client + model rotation + rate limiter
│   ├── collector.py                 ← Agent 1: YouTube API + parallel transcript fetch
│   ├── processor.py                 ← Agent 2: Transcript cleaning
│   ├── analyzer.py                  ← Agent 3: Entity/topic/sentiment (batched, 10/call)
│   ├── insights_agent.py            ← Agent 4: Viral patterns, content gaps, evolution
│   └── reporter.py                  ← Agent 5: Yearly summaries + HTML report
│
├── database/
│   └── manager.py                   ← Full SQLite schema + all query functions
│
├── utils/
│   ├── helpers.py                   ← Text cleaning, JSON parsing utilities
│   └── rate_limiter.py              ← Token bucket rate limiter
│
├── dashboard/
│   └── app.py                       ← Streamlit dashboard (9 pages)
│
└── data/
    ├── aim_intelligence.db          ← SQLite database (auto-created on first run)
    ├── pipeline.log                 ← Execution log
    └── outputs/
        ├── architecture_diagram.png ← System architecture visual
        └── reports/
            ├── annual_report.html   ← Generated annual report (2025–2026)
            └── insights.json        ← Cross-video insights (viral, gaps, evolution)
```

---

## Deliverables

| Item | Location |
|---|---|
| Source code | This repository (18 Python files) |
| Architecture diagram | `data/outputs/architecture_diagram.png` |
| Annual HTML report | `data/outputs/reports/annual_report.html` |
| Cross-video insights | `data/outputs/reports/insights.json` |
| Interactive dashboard | `streamlit run dashboard/app.py` |
