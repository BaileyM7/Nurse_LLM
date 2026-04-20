import sys
from pathlib import Path

# Ensure repo root is on sys.path so "from app..." imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from frontend.theme import inject_theme
from app.services.session_manager import session_manager

st.set_page_config(page_title="Session History", page_icon="🏥", layout="wide")
inject_theme()

st.title("Session History")

# Fetch all sessions directly from the service
try:
    sessions = session_manager.list_sessions()
except Exception as e:
    st.error(f"Could not load sessions: {e}")
    st.stop()

if not sessions:
    st.info("No sessions yet. Complete a patient assessment to see your history here.")
    st.stop()

# Display sessions as a table
st.subheader(f"Total Sessions: {len(sessions)}")

for session in sessions:  # Already sorted most recent first by session_manager
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
