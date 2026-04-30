"""Rule-based baseline (floor): keyword match → scripted reply from scenario JSON, no LLM."""

from __future__ import annotations

from app.models.scenario import PatientScenario


class RuleBasedPatient:
    def __init__(self, scenario: PatientScenario):
        self.scenario = scenario

    def respond(self, student_message: str) -> str:
        msg = student_message.lower()

        # Chief complaint / opening
        if any(
            w in msg
            for w in [
                "what brings you",
                "why are you here",
                "chief complaint",
                "what's going on",
                "how can i help",
            ]
        ):
            return self.scenario.chief_complaint

        # HPI: symptom-specific
        for name, detail in self.scenario.symptoms_present.items():
            if name.replace("_", " ") in msg:
                return detail.description or f"Yes, I have {name.replace('_', ' ')}."

        if (
            any(w in msg for w in ["when did", "how long", "onset"])
            and self.scenario.onset_description
        ):
            return self.scenario.onset_description

        # Symptoms absent
        for absent in self.scenario.symptoms_absent:
            if absent.lower() in msg:
                return f"No, I don't have {absent}."

        # PMH
        if any(
            w in msg
            for w in [
                "medical history",
                "past medical",
                "conditions",
                "health problems",
                "pmh",
            ]
        ):
            return (
                "My medical history includes: "
                + ", ".join(self.scenario.past_medical_history)
                if self.scenario.past_medical_history
                else "Nothing significant."
            )

        # Medications
        if any(
            w in msg for w in ["medication", "medicine", "pills", "what do you take"]
        ):
            return (
                "I take: " + ", ".join(self.scenario.medications)
                if self.scenario.medications
                else "I don't take any medications."
            )

        # Allergies
        if "allerg" in msg:
            return (
                "I'm allergic to: " + ", ".join(self.scenario.allergies)
                if self.scenario.allergies
                else "No known allergies."
            )

        # Social
        if "smok" in msg:
            return self.scenario.social_history.smoking or "I don't smoke."
        if any(w in msg for w in ["alcohol", "drink"]):
            return self.scenario.social_history.alcohol or "I don't drink."
        if any(w in msg for w in ["drug", "recreational"]):
            return self.scenario.social_history.drugs or "No."
        if any(w in msg for w in ["work", "job", "occupation"]):
            return self.scenario.social_history.occupation or "I'd rather not say."

        # Family
        if "family" in msg:
            if self.scenario.family_history.conditions:
                parts = [
                    f"{m}: {c}"
                    for m, c in self.scenario.family_history.conditions.items()
                ]
                return "In my family, " + "; ".join(parts) + "."
            return "No significant family history."

        # Vitals / labs — delegate to keywords
        v = self.scenario.vitals
        if (
            "blood pressure" in msg or "bp" in msg.split()
        ) and v.blood_pressure_systolic is not None:
            return f"Blood pressure is {v.blood_pressure_systolic}/{v.blood_pressure_diastolic}."
        if (
            any(w in msg for w in ["heart rate", "pulse", "hr"])
            and v.heart_rate is not None
        ):
            return f"Heart rate is {v.heart_rate}."
        if (
            any(w in msg for w in ["temperature", "temp", "fever"])
            and v.temperature is not None
        ):
            return f"Temperature is {v.temperature}°F."
        if any(w in msg for w in ["spo2", "oxygen", "pulse ox"]) and v.spo2 is not None:
            return f"SpO2 is {v.spo2}%."

        # Fallback
        return "I don't understand the question. Could you rephrase?"
