# Nurse LLM

**AI-powered nursing assessment trainer.** Nursing students practice patient assessments by conversing with simulated patients, then receive structured, quote-grounded feedback on their clinical coverage, depth, and critical-finding discovery.

🌐 **Live demo:** hosted on [Streamlit Community Cloud](https://share.streamlit.io/) — see [Deployment](#deployment) below.

---

## How It Works

1. **Select a Patient** — Browse 100+ scenarios across 9 clinical categories (Cardiac, Respiratory, GI, Neuro, Infectious, MSK, Endocrine, Psych, Renal) with filters for category, severity, and keyword search, plus sort by name / severity / category. Paginated 9 per page.

2. **Conduct Your Assessment** — Chat with the simulated patient. Ask about symptoms, medical history, medications, allergies, social and family history, or request vitals and labs. The patient stays in character and only reveals information you specifically ask about.

3. **Watch Your Coverage in Real Time** — The sidebar shows live domain-coverage tracking with depth indicators:
   - ○ Missed · ◐ Surface (1 question) · ◕ Explored (2–3) · ● Deep (4+)
   - A depth-weighted score rewards thorough exploration over checklist-style single questions.

4. **Get Feedback** — When you end the session, you get a structured report with:
   - **Evaluator score** from GPT-4o, considering depth and critical-finding discovery
   - **Depth score** from the tracker (depth-weighted coverage average)
   - Domains covered / missed with depth level per domain
   - Strengths and improvements **grounded in specific quotes** with turn citations (e.g., *"Good follow-up on radiation (Turn 4: 'Does the pain spread anywhere?')"*)
   - Critical findings caught vs. missed, with suggested questions for those missed
   - Notable moments, primary diagnosis, and differential diagnoses

---

## Architecture

- **Frontend:** Streamlit (multi-page app: Home, Patient Chat, Session Review, History)
- **Backend:** Services live in `app/services/` and are called directly from Streamlit — a FastAPI router layer also exists (`app/routers/`) for when the app is deployed as a traditional two-process service.
- **LLM:** OpenAI (GPT-4o-mini for chat + GPT-4o for feedback) **or** Google Gemini (1.5-flash / 1.5-pro) — select via `LLM_PROVIDER`
- **Domain classifier:** Two-stage pipeline — regex keyword rules catch clear cases; a dedicated low-temperature LLM call handles ambiguous ones and supports **multi-label** classification (one question can span multiple domains).
- **Assessment tracker:** Maintains per-domain coverage, question counts, and computes depth-weighted scores.
- **Feedback service:** Post-session LLM call (quality tier) with quote-grounded prompt + JSON mode (OpenAI) or JSON prompt enforcement (Gemini).
- **Data:** 100+ structured patient scenarios (JSON files) validated against a Pydantic schema
- **Database:** SQLite for session history and feedback persistence
- **Evaluation framework:** Standalone `evaluation/` package with baselines (rule-based, few-shot, full pipeline), metrics (fidelity, domain classification, engagement, edge cases, error analysis), ablation runner, and report/plot generators.

---

## Setup

### Prerequisites

- Python 3.11+
- At least one LLM API key:
  - [OpenAI](https://platform.openai.com/api-keys), or
  - [Google Gemini](https://aistudio.google.com/app/apikey)

### Installation

```bash
git clone https://github.com/BaileyM7/Nurse_LLM.git
cd Nurse_LLM

pip install -r requirements.txt

cp .env.example .env
```

Edit `.env` and choose your provider:

```bash
# OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL_NAME=gpt-4o-mini
OPENAI_FEEDBACK_MODEL=gpt-4o

# Or Gemini
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-key-here
GEMINI_MODEL_NAME=gemini-1.5-flash
GEMINI_FEEDBACK_MODEL=gemini-1.5-pro
```

### Running Locally

The Streamlit app calls the service layer directly — no separate API process required:

```bash
python -m streamlit run frontend/Home.py
```

The app opens at `http://localhost:8501`.

> If you want to run the FastAPI backend separately (for API consumers), it's still available:
> ```bash
> python -m uvicorn app.main:app --reload
> ```
> Docs at `http://localhost:8000/docs`.

---

## Deployment

The app is designed to deploy on **Streamlit Community Cloud**:

1. Push this repo to GitHub.
2. On [share.streamlit.io](https://share.streamlit.io), create a new app pointing at `frontend/Home.py` on your `main` branch.
3. Under the app's **Secrets** settings, add:
   ```toml
   LLM_PROVIDER = "openai"
   OPENAI_API_KEY = "sk-your-key-here"
   # or:
   # LLM_PROVIDER = "gemini"
   # GEMINI_API_KEY = "your-key-here"
   ```
4. Python 3.11 is pinned via [`runtime.txt`](runtime.txt) to avoid LangChain/Pydantic-V1 issues on newer Python.

---

## Generating More Patient Cases

The repo includes 100+ curated scenarios. To generate additional cases using the configured LLM:

```bash
# List category targets
python scripts/generate_cases.py --list-categories

# Generate N new cases (auto-numbers from the highest existing case)
python scripts/generate_cases.py --count 10

# Only a specific category
python scripts/generate_cases.py --category cardiac --count 5
```

Each generated case is validated against the `PatientScenario` Pydantic schema before being saved.

---

## Evaluation

A full evaluation harness lives under `evaluation/`:

```bash
cd evaluation
pip install -r requirements.txt

# Run baseline comparison (rule-based vs. few-shot vs. full pipeline)
python runners/run_all_systems.py

# Generate plots and final report
python reports/generate_plots.py
python reports/generate_report.py
```

Results land in `evaluation/results/`: fidelity CSVs, domain confusion matrices, ablation summaries, per-scenario failure rates, and rendered plots. See [`evaluation/METHODOLOGY.md`](evaluation/METHODOLOGY.md) for scoring definitions.

---

## Project Structure

```
Nurse_LLM/
├── app/                            # Python service layer
│   ├── config.py                   # Pydantic settings (reads .env or Streamlit secrets)
│   ├── main.py                     # Optional FastAPI entrypoint
│   ├── models/                     # Pydantic schemas (scenario, session, assessment)
│   ├── routers/                    # FastAPI endpoints (scenarios, chat, sessions)
│   ├── services/
│   │   ├── llm_provider.py         # Multi-provider factory (OpenAI / Gemini, fast + quality tiers)
│   │   ├── llm_service.py          # Patient simulation
│   │   ├── domain_classifier.py    # Keyword-rule + LLM multi-label classifier
│   │   ├── assessment_service.py   # Depth-weighted coverage tracker
│   │   ├── feedback_service.py     # Quote-grounded end-of-session feedback
│   │   ├── scenario_service.py     # JSON scenario loader
│   │   └── session_manager.py      # In-memory + SQLite session persistence
│   └── db/                         # SQLAlchemy models + SQLite setup
├── frontend/                       # Streamlit app
│   ├── Home.py                     # Landing page
│   ├── theme.py                    # Shared visual theme
│   └── pages/
│       ├── 1_Patient_Chat.py       # Scenario picker + active chat + live coverage
│       ├── 2_Session_Review.py     # Post-session feedback report
│       └── 3_History.py            # Past sessions
├── data/scenarios/                 # 100+ patient case JSON files
├── evaluation/                     # Baselines, metrics, ablations, reports
├── scripts/
│   ├── generate_cases.py           # Scenario synthesis via LLM
│   └── seed_db.py                  # DB initialization
├── architecture_diagram.html       # SVG architecture diagram for slides
├── runtime.txt                     # Python version for Streamlit Cloud
└── requirements.txt
```

---

## Team

Team 2 (CS 5804 — Virginia Tech):

- **Madison Henry** — Scenario curation & UI design (`madisonmh@vt.edu`)
- **Yuliya Hrynets** — Evaluation framework & baselines (`yuliyahryn@vt.edu`)
- **Dominic Jibin James** — Multi-provider LLM integration (`dominicjames@vt.edu`)
- **Bailey Malota** — Pipeline, domain classifier, feedback system (`baileym04@vt.edu`)
