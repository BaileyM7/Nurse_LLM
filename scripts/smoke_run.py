"""Smoke test: load a scenario, run one student turn through the rule-based
baseline (no API calls), print patient response. Used in README test
instructions and CI.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.scenario import PatientScenario
from evaluation.baselines.rule_based_patient import RuleBasedPatient


def main() -> int:
    scenario_path = Path("data/scenarios/case_001.json")
    if not scenario_path.exists():
        print(f"FAIL: {scenario_path} not found", file=sys.stderr)
        return 1
    with open(scenario_path) as f:
        scenario = PatientScenario(**json.load(f))
    patient = RuleBasedPatient(scenario)
    reply = patient.respond("Can you describe your chest pain?")
    print(f"Scenario: {scenario.name}")
    print(f"Patient reply: {reply}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
