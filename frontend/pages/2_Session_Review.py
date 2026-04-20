import sys
from pathlib import Path

# Ensure repo root is on sys.path so "from app..." imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from frontend.theme import inject_theme
from app.services.session_manager import session_manager

st.set_page_config(page_title="Session Review", page_icon="🏥", layout="wide")
inject_theme()

st.markdown('<div class="case-eyebrow">Post-session feedback</div>', unsafe_allow_html=True)
st.title("Session Review")
st.caption("Review your coverage, strengths, missed findings, and follow-up considerations.")

session_id = st.session_state.get("session_id")

if not session_id:
    st.info("No session to review. Start and complete a patient assessment first.")
    st.stop()

if st.session_state.get("session_active", False):
    st.warning("Your session is still active. End it in the Patient Chat page first.")
    st.stop()

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

duration = st.session_state.get("session_duration", 0)
minutes, seconds = divmod(duration, 60)
duration_str = f"{minutes:02d}:{seconds:02d}"

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Overall Score", f"{feedback['overall_score']:.0f}/100")
with col2:
    st.metric("Domains Covered", f"{len(feedback['domains_covered'])}/7")
with col3:
    st.metric("Time Taken", duration_str)

st.markdown(
    f"""
    <div class="diagnosis-callout">
        <span class="diagnosis-label">Primary diagnosis</span>
        <span class="diagnosis-text">{feedback['diagnosis']}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()

# Summary
if feedback.get("summary"):
    st.markdown('<div class="section-kicker">Performance overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Summary</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="feature-panel">{feedback["summary"]}</div>', unsafe_allow_html=True)
    st.markdown("<div style='height: 0.9rem;'></div>", unsafe_allow_html=True)

# Coverage
st.markdown('<div class="section-kicker">Assessment breadth</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Assessment Coverage</div>', unsafe_allow_html=True)

col_covered, col_missed = st.columns(2)

with col_covered:
    with st.container(border=True):
        st.markdown("**Domains Covered**")
        if feedback.get("domains_covered"):
            for domain in feedback["domains_covered"]:
                pretty = domain.replace("_", " ").title()
                st.markdown(
                    f"<span style='color:#4E5A47; font-weight:700;'>Covered</span> — {pretty}",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No domains were covered.")

with col_missed:
    with st.container(border=True):
        st.markdown("**Domains Missed**")
        if feedback.get("domains_missed"):
            for domain in feedback["domains_missed"]:
                pretty = domain.replace("_", " ").title()
                st.markdown(
                    f"<span style='color:#A86248; font-weight:700;'>Missed</span> — {pretty}",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No domains missed.")

st.markdown("<div style='height: 0.9rem;'></div>", unsafe_allow_html=True)

# Strengths / improvement
st.markdown('<div class="section-kicker">Coaching notes</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Strengths and Improvements</div>', unsafe_allow_html=True)

col_str, col_imp = st.columns(2)

with col_str:
    with st.container(border=True):
        st.markdown("**Strengths**")
        if feedback.get("strengths"):
            for item in feedback["strengths"]:
                st.markdown(f"- {item}")
        else:
            st.caption("No strengths listed.")

with col_imp:
    with st.container(border=True):
        st.markdown("**Areas for Improvement**")
        if feedback.get("improvements"):
            for item in feedback["improvements"]:
                st.markdown(f"- {item}")
        else:
            st.caption("No improvement notes listed.")

st.markdown("<div style='height: 0.9rem;'></div>", unsafe_allow_html=True)

# Critical findings
st.markdown('<div class="section-kicker">Clinical misses</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Critical Findings</div>', unsafe_allow_html=True)

col_caught, col_missed_findings = st.columns(2)

with col_caught:
    with st.container(border=True):
        st.markdown("**Caught**")
        if feedback.get("critical_findings_caught"):
            for finding in feedback["critical_findings_caught"]:
                st.markdown(
                    f"<span style='color:#4E5A47; font-weight:700;'>Identified</span> — {finding}",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("None identified.")

with col_missed_findings:
    with st.container(border=True):
        st.markdown("**Missed**")
        if feedback.get("critical_findings_missed"):
            for finding in feedback["critical_findings_missed"]:
                st.markdown(
                    f"<span style='color:#A86248; font-weight:700;'>Missed</span> — {finding}",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("None missed — great job.")

st.markdown("<div style='height: 0.9rem;'></div>", unsafe_allow_html=True)

# Notable moments
if feedback.get("turn_highlights"):
    st.markdown('<div class="section-kicker">Conversation review</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Notable Moments</div>', unsafe_allow_html=True)

    for highlight in feedback["turn_highlights"]:
        turn_num = highlight.get("turn", "?")
        student_said = highlight.get("student_said", "")
        preview = student_said[:60] + ("..." if len(student_said) > 60 else "")

        with st.expander(f"Turn {turn_num}: {preview}"):
            st.markdown(f"**You said:** {student_said}")
            st.markdown(f"**Commentary:** {highlight.get('commentary', '')}")

    st.markdown("<div style='height: 0.9rem;'></div>", unsafe_allow_html=True)

# Differentials
if feedback.get("differential_diagnoses"):
    st.markdown('<div class="section-kicker">Clinical reasoning</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Differential Diagnoses to Consider</div>', unsafe_allow_html=True)

    items = "".join(f"<li>{dx}</li>" for dx in feedback["differential_diagnoses"])
    st.markdown(
        f'<div class="feature-panel"><ul style="margin:0; padding-left:1.3rem;">{items}</ul></div>',
        unsafe_allow_html=True,
    )