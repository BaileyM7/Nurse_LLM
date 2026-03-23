from fastapi import APIRouter, HTTPException

from app.models.scenario import PatientScenario, ScenarioSummary
from app.services.scenario_service import scenario_service

router = APIRouter()


@router.get("/", response_model=list[ScenarioSummary])
async def list_scenarios():
    """List all available patient scenarios."""
    return scenario_service.list_scenarios()


@router.get("/{patient_id}", response_model=PatientScenario)
async def get_scenario(patient_id: str):
    """Get full details for a specific patient scenario."""
    scenario = scenario_service.get_scenario(patient_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{patient_id}' not found")
    return scenario


@router.post("/reload")
async def reload_scenarios():
    """Reload scenarios from disk (development helper)."""
    scenario_service.reload()
    return {"status": "reloaded", "count": len(scenario_service.get_scenario_ids())}
