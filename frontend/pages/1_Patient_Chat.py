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


# ── Sidebar: Scenario Selection + Session Info ───────────────────────────────
with st.sidebar:
    st.header("Patient Selection")

    if not st.session_state.session_active:
        scenarios = fetch_scenarios()
        if scenarios:
            # Build display labels
            options = {
                s["patient_id"]: f"{s['name']} ({s['age']}yo {s['sex']}) - {s['chief_complaint'][:40]}..."
                for s in scenarios
            }
            selected = st.selectbox(
                "Choose a patient:",
                options.keys(),
                format_func=lambda x: options[x],
            )

            if st.button("Start Session", type="primary", use_container_width=True):
                start_session(selected)
                st.rerun()
        else:
            st.warning("No scenarios available. Check that the API is running and scenarios are loaded.")
    else:
        # Active session info
        st.subheader(f"Patient: {st.session_state.patient_name}")
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


# ── Main Chat Area ───────────────────────────────────────────────────────────
st.title("Patient Assessment Chat")

if not st.session_state.session_active and not st.session_state.messages:
    st.info("Select a patient from the sidebar and click 'Start Session' to begin.")
elif not st.session_state.session_active and st.session_state.messages:
    st.success(
        "Session complete! Go to **Session Review** in the sidebar to see your feedback."
    )

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
if st.session_state.session_active:
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
