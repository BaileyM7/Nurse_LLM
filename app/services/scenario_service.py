import json
from pathlib import Path

from app.config import settings
from app.models.scenario import PatientScenario, ScenarioSummary


class ScenarioService:
    """Loads and serves patient scenarios from JSON files."""

    def __init__(self):
        self._scenarios: dict[str, PatientScenario] = {}
        self._load_scenarios()

    def _load_scenarios(self) -> None:
        scenarios_dir = Path(settings.scenarios_dir)
        if not scenarios_dir.exists():
            return

        for file_path in sorted(scenarios_dir.glob("*.json")):
            with open(file_path, "r") as f:
                data = json.load(f)
            scenario = PatientScenario(**data)
            self._scenarios[scenario.patient_id] = scenario

    def reload(self) -> None:
        """Reload scenarios from disk (useful during development)."""
        self._scenarios.clear()
        self._load_scenarios()

    def list_scenarios(self) -> list[ScenarioSummary]:
        return [
            ScenarioSummary(
                patient_id=s.patient_id,
                name=s.name,
                age=s.age,
                sex=s.sex,
                chief_complaint=s.chief_complaint,
                severity=s.severity,
            )
            for s in self._scenarios.values()
        ]

    def get_scenario(self, patient_id: str) -> PatientScenario | None:
        return self._scenarios.get(patient_id)

    def get_scenario_ids(self) -> list[str]:
        return list(self._scenarios.keys())


# Singleton instance
scenario_service = ScenarioService()
