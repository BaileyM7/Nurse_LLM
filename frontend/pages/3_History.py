import httpx
import streamlit as st

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Session History", page_icon="📊", layout="wide")
st.title("Session History")

# Fetch all sessions
try:
    resp = httpx.get(f"{API_URL}/api/sessions/")
    resp.raise_for_status()
    sessions = resp.json()
except Exception as e:
    st.error(f"Could not load sessions: {e}")
    st.stop()

if not sessions:
    st.info("No sessions yet. Complete a patient assessment to see your history here.")
    st.stop()

# Display sessions as a table
st.subheader(f"Total Sessions: {len(sessions)}")

for session in reversed(sessions):  # Most recent first
    status_icon = "🟢" if session["status"] == "active" else "✅"
    with st.expander(
        f"{status_icon} Session {session['session_id']} — "
        f"Scenario: {session['scenario_id']} — "
        f"Coverage: {session['coverage_score']:.0f}% — "
        f"Turns: {session['turn_count']}"
    ):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Status", session["status"].capitalize())
        with col2:
            st.metric("Coverage Score", f"{session['coverage_score']:.0f}%")
        with col3:
            st.metric("Total Turns", session["turn_count"])

        st.caption(f"Started: {session['start_time']}")

        if session["status"] == "ended":
            if st.button(f"View Feedback", key=f"fb_{session['session_id']}"):
                st.session_state.session_id = session["session_id"]
                st.session_state.session_active = False
                st.switch_page("pages/2_Session_Review.py")
