import time

import httpx
import streamlit as st

API_URL = "http://localhost:8000"

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
        resp = httpx.get(f"{API_URL}/api/scenarios/")
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Failed to load scenarios: {e}")
        return []


def start_session(scenario_id: str):
    try:
        resp = httpx.post(
            f"{API_URL}/api/sessions/start",
            json={"scenario_id": scenario_id},
        )
        resp.raise_for_status()
        data = resp.json()
        st.session_state.session_id = data["session_id"]
        st.session_state.session_active = True
        st.session_state.patient_name = data["patient_name"]
        st.session_state.chief_complaint = data["chief_complaint"]
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
        resp = httpx.post(
            f"{API_URL}/api/chat/",
            json={
                "session_id": st.session_state.session_id,
                "message": message,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        # Update state
        st.session_state.messages.append({"role": "student", "content": message})
        st.session_state.messages.append({
            "role": "patient",
            "content": data["patient_response"]["dialogue"],
        })
        st.session_state.turn_count = data["turn_count"]
        st.session_state.domains_covered = data["domains_covered"]

        # Track revealed vitals/labs
        pr = data["patient_response"]
        if pr.get("vitals_revealed"):
            st.session_state.vitals_revealed.update(pr["vitals_revealed"])
        if pr.get("labs_revealed"):
            st.session_state.labs_revealed.update(pr["labs_revealed"])

    except Exception as e:
        st.error(f"Error communicating with patient: {e}")


def end_session():
    try:
        resp = httpx.post(
            f"{API_URL}/api/sessions/{st.session_state.session_id}/end",
            timeout=30.0,
        )
        resp.raise_for_status()
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
        st.warning("No scenarios available. Make sure the backend is running.")
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
