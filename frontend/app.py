import streamlit as st

st.set_page_config(
    page_title="Nurse LLM - Patient Assessment Trainer",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Nurse LLM")
st.subheader("AI-Powered Patient Assessment Trainer")

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

# Check API connection
API_URL = "http://localhost:8000"

try:
    import httpx
    response = httpx.get(f"{API_URL}/")
    if response.status_code == 200:
        st.success("API connected successfully")
    else:
        st.warning("API returned unexpected status. Make sure the backend is running.")
except Exception:
    st.error(
        "Cannot connect to the API. Please start the backend first:\n\n"
        "`uvicorn app.main:app --reload`"
    )
