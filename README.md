# Nurse LLM

AI-powered nursing assessment chatbot for student education. Students practice patient assessment by conversing with simulated patients, then receive structured feedback on their clinical assessment coverage.

## How It Works

1. **Select a Patient** — Choose from 39 patient scenarios across 9 clinical categories (Cardiac, Respiratory, GI, Neuro, Infectious, MSK, Endocrine, Psych, Renal). Each patient has a unique personality, medical history, and presenting complaint.

2. **Conduct Your Assessment** — Chat with the simulated patient as you would in a clinical setting. Ask about their symptoms, medical history, medications, allergies, social history, and family history. The patient responds in character, only revealing information you ask about.

3. **Get Feedback** — When you end the session, the system generates a detailed feedback report showing:
   - Which of the 7 assessment domains you covered (HPI, ROS, PMH, Medications, Allergies, Social History, Family History)
   - Critical findings you caught or missed
   - Specific strengths and areas for improvement
   - The actual diagnosis and differential diagnoses

## Architecture

- **Backend**: FastAPI (Python) served with uvicorn
- **Frontend**: Streamlit
- **LLM**: OpenAI GPT-4o-mini via LangChain
- **Data**: 39 structured patient scenarios (JSON files)
- **Database**: SQLite for session history and feedback persistence

## Setup

### Prerequisites

- Python 3.11+
- An OpenAI API key ([get one here](https://platform.openai.com/api-keys))

### Installation

```bash
# Clone the repo
git clone https://github.com/your-username/Nurse_LLM.git
cd Nurse_LLM

# Install dependencies
pip install -r requirements.txt

# Create your environment file
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:

```
OPENAI_API_KEY=sk-your-key-here
```

### Running

You need two terminals — one for the backend, one for the frontend.

**Terminal 1 — Start the API:**

```bash
python -m uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. You can view the interactive API docs at `http://localhost:8000/docs`.

**Terminal 2 — Start the frontend:**

```bash
python -m streamlit run frontend/app.py
```

Streamlit will open in your browser at `http://localhost:8501`.

### Generating More Patient Cases

The repo includes 39 hand-crafted patient scenarios. To generate additional cases using the OpenAI API:

```bash
# List available categories
python scripts/generate_cases.py --list-categories

# Generate cases for a specific category
python scripts/generate_cases.py --category cardiac --count 5

# Generate cases across all categories
python scripts/generate_cases.py
```

## Project Structure

```
Nurse_LLM/
├── app/                    # FastAPI backend
│   ├── main.py             # App entrypoint
│   ├── config.py           # Settings (.env)
│   ├── models/             # Pydantic schemas (scenario, session, assessment)
│   ├── routers/            # API endpoints (scenarios, chat, sessions)
│   ├── services/           # Business logic (LLM, assessment tracking, feedback)
│   └── db/                 # SQLite persistence
├── frontend/               # Streamlit UI
│   ├── app.py              # Landing page
│   └── pages/              # Chat, Session Review, History
├── data/scenarios/         # Patient case JSON files (39 cases)
├── scripts/                # Case generation & DB setup
└── requirements.txt
```
