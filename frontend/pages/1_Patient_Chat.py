import asyncio
import sys
import time
from pathlib import Path

# Ensure repo root is on sys.path so "from app..." imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st


def run_async(coro):
    """Run an async coroutine safely, even if an event loop is already running."""
    try:
        asyncio.get_running_loop()
        # Loop already running (Streamlit) — run in a new thread with its own loop
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(lambda: asyncio.run(coro))
            return future.result(timeout=60)
    except RuntimeError:
        # No loop running — safe to use asyncio.run directly
        return asyncio.run(coro)

from app.config import settings
from app.models.session import ChatMessage, MessageRole
from app.services.scenario_service import scenario_service
from app.services.llm_service import llm_service
from app.services.feedback_service import feedback_service
from app.services.session_manager import session_manager
from app.services.domain_classifier import domain_classifier

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
if "patient_page" not in st.session_state:
    st.session_state.patient_page = 0
if "last_filter_key" not in st.session_state:
    st.session_state.last_filter_key = ""


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

        # Classify the student's question via dedicated classifier (keyword + LLM fallback)
        classification = run_async(domain_classifier.classify(message))
        primary_domain = classification.domains[0] if classification.domains else "conversational"

        # Get patient dialogue from simulation LLM
        patient_response = run_async(
            llm_service.get_patient_response(sid, message)
        )
        # Override the sim's self-reported domain with the dedicated classifier result
        patient_response.domain_explored = primary_domain
        patient_response.domain_confidence = classification.confidence

        # Record messages in-memory
        session["messages"].append(ChatMessage(
            role=MessageRole.STUDENT,
            content=message,
            domain_explored=primary_domain,
        ))
        session["messages"].append(ChatMessage(
            role=MessageRole.PATIENT,
            content=patient_response.dialogue,
        ))
        session["turn_count"] += 1

        # Persist to SQLite
        session_manager.save_message(sid, "student", message, domain=primary_domain)
        session_manager.save_message(sid, "patient", patient_response.dialogue)

        # Update assessment tracker with multi-label domains
        session["tracker"].update(
            domains=classification.domains,
            confidence=classification.confidence,
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

        feedback = run_async(
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

    filter_cols = st.columns([2, 2, 2, 3])
    with filter_cols[0]:
        cat_filter = st.selectbox("Category", ["All"] + categories, key="cat_filter")
    with filter_cols[1]:
        sev_filter = st.selectbox("Severity", ["All", "Critical", "High", "Medium", "Low"], key="sev_filter")
    with filter_cols[2]:
        sort_by = st.selectbox("Sort by", ["Default", "Name", "Severity", "Category"], key="sort_filter")
    with filter_cols[3]:
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

    # Apply sort
    SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    if sort_by == "Name":
        filtered = sorted(filtered, key=lambda s: s["name"].lower())
    elif sort_by == "Severity":
        filtered = sorted(filtered, key=lambda s: SEVERITY_ORDER.get((s.get("severity") or "").lower(), 99))
    elif sort_by == "Category":
        filtered = sorted(filtered, key=lambda s: (s.get("category") or "ZZZ"))

    # Reset pagination when filters or sort change
    filter_key = f"{cat_filter}|{sev_filter}|{sort_by}|{search}"
    if filter_key != st.session_state.last_filter_key:
        st.session_state.patient_page = 0
        st.session_state.last_filter_key = filter_key

    # Pagination math
    ITEMS_PER_PAGE = 9  # 3 rows of 3 cards
    total_pages = max(1, (len(filtered) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    st.session_state.patient_page = min(st.session_state.patient_page, total_pages - 1)

    page_start = st.session_state.patient_page * ITEMS_PER_PAGE
    page_end = page_start + ITEMS_PER_PAGE
    paginated = filtered[page_start:page_end] if filtered else []

    if filtered:
        st.caption(f"Showing {page_start + 1}–{min(page_end, len(filtered))} of {len(filtered)} patients")
    else:
        st.caption(f"No patients match your filters")

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

    # ── Card grid (3 columns × 3 rows = 9 per page) ──────────────────────
    for row_start in range(0, len(paginated), 3):
        row_items = paginated[row_start:row_start + 3]
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

    # ── Pagination controls ──────────────────────────────────────────────
    if total_pages > 1:
        st.divider()
        col_prev, col_info, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.button("← Previous", disabled=st.session_state.patient_page == 0, use_container_width=True):
                st.session_state.patient_page -= 1
                st.rerun()
        with col_info:
            st.markdown(
                f"<p style='text-align:center; padding-top:0.5em'>Page {st.session_state.patient_page + 1} of {total_pages}</p>",
                unsafe_allow_html=True,
            )
        with col_next:
            if st.button("Next →", disabled=st.session_state.patient_page >= total_pages - 1, use_container_width=True):
                st.session_state.patient_page += 1
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

        # Assessment Coverage with depth indicators
        st.subheader("Assessment Coverage")
        all_domains = ["HPI", "ROS", "PMH", "Medications", "Allergies", "Social_History", "Family_History"]

        # Pull live tracker state for depth info
        sid = st.session_state.session_id
        session = session_manager.get_session(sid)
        tracker_result = session["tracker"].get_result() if session else None

        DEPTH_ICONS = {"Missed": "○", "Surface": "◐", "Explored": "◕", "Deep": "●"}

        for domain in all_domains:
            label = domain.replace("_", " ")
            if tracker_result and domain in tracker_result.domains:
                cov = tracker_result.domains[domain]
                icon = DEPTH_ICONS.get(cov.depth, "○")
                pct = cov.depth_score / 100.0
                st.progress(pct, text=f"{icon} {label} ({cov.question_count} q)")
            else:
                st.progress(0.0, text=f"○ {label}")

        # Depth-weighted coverage score from tracker
        score = tracker_result.coverage_score if tracker_result else 0.0
        st.metric("Coverage Score", f"{score:.0f}%")
        st.caption("○ Missed · ◐ Surface · ◕ Explored · ● Deep")

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
