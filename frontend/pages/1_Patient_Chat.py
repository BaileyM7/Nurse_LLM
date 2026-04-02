import asyncio
import time

import streamlit as st

from app.config import settings
from app.models.session import ChatMessage, MessageRole
from app.services.scenario_service import scenario_service
from app.services.llm_service import llm_service
from app.services.feedback_service import feedback_service
from app.services.session_manager import session_manager

st.set_page_config(page_title="Patient Chat", page_icon="💬", layout="wide")

# ── Session State Initialization ─────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_active" not in st.session_state:
    st.session_state.session_active = False
if "patient_name" not in st.session_state:
    st.session_state.patient_name = ""
if "chief_complaint" not in st.session_state:
    st.session_state.chief_complaint = ""
if "domains_covered" not in st.session_state:
    st.session_state.domains_covered = []
if "turn_count" not in st.session_state:
    st.session_state.turn_count = 0
if "start_time" not in st.session_state:
    st.session_state.start_time = None
if "vitals_revealed" not in st.session_state:
    st.session_state.vitals_revealed = {}
if "labs_revealed" not in st.session_state:
    st.session_state.labs_revealed = {}


# ── Helper Functions ─────────────────────────────────────────────────────────
def fetch_scenarios():
    try:
        summaries = scenario_service.list_scenarios()
        return [s.model_dump() for s in summaries]
    except Exception as e:
        st.error(f"Failed to load scenarios: {e}")
        return []


def start_session(scenario_id: str):
    try:
        scenario = scenario_service.get_scenario(scenario_id)
        if not scenario:
            st.error(f"Scenario '{scenario_id}' not found")
            return

        session = session_manager.create_session(scenario_id)
        llm_service.start_session(session["session_id"], scenario)

        st.session_state.session_id = session["session_id"]
        st.session_state.session_active = True
        st.session_state.patient_name = scenario.name
        st.session_state.chief_complaint = scenario.chief_complaint
        st.session_state.messages = []
        st.session_state.domains_covered = []
        st.session_state.turn_count = 0
        st.session_state.start_time = time.time()
        st.session_state.vitals_revealed = {}
        st.session_state.labs_revealed = {}
    except Exception as e:
        st.error(f"Failed to start session: {e}")


def send_message(message: str):
    try:
        sid = st.session_state.session_id
        session = session_manager.get_session(sid)
        if not session:
            st.error("Session not found")
            return

        if session["turn_count"] >= settings.max_turns:
            st.error(f"Maximum turns ({settings.max_turns}) reached. Please end the session.")
            return

        # Get LLM response (async call)
        patient_response = asyncio.run(
            llm_service.get_patient_response(sid, message)
        )

        # Record messages in-memory
        session["messages"].append(ChatMessage(
            role=MessageRole.STUDENT,
            content=message,
            domain_explored=patient_response.domain_explored,
        ))
        session["messages"].append(ChatMessage(
            role=MessageRole.PATIENT,
            content=patient_response.dialogue,
        ))
        session["turn_count"] += 1

        # Persist to SQLite
        session_manager.save_message(sid, "student", message, domain=patient_response.domain_explored)
        session_manager.save_message(sid, "patient", patient_response.dialogue)

        # Update assessment tracker
        session["tracker"].update(
            domain_explored=patient_response.domain_explored,
            confidence=patient_response.domain_confidence,
            student_message=message,
        )

        # Update Streamlit state
        st.session_state.messages.append({"role": "student", "content": message})
        st.session_state.messages.append({
            "role": "patient",
            "content": patient_response.dialogue,
        })
        st.session_state.turn_count = session["turn_count"]
        st.session_state.domains_covered = session["tracker"].get_covered_domains()

        # Track revealed vitals/labs
        if patient_response.vitals_revealed:
            st.session_state.vitals_revealed.update(patient_response.vitals_revealed)
        if patient_response.labs_revealed:
            st.session_state.labs_revealed.update(patient_response.labs_revealed)

    except Exception as e:
        st.error(f"Error communicating with patient: {e}")


def end_session():
    try:
        sid = st.session_state.session_id
        session = session_manager.get_session(sid)
        if not session:
            st.error("Session not found")
            return

        session["status"] = "ended"

        # Clean up LLM session
        llm_service.end_session(sid)

        # Generate feedback
        scenario = scenario_service.get_scenario(session["scenario_id"])
        assessment = session["tracker"].get_result()

        feedback = asyncio.run(
            feedback_service.generate_feedback(
                session_id=sid,
                scenario=scenario,
                messages=session["messages"],
                assessment=assessment,
            )
        )
        session["feedback"] = feedback

        # Persist to SQLite
        session_manager.end_session(sid, score=feedback.overall_score)
        session_manager.save_feedback(sid, feedback)

        st.session_state.session_active = False
    except Exception as e:
        st.error(f"Failed to end session: {e}")


SEVERITY_BADGES = {
    "critical": "🔴 CRITICAL",
    "high": "🟠 HIGH",
    "medium": "🟡 MEDIUM",
    "low": "🟢 LOW",
}


# ─────────────────────────────────────────────────────────────────────────────
# MODE 1: Patient Selection (main pane — no active session)
# ─────────────────────────────────────────────────────────────────────────────
if not st.session_state.session_active and not st.session_state.messages:
    st.title("Select a Patient")

    scenarios = fetch_scenarios()
    if not scenarios:
        st.warning("No scenarios available.")
        st.stop()

    # ── Filter bar ────────────────────────────────────────────────────────
    categories = sorted(set(s.get("category", "Other") or "Other" for s in scenarios))

    filter_cols = st.columns([2, 2, 3])
    with filter_cols[0]:
        cat_filter = st.selectbox("Category", ["All"] + categories, key="cat_filter")
    with filter_cols[1]:
        sev_filter = st.selectbox("Severity", ["All", "Critical", "High", "Medium", "Low"], key="sev_filter")
    with filter_cols[2]:
        search = st.text_input("Search", placeholder="Name or complaint...", key="search")

    # Apply filters
    filtered = scenarios
    if cat_filter != "All":
        filtered = [s for s in filtered if s.get("category") == cat_filter]
    if sev_filter != "All":
        filtered = [s for s in filtered if (s.get("severity") or "").lower() == sev_filter.lower()]
    if search:
        q = search.lower()
        filtered = [s for s in filtered if q in s["name"].lower() or q in s["chief_complaint"].lower()]

    st.caption(f"Showing {len(filtered)} of {len(scenarios)} patients")

    # Inject CSS to make all patient cards the same height per row
    st.markdown("""
    <style>
    /* Equal-height cards within each row */
    div[data-testid="stHorizontalBlock"] {
        align-items: stretch;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        height: 100%;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div[data-testid="stVerticalBlockBorderWrapper"] > div {
        height: 100%;
        display: flex;
        flex-direction: column;
    }
    </style>
    """, unsafe_allow_html=True)

    # Cap complaint length so cards have uniform text
    COMPLAINT_MAX = 80

    # ── Card grid (3 columns) ────────────────────────────────────────────
    for row_start in range(0, len(filtered), 3):
        row_items = filtered[row_start:row_start + 3]
        cols = st.columns(3)

        for col, s in zip(cols, row_items):
            sev = (s.get("severity") or "").lower()
            badge = SEVERITY_BADGES.get(sev, "⚪ UNKNOWN")
            cat_label = s.get("category") or ""
            complaint = s["chief_complaint"]
            if len(complaint) > COMPLAINT_MAX:
                complaint = complaint[:COMPLAINT_MAX].rsplit(" ", 1)[0] + "..."

            with col:
                with st.container(border=True):
                    st.markdown(f"**{s['name']}**")
                    st.caption(f"{s['age']}yo {s['sex']} · {cat_label} · {badge}")
                    st.markdown(f"*\"{complaint}\"*")
                    if st.button("Start Assessment", key=f"sel_{s['patient_id']}", use_container_width=True):
                        start_session(s["patient_id"])
                        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# MODE 2: Session complete (no active session, but messages exist)
# ─────────────────────────────────────────────────────────────────────────────
elif not st.session_state.session_active and st.session_state.messages:
    st.title("Session Complete")
    st.success("Go to **Session Review** in the sidebar to see your feedback.")

    if st.button("Start New Session"):
        st.session_state.messages = []
        st.session_state.session_id = None
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# MODE 3: Active chat session (sidebar + chat)
# ─────────────────────────────────────────────────────────────────────────────
else:
    # ── Sidebar: session info + coverage tracker ─────────────────────────
    with st.sidebar:
        st.header(f"Patient: {st.session_state.patient_name}")
        st.caption(f"Complaint: {st.session_state.chief_complaint}")

        # Timer
        if st.session_state.start_time:
            elapsed = int(time.time() - st.session_state.start_time)
            minutes, seconds = divmod(elapsed, 60)
            st.metric("Time Elapsed", f"{minutes:02d}:{seconds:02d}")

        st.metric("Turns", st.session_state.turn_count)

        # Assessment Coverage
        st.subheader("Assessment Coverage")
        all_domains = ["HPI", "ROS", "PMH", "Medications", "Allergies", "Social_History", "Family_History"]
        covered = st.session_state.domains_covered

        for domain in all_domains:
            is_covered = domain in covered
            label = domain.replace("_", " ")
            st.progress(1.0 if is_covered else 0.0, text=f"{'✓' if is_covered else '○'} {label}")

        coverage_pct = len(covered) / len(all_domains) * 100
        st.metric("Coverage Score", f"{coverage_pct:.0f}%")

        # Revealed vitals
        if st.session_state.vitals_revealed:
            st.subheader("Vitals")
            for k, v in st.session_state.vitals_revealed.items():
                st.text(f"{k}: {v}")

        # Revealed labs
        if st.session_state.labs_revealed:
            st.subheader("Lab Results")
            for k, v in st.session_state.labs_revealed.items():
                st.text(f"{k}: {v}")

        st.divider()
        if st.button("End Session", type="secondary", use_container_width=True):
            end_session()
            st.rerun()

    # ── Main area: Chat ──────────────────────────────────────────────────
    st.title("Patient Assessment Chat")

    # Display chat messages
    for msg in st.session_state.messages:
        role = msg["role"]
        if role == "student":
            with st.chat_message("user"):
                st.write(msg["content"])
        else:
            with st.chat_message("assistant", avatar="🏥"):
                st.write(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask your patient a question..."):
        # Show student message immediately
        with st.chat_message("user"):
            st.write(prompt)

        # Get and show patient response
        with st.chat_message("assistant", avatar="🏥"):
            with st.spinner("Patient is responding..."):
                send_message(prompt)
                if st.session_state.messages:
                    st.write(st.session_state.messages[-1]["content"])

        st.rerun()  # Refresh sidebar coverage
