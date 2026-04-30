"""Smoke test: runs scripts/smoke_run.py as a subprocess and verifies output."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "smoke_run.py"


def test_smoke_run_exits_zero():
    """smoke_run.py should exit 0 (no API calls — uses rule-based patient)."""
    result = subprocess.run(
        [sys.executable, str(SMOKE_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert (
        result.returncode == 0
    ), f"smoke_run.py exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"


def test_smoke_run_outputs_scenario_name():
    """smoke_run.py should print the patient's name (Maria Santos)."""
    result = subprocess.run(
        [sys.executable, str(SMOKE_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert (
        "Maria Santos" in result.stdout
    ), f"Expected 'Maria Santos' in stdout, got:\n{result.stdout}"


def test_smoke_run_outputs_patient_reply():
    """smoke_run.py should print a non-empty patient reply line."""
    result = subprocess.run(
        [sys.executable, str(SMOKE_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    # The script prints "Patient reply: <something>"
    lines = [
        line for line in result.stdout.splitlines() if line.startswith("Patient reply:")
    ]
    assert lines, f"No 'Patient reply:' line found in output:\n{result.stdout}"
    # The reply should have actual content after the colon
    reply_text = lines[0].split("Patient reply:", 1)[1].strip()
    assert len(reply_text) > 5, f"Patient reply is too short: {reply_text!r}"
