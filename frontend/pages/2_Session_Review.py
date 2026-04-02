import sys
from pathlib import Path

# Ensure repo root is on sys.path so "from app..." imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from app.services.session_manager import session_manager

st.set_page_config(page_title="Session Review", page_icon="📋", layout="wide")
st.title("Session Review")

session_id = st.session_state.get("session_id")

if not session_id:
    st.info("No session to review. Start and complete a patient assessment first.")
    st.stop()

if st.session_state.get("session_active", False):
    st.warning("Your session is still active. End it in the Patient Chat page first.")
    st.stop()

# Get feedback — check in-memory first, then SQLite
feedback = None
session = session_manager.get_session(session_id)
if session and session.get("feedback"):
    feedback = session["feedback"].model_dump()
else:
    stored = session_manager.get_stored_feedback(session_id)
    if stored:
        feedback = stored.model_dump()

if not feedback:
    st.error("Could not load feedback for this session.")
    st.stop()

# ── Overall Score ────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Overall Score", f"{feedback['overall_score']:.0f}/100")
with col2:
    st.metric("Domains Covered", f"{len(feedback['domains_covered'])}/7")
with col3:
    st.metric("Diagnosis", feedback["diagnosis"])

st.divider()

# ── Summary ──────────────────────────────────────────────────────────────────
if feedback.get("summary"):
    st.subheader("Summary")
    st.write(feedback["summary"])

# ── Domain Coverage ──────────────────────────────────────────────────────────
st.subheader("Assessment Coverage")
col_covered, col_missed = st.columns(2)

with col_covered:
    st.markdown("**Domains Covered**")
    for domain in feedback["domains_covered"]:
        st.markdown(f"- ✅ {domain.replace('_', ' ')}")

with col_missed:
    st.markdown("**Domains Missed**")
    for domain in feedback["domains_missed"]:
        st.markdown(f"- ❌ {domain.replace('_', ' ')}")

st.divider()

# ── Strengths & Improvements ────────────────────────────────────────────────
col_str, col_imp = st.columns(2)

with col_str:
    st.subheader("Strengths")
    for item in feedback.get("strengths", []):
        st.markdown(f"- 💪 {item}")

with col_imp:
    st.subheader("Areas for Improvement")
    for item in feedback.get("improvements", []):
        st.markdown(f"- 📝 {item}")

st.divider()

# ── Critical Findings ───────────────────────────────────────────────────────
st.subheader("Critical Findings")
col_caught, col_missed_findings = st.columns(2)

with col_caught:
    st.markdown("**Caught**")
    for f in feedback.get("critical_findings_caught", []):
        st.markdown(f"- ✅ {f}")
    if not feedback.get("critical_findings_caught"):
        st.caption("None identified")

with col_missed_findings:
    st.markdown("**Missed**")
    for f in feedback.get("critical_findings_missed", []):
        st.markdown(f"- ⚠️ {f}")
    if not feedback.get("critical_findings_missed"):
        st.caption("None missed - great job!")

st.divider()

# ── Turn Highlights ──────────────────────────────────────────────────────────
if feedback.get("turn_highlights"):
    st.subheader("Notable Moments")
    for highlight in feedback["turn_highlights"]:
        with st.expander(f"Turn {highlight.get('turn', '?')}: {highlight.get('student_said', '')[:60]}..."):
            st.markdown(f"**You said:** {highlight.get('student_said', '')}")
            st.markdown(f"**Commentary:** {highlight.get('commentary', '')}")

# ── Differential Diagnoses ──────────────────────────────────────────────────
if feedback.get("differential_diagnoses"):
    st.subheader("Differential Diagnoses to Consider")
    for dx in feedback["differential_diagnoses"]:
        st.markdown(f"- {dx}")
