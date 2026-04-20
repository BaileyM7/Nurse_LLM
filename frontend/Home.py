import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from frontend.theme import inject_theme

st.set_page_config(
    page_title="Nurse LLM - Patient Assessment Trainer",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()

st.markdown('<div class="case-eyebrow">Training Tool</div>', unsafe_allow_html=True)

st.title("Nurse LLM")

st.markdown(
    "<div style='font-size:1.2rem; color:#7B8A74; margin-bottom:1rem;'>"
    "AI-Powered Patient Assessment Trainer"
    "</div>",
    unsafe_allow_html=True
)

st.markdown("""
Welcome to the Nursing Assessment Practice Tool. This application helps nursing students
practice patient assessment skills through simulated patient interactions.

### How it works
1. **Select a Patient** - Choose a patient scenario from the available cases
2. **Conduct Your Assessment** - Ask the patient questions as you would in a clinical setting
3. **Get Feedback** - Receive detailed feedback on your assessment coverage and technique

### Assessment Domains
The system tracks your coverage across these clinical domains:
- **HPI** - History of Present Illness
- **ROS** - Review of Systems
- **PMH** - Past Medical History
- **Medications** - Current medications
- **Allergies** - Known allergies
- **Social History** - Lifestyle and social factors
- **Family History** - Family medical history

### Get Started
Use the sidebar to navigate to **Patient Chat** and begin a session.
""")