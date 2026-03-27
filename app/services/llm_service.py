import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.config import settings
from app.models.scenario import PatientScenario
from app.models.session import PatientResponse


SYSTEM_PROMPT_TEMPLATE = """You are a simulated patient in a nursing assessment training scenario.
You must stay in character at ALL times.

## Your Identity
- Name: {name}
- Age: {age}
- Sex: {sex}
- Setting: {setting}

## Your Personality
- Personality: {personality}
- Communication style: {communication_style}
{pain_style_line}

## Your Chief Complaint
You came in because: {chief_complaint}
{onset_line}

## Your Symptoms (ONLY reveal these if asked)
Present symptoms:
{symptoms_present_text}

Symptoms you do NOT have (deny if asked):
{symptoms_absent_text}

## Your Medical History
- Past medical history: {pmh_text}
- Surgical history: {surgical_text}
- Medications: {meds_text}
- Allergies: {allergies_text}
- Social history: {social_hx_text}
- Family history: {family_hx_text}

## Your Vitals (only reveal if the student says they are checking/measuring them)
{vitals_text}

## Your Lab Results (only reveal if the student orders/asks about them)
{labs_text}

## CRITICAL RULES
1. NEVER break character. You are the patient, not an AI.
2. ONLY mention symptoms listed above. If asked about a symptom not listed, deny it.
3. NEVER give medical advice, diagnoses, or treatment suggestions.
4. Respond naturally as a patient would — use plain language, not medical terminology.
5. If the student hasn't asked about something, don't volunteer the information.
6. Keep responses concise — 1-3 sentences typically, unless the student asks for detail.
7. Show your personality in how you respond (anxious patients ramble, stoic patients give short answers, etc.)

## RESPONSE FORMAT
You must respond with valid JSON in this exact format:
{{
    "dialogue": "what you say as the patient",
    "domain_explored": "which assessment domain the student's question relates to (HPI, ROS, PMH, Medications, Allergies, Social_History, Family_History, or conversational)",
    "domain_confidence": 0.0 to 1.0,
    "vitals_revealed": null or {{"vital_name": value}} if you revealed vitals,
    "labs_revealed": null or {{"lab_name": value}} if you revealed labs
}}"""


def _build_system_prompt(scenario: PatientScenario) -> str:
    """Build the patient persona system prompt from a scenario."""

    # Format symptoms present
    symptoms_lines = []
    for symptom_name, detail in scenario.symptoms_present.items():
        parts = [f"- {symptom_name}: {detail.description}"]
        if detail.onset:
            parts.append(f"  Onset: {detail.onset}")
        if detail.severity:
            parts.append(f"  Severity: {detail.severity}")
        if detail.location:
            parts.append(f"  Location: {detail.location}")
        if detail.radiation:
            parts.append(f"  Radiates to: {detail.radiation}")
        if detail.character:
            parts.append(f"  Character: {detail.character}")
        if detail.aggravating_factors:
            parts.append(f"  Worse with: {', '.join(detail.aggravating_factors)}")
        if detail.alleviating_factors:
            parts.append(f"  Better with: {', '.join(detail.alleviating_factors)}")
        symptoms_lines.append("\n".join(parts))
    symptoms_present_text = "\n".join(symptoms_lines) if symptoms_lines else "None specified"

    # Format symptoms absent
    symptoms_absent_text = ", ".join(scenario.symptoms_absent) if scenario.symptoms_absent else "None specified"

    # Format vitals
    vitals = scenario.vitals
    vitals_parts = []
    if vitals.heart_rate is not None:
        vitals_parts.append(f"Heart Rate: {vitals.heart_rate} bpm")
    if vitals.blood_pressure_systolic is not None:
        vitals_parts.append(f"Blood Pressure: {vitals.blood_pressure_systolic}/{vitals.blood_pressure_diastolic} mmHg")
    if vitals.respiratory_rate is not None:
        vitals_parts.append(f"Respiratory Rate: {vitals.respiratory_rate} breaths/min")
    if vitals.spo2 is not None:
        vitals_parts.append(f"SpO2: {vitals.spo2}%")
    if vitals.temperature is not None:
        vitals_parts.append(f"Temperature: {vitals.temperature}°F")
    if vitals.pain_scale is not None:
        vitals_parts.append(f"Pain Scale: {vitals.pain_scale}/10")
    vitals_text = "\n".join(vitals_parts) if vitals_parts else "Not available"

    # Format labs
    labs_text = "\n".join(f"- {k}: {v}" for k, v in scenario.labs.items()) if scenario.labs else "No labs ordered"

    return SYSTEM_PROMPT_TEMPLATE.format(
        name=scenario.name,
        age=scenario.age,
        sex=scenario.sex,
        setting=scenario.setting,
        personality=scenario.personality,
        communication_style=scenario.communication_style,
        pain_style_line=f"- Pain description style: {scenario.pain_description_style}" if scenario.pain_description_style else "",
        chief_complaint=scenario.chief_complaint,
        onset_line=f"Onset: {scenario.onset_description}" if scenario.onset_description else "",
        symptoms_present_text=symptoms_present_text,
        symptoms_absent_text=symptoms_absent_text,
        pmh_text=", ".join(scenario.past_medical_history) if scenario.past_medical_history else "None",
        surgical_text=", ".join(scenario.surgical_history) if scenario.surgical_history else "None",
        meds_text=", ".join(scenario.medications) if scenario.medications else "None",
        allergies_text=", ".join(scenario.allergies) if scenario.allergies else "NKDA",
        social_hx_text=_format_social_hx(scenario.social_history),
        family_hx_text=_format_family_hx(scenario.family_history),
        vitals_text=vitals_text,
        labs_text=labs_text,
    )


def _format_social_hx(social) -> str:
    parts = []
    if social.smoking:
        parts.append(f"Smoking: {social.smoking}")
    if social.alcohol:
        parts.append(f"Alcohol: {social.alcohol}")
    if social.drugs:
        parts.append(f"Drugs: {social.drugs}")
    if social.occupation:
        parts.append(f"Occupation: {social.occupation}")
    if social.living_situation:
        parts.append(f"Living: {social.living_situation}")
    return "; ".join(parts) if parts else "Noncontributory"


def _format_family_hx(family) -> str:
    if family.conditions:
        return "; ".join(f"{member}: {condition}" for member, condition in family.conditions.items())
    return "Noncontributory"

def _detect_requested_vitals(student_message: str, scenario: PatientScenario) -> dict:
    msg = student_message.lower()
    revealed = {}

    vitals = scenario.vitals

    if any(term in msg for term in ["blood pressure", "bp", "b/p"]):
        if (
            vitals.blood_pressure_systolic is not None
            and vitals.blood_pressure_diastolic is not None
        ):
            revealed["Blood Pressure"] = (
                f"{vitals.blood_pressure_systolic}/{vitals.blood_pressure_diastolic} mmHg"
            )

    if any(term in msg for term in ["heart rate", "pulse rate", "hr"]):
        if vitals.heart_rate is not None:
            revealed["Heart Rate"] = f"{vitals.heart_rate} bpm"

    # Only use plain "pulse" if "pulse ox" was not what they meant
    if "pulse" in msg and "pulse ox" not in msg and "pulse oxim" not in msg:
        if "Heart Rate" not in revealed and vitals.heart_rate is not None:
            revealed["Heart Rate"] = f"{vitals.heart_rate} bpm"

    if any(term in msg for term in ["respiratory rate", "resp rate", "rr"]):
        if vitals.respiratory_rate is not None:
            revealed["Respiratory Rate"] = f"{vitals.respiratory_rate} breaths/min"

    if any(term in msg for term in ["spo2", "oxygen saturation", "pulse ox", "pulse oximetry", "o2 sat", "satting"]):
        if vitals.spo2 is not None:
            revealed["SpO2"] = f"{vitals.spo2}%"

    if any(term in msg for term in ["temperature", "temp", "fever"]):
        if vitals.temperature is not None:
            revealed["Temperature"] = f"{vitals.temperature}°F"

    if any(term in msg for term in ["pain", "pain score", "pain scale"]):
        if vitals.pain_scale is not None:
            revealed["Pain Scale"] = f"{vitals.pain_scale}/10"

    return revealed


def _detect_requested_labs(student_message: str, scenario: PatientScenario) -> dict:
    msg = student_message.lower()
    revealed = {}

    if not scenario.labs:
        return revealed

    # direct exact-ish matching against lab names in scenario
    for lab_name, lab_value in scenario.labs.items():
        lab_lower = lab_name.lower()
        if lab_lower in msg:
            revealed[lab_name] = lab_value
            continue

        # common aliases
        aliases = {
            "cbc": ["cbc", "complete blood count"],
            "cmp": ["cmp", "comprehensive metabolic panel"],
            "bmp": ["bmp", "basic metabolic panel"],
            "troponin": ["troponin"],
            "abg": ["abg", "arterial blood gas"],
            "lactate": ["lactate"],
            "wbc": ["wbc", "white blood cell"],
            "hemoglobin": ["hemoglobin", "hgb"],
            "platelets": ["platelets", "plt"],
            "glucose": ["glucose", "blood sugar"],
        }

        for key, terms in aliases.items():
            if key in lab_lower and any(term in msg for term in terms):
                revealed[lab_name] = lab_value
                break

    return revealed


class LLMService:
    """Manages LLM interactions for patient simulation."""

    def __init__(self):
        self._llm = ChatOpenAI(
            model=settings.model_name,
            api_key=settings.openai_api_key,
            temperature=0.7,
        )
        # Per-session conversation histories: session_id → list of messages
        self._histories: dict[str, list] = {}
        # Per-session system prompts
        self._system_prompts: dict[str, str] = {}
        self._scenarios: dict[str, PatientScenario] = {}

    def start_session(self, session_id: str, scenario: PatientScenario) -> None:
        """Initialize conversation state for a new session."""
        system_prompt = _build_system_prompt(scenario)
        self._system_prompts[session_id] = system_prompt
        self._histories[session_id] = []
        self._scenarios[session_id] = scenario

    def end_session(self, session_id: str) -> list:
        """Clean up session and return conversation history."""
        history = self._histories.pop(session_id, [])
        self._system_prompts.pop(session_id, None)
        self._scenarios.pop(session_id, None)
        return history

    # async def get_patient_response(self, session_id: str, student_message: str) -> PatientResponse:
    #     """Send student message to LLM and get structured patient response."""
    #     if session_id not in self._system_prompts:
    #         raise ValueError(f"Session '{session_id}' not found. Start a session first.")
    #
    #     # Build message list
    #     messages = [SystemMessage(content=self._system_prompts[session_id])]
    #     messages.extend(self._histories[session_id])
    #     messages.append(HumanMessage(content=student_message))
    #
    #     # Call LLM
    #     response = await self._llm.ainvoke(messages)
    #
    #     # Parse structured response
    #     try:
    #         response_data = json.loads(response.content)
    #         patient_response = PatientResponse(**response_data)
    #     except (json.JSONDecodeError, Exception):
    #         # Fallback: treat entire response as dialogue
    #         patient_response = PatientResponse(
    #             dialogue=response.content,
    #             domain_explored="conversational",
    #             domain_confidence=0.0,
    #         )
    #
    #     # Update conversation history
    #     self._histories[session_id].append(HumanMessage(content=student_message))
    #     self._histories[session_id].append(AIMessage(content=response.content))
    #
    #     return patient_response

    async def get_patient_response(self, session_id: str, student_message: str) -> PatientResponse:
        """Send student message to LLM and get structured patient response."""
        if session_id not in self._system_prompts:
            raise ValueError(f"Session '{session_id}' not found. Start a session first.")

        scenario = self._scenarios.get(session_id)
        if scenario is None:
            raise ValueError(f"Scenario for session '{session_id}' not found.")

        # Deterministically detect requested diagnostics
        vitals_revealed = _detect_requested_vitals(student_message, scenario)
        labs_revealed = _detect_requested_labs(student_message, scenario)

        # Build message list
        messages = [SystemMessage(content=self._system_prompts[session_id])]
        messages.extend(self._histories[session_id])
        messages.append(HumanMessage(content=student_message))

        # Call LLM
        response = await self._llm.ainvoke(messages)

        # Parse structured response
        try:
            response_data = json.loads(response.content)
            patient_response = PatientResponse(**response_data)
        except (json.JSONDecodeError, Exception):
            patient_response = PatientResponse(
                dialogue=response.content,
                domain_explored="conversational",
                domain_confidence=0.0,
                vitals_revealed=None,
                labs_revealed=None,
            )

        # Override/merge revealed diagnostics with deterministic backend logic
        merged_vitals = {}
        merged_labs = {}

        if patient_response.vitals_revealed:
            merged_vitals.update(patient_response.vitals_revealed)
        if patient_response.labs_revealed:
            merged_labs.update(patient_response.labs_revealed)

        merged_vitals.update(vitals_revealed)
        merged_labs.update(labs_revealed)

        patient_response.vitals_revealed = merged_vitals or None
        patient_response.labs_revealed = merged_labs or None

        # Update conversation history
        self._histories[session_id].append(HumanMessage(content=student_message))
        self._histories[session_id].append(AIMessage(content=response.content))

        return patient_response

    def get_history(self, session_id: str) -> list:
        """Get conversation history for a session."""
        return self._histories.get(session_id, [])


# Singleton instance
llm_service = LLMService()
