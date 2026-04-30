"""Tests for PatientScenario Pydantic model loading and validation."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.scenario import AssessmentRubric, PatientScenario

CASE_001_PATH = Path(__file__).parent.parent / "data" / "scenarios" / "case_001.json"


def _load_raw() -> dict:
    with open(CASE_001_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_valid_scenario_loads(sample_scenario):
    """case_001.json should load without error and populate identity fields."""
    assert sample_scenario.name == "Maria Santos"
    assert sample_scenario.age == 67
    assert sample_scenario.sex == "Female"
    assert sample_scenario.patient_id == "case_001"


def test_chief_complaint_populated(sample_scenario):
    """Chief complaint should be a non-empty string describing the presentation."""
    assert isinstance(sample_scenario.chief_complaint, str)
    assert len(sample_scenario.chief_complaint) > 0


def test_symptoms_present_nested_model(sample_scenario):
    """symptoms_present should contain SymptomDetail objects with description."""
    assert "chest_pain" in sample_scenario.symptoms_present
    chest = sample_scenario.symptoms_present["chest_pain"]
    assert (
        "pressure" in chest.description.lower()
        or "tightness" in chest.description.lower()
    )
    assert chest.radiation is not None
    assert "arm" in chest.radiation.lower() or "jaw" in chest.radiation.lower()


def test_symptoms_absent_is_list(sample_scenario):
    """symptoms_absent should be a non-empty list of strings."""
    assert isinstance(sample_scenario.symptoms_absent, list)
    assert len(sample_scenario.symptoms_absent) > 0
    assert "fever" in sample_scenario.symptoms_absent


def test_rubric_populated(sample_scenario):
    """The rubric field should have a diagnosis and expected_domains."""
    rubric = sample_scenario.rubric
    assert isinstance(rubric, AssessmentRubric)
    assert "NSTEMI" in rubric.diagnosis
    assert len(rubric.expected_domains) == 7
    assert len(rubric.critical_findings) > 0


def test_vitals_heart_rate(sample_scenario):
    """Vitals should be parsed into a VitalSigns model with numeric fields."""
    assert sample_scenario.vitals.heart_rate == 102
    assert sample_scenario.vitals.spo2 == 94.0


def test_past_medical_history(sample_scenario):
    """PMH should list known conditions."""
    pmh = sample_scenario.past_medical_history
    assert any("Hypertension" in item for item in pmh)
    assert any("Diabetes" in item for item in pmh)


def test_empty_dict_raises_validation_error():
    """An empty dict should fail PatientScenario validation (missing required fields)."""
    with pytest.raises(ValidationError):
        PatientScenario(**{})


def test_missing_rubric_raises_validation_error():
    """A scenario without a rubric should fail validation."""
    raw = _load_raw()
    del raw["rubric"]
    with pytest.raises(ValidationError):
        PatientScenario(**raw)


def test_missing_name_raises_validation_error():
    """A scenario without a name should fail validation."""
    raw = _load_raw()
    del raw["name"]
    with pytest.raises(ValidationError):
        PatientScenario(**raw)


def test_invalid_pain_scale_raises_validation_error():
    """pain_scale out of 0-10 range should fail validation."""
    raw = _load_raw()
    raw["vitals"]["pain_scale"] = 15  # exceeds le=10 constraint
    with pytest.raises(ValidationError):
        PatientScenario(**raw)
