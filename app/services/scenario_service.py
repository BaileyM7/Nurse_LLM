import json
from pathlib import Path

from pydantic import ValidationError

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
            with open(file_path) as f:
                data = json.load(f)
            try:
                scenario = PatientScenario(**data)
            except ValidationError as e:
                raise ValueError(f"Malformed scenario {file_path.name}: {e}") from e
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
                category=s.category,
                severity=s.severity,
            )
            for s in self._scenarios.values()
        ]

    def get_scenario(self, patient_id: str) -> PatientScenario | None:
        return self._scenarios.get(patient_id)

    def get_scenario_ids(self) -> list[str]:
        return list(self._scenarios.keys())


def load_scenario(path: Path) -> PatientScenario:
    """Load and validate a single scenario file, raising ValueError with the file name on error."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    try:
        return PatientScenario(**data)
    except ValidationError as e:
        raise ValueError(f"Malformed scenario {path.name}: {e}") from e


# Singleton instance
scenario_service = ScenarioService()
