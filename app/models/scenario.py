from pydantic import BaseModel, Field


class SymptomDetail(BaseModel):
    """Detailed description of a present symptom."""
    description: str = Field(..., description="How the patient experiences/describes this symptom")
    onset: str | None = Field(None, description="When the symptom started, e.g. '2 hours ago'")
    character: str | None = Field(None, description="Nature of the symptom, e.g. 'sharp', 'pressure-like'")
    severity: str | None = Field(None, description="Severity rating, e.g. '7/10'")
    location: str | None = Field(None, description="Where the symptom is felt")
    radiation: str | None = Field(None, description="Where the symptom radiates to, if applicable")
    aggravating_factors: list[str] = Field(default_factory=list)
    alleviating_factors: list[str] = Field(default_factory=list)
    associated_symptoms: list[str] = Field(default_factory=list)


class VitalSigns(BaseModel):
    """Patient vital signs."""
    heart_rate: int | None = Field(None, description="Beats per minute")
    blood_pressure_systolic: int | None = None
    blood_pressure_diastolic: int | None = None
    respiratory_rate: int | None = Field(None, description="Breaths per minute")
    spo2: float | None = Field(None, description="Oxygen saturation percentage")
    temperature: float | None = Field(None, description="Temperature in Fahrenheit")
    pain_scale: int | None = Field(None, ge=0, le=10, description="Pain scale 0-10")


class SocialHistory(BaseModel):
    """Patient social history."""
    smoking: str | None = Field(None, description="Smoking status/history")
    alcohol: str | None = Field(None, description="Alcohol use")
    drugs: str | None = Field(None, description="Recreational drug use")
    occupation: str | None = None
    living_situation: str | None = None
    exercise: str | None = None
    diet: str | None = None


class FamilyHistory(BaseModel):
    """Family medical history."""
    conditions: dict[str, str] = Field(
        default_factory=dict,
        description="Family member → condition mapping, e.g. {'father': 'MI at 55', 'mother': 'DM2'}"
    )


class AssessmentRubric(BaseModel):
    """Expected assessment approach for scoring students."""
    expected_domains: list[str] = Field(
        default_factory=list,
        description="Which assessment domains are most critical for this case"
    )
    critical_findings: list[str] = Field(
        default_factory=list,
        description="Key findings the student should discover"
    )
    diagnosis: str = Field(..., description="The actual diagnosis for this case")
    differential_diagnoses: list[str] = Field(
        default_factory=list,
        description="Reasonable differential diagnoses"
    )
    recommended_interventions: list[str] = Field(
        default_factory=list,
        description="What a nurse should do/recommend for this patient"
    )


class PatientScenario(BaseModel):
    """
    Full patient scenario definition.

    This is the core data contract — every patient case JSON must conform to this schema.
    The LLM service uses this to construct the patient persona, and the assessment tracker
    uses the rubric to score student performance.
    """
    # Identity
    patient_id: str = Field(..., description="Unique case identifier, e.g. 'case_001'")
    name: str = Field(..., description="Patient's name")
    age: int = Field(..., ge=0, le=120)
    sex: str = Field(..., description="'Male', 'Female', or 'Other'")
    ethnicity: str | None = None
    weight_lbs: float | None = None
    height_inches: float | None = None

    # Presentation
    chief_complaint: str = Field(..., description="Why the patient is here, in their own words")
    onset_description: str | None = Field(None, description="When and how symptoms began")
    severity: str | None = Field(None, description="Overall acuity: 'low', 'medium', 'high', 'critical'")
    setting: str = Field("Emergency Department", description="Where the encounter takes place")

    # Symptoms
    symptoms_present: dict[str, SymptomDetail] = Field(
        default_factory=dict,
        description="Symptoms the patient HAS — key is symptom name, value is detail"
    )
    symptoms_absent: list[str] = Field(
        default_factory=list,
        description="Symptoms the patient does NOT have (deny if asked)"
    )

    # Vitals & Labs
    vitals: VitalSigns = Field(default_factory=VitalSigns)
    labs: dict[str, str | float] = Field(
        default_factory=dict,
        description="Lab results, e.g. {'troponin': 0.8, 'WBC': '12.5 K/uL'}"
    )

    # History
    past_medical_history: list[str] = Field(default_factory=list, description="PMH conditions")
    surgical_history: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list, description="Current medications")
    allergies: list[str] = Field(default_factory=list, description="Known allergies")
    social_history: SocialHistory = Field(default_factory=SocialHistory)
    family_history: FamilyHistory = Field(default_factory=FamilyHistory)

    # Persona (for LLM simulation)
    personality: str = Field(
        "cooperative and straightforward",
        description="How the patient behaves, e.g. 'anxious and verbose', 'stoic and reserved'"
    )
    communication_style: str = Field(
        "direct",
        description="How they communicate, e.g. 'tends to minimize symptoms', 'dramatic, uses metaphors'"
    )
    pain_description_style: str | None = Field(
        None,
        description="How they describe pain, e.g. 'uses numbers precisely', 'vague and evasive'"
    )

    # Assessment rubric
    rubric: AssessmentRubric


class ScenarioSummary(BaseModel):
    """Lightweight summary for listing scenarios in the UI."""
    patient_id: str
    name: str
    age: int
    sex: str
    chief_complaint: str
    severity: str | None = None
