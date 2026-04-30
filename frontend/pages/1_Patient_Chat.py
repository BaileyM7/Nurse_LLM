import asyncio
import sys
import time
from pathlib import Path

# Ensure repo root is on sys.path so "from app..." imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from frontend.theme import inject_theme

st.set_page_config(page_title="Patient Chat", page_icon="🏥", layout="wide")
inject_theme()


def run_async(coro):
    """Run an async coroutine safely, even if an event loop is already running."""
    try:
        asyncio.get_running_loop()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(lambda: asyncio.run(coro))
            return future.result(timeout=60)
    except RuntimeError:
        return asyncio.run(coro)


from app.config import settings  # noqa: E402
from app.models.session import ChatMessage, MessageRole  # noqa: E402
from app.services.domain_classifier import domain_classifier  # noqa: E402
from app.services.feedback_service import feedback_service  # noqa: E402
from app.services.llm_service import llm_service  # noqa: E402
from app.services.scenario_service import scenario_service  # noqa: E402
from app.services.session_manager import session_manager  # noqa: E402

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
if "session_duration" not in st.session_state:
    st.session_state.session_duration = 0


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
            st.error(
                f"Maximum turns ({settings.max_turns}) reached. Please end the session."
            )
            return

        classification = run_async(domain_classifier.classify(message))
        primary_domain = (
            classification.domains[0] if classification.domains else "conversational"
        )

        patient_response = run_async(llm_service.get_patient_response(sid, message))
        patient_response.domain_explored = primary_domain
        patient_response.domain_confidence = classification.confidence

        session["messages"].append(
            ChatMessage(
                role=MessageRole.STUDENT,
                content=message,
                domain_explored=primary_domain,
            )
        )
        session["messages"].append(
            ChatMessage(
                role=MessageRole.PATIENT,
                content=patient_response.dialogue,
            )
        )
        session["turn_count"] += 1

        session_manager.save_message(sid, "student", message, domain=primary_domain)
        session_manager.save_message(sid, "patient", patient_response.dialogue)

        session["tracker"].update(
            domains=classification.domains,
            confidence=classification.confidence,
            student_message=message,
        )

        st.session_state.messages.append({"role": "student", "content": message})
        st.session_state.messages.append(
            {
                "role": "patient",
                "content": patient_response.dialogue,
            }
        )
        st.session_state.turn_count = session["turn_count"]
        st.session_state.domains_covered = session["tracker"].get_covered_domains()

        # De-dup: prefer Title Case keys (rule-based) over snake_case (LLM schema).
        if patient_response.vitals_revealed:
            for k, v in patient_response.vitals_revealed.items():
                title_key = k.replace("_", " ").title()
                # Skip if we already have the human-formatted version
                if (
                    title_key in st.session_state.vitals_revealed
                    or title_key in patient_response.vitals_revealed
                ) and k != title_key:
                    continue
                st.session_state.vitals_revealed[title_key if k != title_key else k] = v

        if patient_response.labs_revealed:
            for k, v in patient_response.labs_revealed.items():
                title_key = k.replace("_", " ").title()
                if (
                    title_key in st.session_state.labs_revealed
                    or title_key in patient_response.labs_revealed
                ) and k != title_key:
                    continue
                st.session_state.labs_revealed[title_key if k != title_key else k] = v

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
        llm_service.end_session(sid)

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

        session_manager.end_session(sid, score=feedback.overall_score)
        session_manager.save_feedback(sid, feedback)

        if st.session_state.start_time:
            st.session_state.session_duration = int(
                time.time() - st.session_state.start_time
            )

        st.session_state.session_active = False
    except Exception as e:
        st.error(f"Failed to end session: {e}")


SEVERITY_BADGES = {
    "critical": "🔴 CRITICAL",
    "high": "🟠 HIGH",
    "medium": "🟡 MEDIUM",
    "low": "🟢 LOW",
}


def prettify_label(key: str) -> str:
    return key.replace("_", " ").title()


# MODE 1: Patient Selection
if not st.session_state.session_active and not st.session_state.messages:
    st.title("Select a Patient")

    scenarios = fetch_scenarios()
    if not scenarios:
        st.warning("No scenarios available.")
        st.stop()

    categories = sorted(set(s.get("category", "Other") or "Other" for s in scenarios))

    filter_cols = st.columns([2, 2, 2, 3])
    with filter_cols[0]:
        cat_filter = st.selectbox("Category", ["All"] + categories, key="cat_filter")
    with filter_cols[1]:
        sev_filter = st.selectbox(
            "Severity", ["All", "Critical", "High", "Medium", "Low"], key="sev_filter"
        )
    with filter_cols[2]:
        sort_by = st.selectbox(
            "Sort by", ["Default", "Name", "Severity", "Category"], key="sort_filter"
        )
    with filter_cols[3]:
        search = st.text_input(
            "Search", placeholder="Name or complaint...", key="search"
        )

    filtered = scenarios
    if cat_filter != "All":
        filtered = [s for s in filtered if s.get("category") == cat_filter]
    if sev_filter != "All":
        filtered = [
            s
            for s in filtered
            if (s.get("severity") or "").lower() == sev_filter.lower()
        ]
    if search:
        q = search.lower()
        filtered = [
            s
            for s in filtered
            if q in s["name"].lower() or q in s["chief_complaint"].lower()
        ]

    SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    if sort_by == "Name":
        filtered = sorted(filtered, key=lambda s: s["name"].lower())
    elif sort_by == "Severity":
        filtered = sorted(
            filtered,
            key=lambda s: SEVERITY_ORDER.get((s.get("severity") or "").lower(), 99),
        )
    elif sort_by == "Category":
        filtered = sorted(filtered, key=lambda s: (s.get("category") or "ZZZ"))

    filter_key = f"{cat_filter}|{sev_filter}|{sort_by}|{search}"
    if filter_key != st.session_state.last_filter_key:
        st.session_state.patient_page = 0
        st.session_state.last_filter_key = filter_key

    ITEMS_PER_PAGE = 9
    total_pages = max(1, (len(filtered) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    st.session_state.patient_page = min(st.session_state.patient_page, total_pages - 1)

    page_start = st.session_state.patient_page * ITEMS_PER_PAGE
    page_end = page_start + ITEMS_PER_PAGE
    paginated = filtered[page_start:page_end] if filtered else []

    if filtered:
        st.caption(
            f"Showing {page_start + 1}–{min(page_end, len(filtered))} of {len(filtered)} patients"
        )
    else:
        st.caption("No patients match your filters")

    st.markdown(
        """
    <style>
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
    """,
        unsafe_allow_html=True,
    )

    COMPLAINT_MAX = 80

    for row_start in range(0, len(paginated), 3):
        row_items = paginated[row_start : row_start + 3]
        cols = st.columns(3)

        for col, s in zip(cols, row_items, strict=False):
            sev = (s.get("severity") or "").lower()
            badge = SEVERITY_BADGES.get(sev, "⚪ UNKNOWN")
            cat_label = s.get("category") or ""
            complaint = s["chief_complaint"]
            if len(complaint) > COMPLAINT_MAX:
                complaint = complaint[:COMPLAINT_MAX].rsplit(" ", 1)[0] + "..."

            with col, st.container(border=True):
                st.markdown(f"**{s['name']}**")
                st.caption(f"{s['age']}yo {s['sex']} · {cat_label} · {badge}")
                st.markdown(f'*"{complaint}"*')
                if st.button(
                    "Start Assessment",
                    key=f"sel_{s['patient_id']}",
                    use_container_width=True,
                ):
                    start_session(s["patient_id"])
                    st.rerun()

    if total_pages > 1:
        st.divider()
        col_prev, col_info, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.button(
                "← Previous",
                disabled=st.session_state.patient_page == 0,
                use_container_width=True,
            ):
                st.session_state.patient_page -= 1
                st.rerun()
        with col_info:
            st.markdown(
                f"<p style='text-align:center; padding-top:0.5em'>Page {st.session_state.patient_page + 1} of {total_pages}</p>",
                unsafe_allow_html=True,
            )
        with col_next:
            if st.button(
                "Next →",
                disabled=st.session_state.patient_page >= total_pages - 1,
                use_container_width=True,
            ):
                st.session_state.patient_page += 1
                st.rerun()


# MODE 2: Session complete
elif not st.session_state.session_active and st.session_state.messages:
    st.title("Session Complete")
    st.success("Go to **Session Review** in the sidebar to see your feedback.")

    if st.button("Start New Session"):
        st.session_state.messages = []
        st.session_state.session_id = None
        st.rerun()


# MODE 3: Active chat session
else:
    with st.sidebar:
        # Light text scoped only to progress-bar labels; theme default everywhere else.
        st.markdown(
            """
        <style>
            [data-testid="stSidebar"] [data-testid="stProgress"] p {
                color: #F2EDE4 !important;
            }
        </style>
        """,
            unsafe_allow_html=True,
        )

        st.metric("Turns", st.session_state.turn_count)

        # Live coverage with depth indicators — pulled from the tracker each rerun
        st.subheader("Assessment Coverage")
        _sid = st.session_state.session_id
        _session = session_manager.get_session(_sid) if _sid else None
        _tracker_result = _session["tracker"].get_result() if _session else None

        DEPTH_ICONS = {"Missed": "○", "Surface": "◐", "Explored": "◕", "Deep": "●"}
        DOMAIN_LABELS = {
            "HPI": "HPI",
            "ROS": "ROS",
            "PMH": "PMH",
            "Medications": "Medications",
            "Allergies": "Allergies",
            "Social_History": "Social History",
            "Family_History": "Family History",
        }
        _all_domains = [
            "HPI",
            "ROS",
            "PMH",
            "Medications",
            "Allergies",
            "Social_History",
            "Family_History",
        ]

        for _d in _all_domains:
            _label = DOMAIN_LABELS[_d]
            if _tracker_result and _d in _tracker_result.domains:
                _cov = _tracker_result.domains[_d]
                _icon = DEPTH_ICONS.get(_cov.depth, "○")
                _pct = _cov.depth_score / 100.0
                st.progress(_pct, text=f"{_icon} {_label} ({_cov.question_count}q)")
            else:
                st.progress(0.0, text=f"○ {_label}")

        _score = _tracker_result.coverage_score if _tracker_result else 0.0
        st.metric("Depth Score", f"{_score:.0f}%")
        st.caption("○ Missed · ◐ Surface · ◕ Explored · ● Deep")

        if st.session_state.vitals_revealed:
            st.subheader("Vitals")
            for k, v in st.session_state.vitals_revealed.items():
                st.text(f"{k}: {v}")

        if st.session_state.labs_revealed:
            st.subheader("Lab Results")
            for k, v in st.session_state.labs_revealed.items():
                st.text(f"{k}: {v}")

        st.divider()
        if st.button("End Session", type="secondary", use_container_width=True):
            end_session()
            st.rerun()

    st.markdown(
        f"""
        <div class="case-header-wrap">
            <div class="case-eyebrow">Active case</div>
            <div class="case-title">{st.session_state.patient_name}</div>
            <div class="case-complaint">{st.session_state.chief_complaint}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    for msg in st.session_state.messages:
        role = msg["role"]
        if role == "student":
            with st.chat_message("user"):
                st.write(msg["content"])
        else:
            with st.chat_message("assistant", avatar="🏥"):
                st.write(msg["content"])

    if prompt := st.chat_input("Ask your patient a question..."):
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant", avatar="🏥"), st.spinner(
            "Patient is responding..."
        ):
            send_message(prompt)
            if st.session_state.messages:
                st.write(st.session_state.messages[-1]["content"])

        st.rerun()
