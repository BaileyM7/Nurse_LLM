"""Two-stage domain classifier: keyword rules first, LLM fallback for ambiguous cases."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.llm_provider import create_chat_model


@dataclass
class ClassificationResult:
    """Result of classifying a single student question."""

    domains: list[str] = field(default_factory=list)
    confidence: float = 0.0
    source: str = "none"  # "keyword", "llm", or "none"


# Stage 1 — intentionally specific; we'd rather fall through to LLM than mis-tag.
KEYWORD_RULES: dict[str, list[str]] = {
    "Medications": [
        r"\b(medication|medicine|pill|prescription|drug|rx)\b",
        r"\b(take|taking|takes)\s+(any|anything|meds?)\b",
        r"\bover[-\s]?the[-\s]?counter\b|\botc\b",
        r"\b(supplement|vitamin|herbal)\b",
    ],
    "Allergies": [
        r"\ballerg(y|ies|ic)\b",
        r"\breaction to\b.*(drug|medication|food)",
        r"\bnkda\b",
    ],
    "PMH": [
        r"\b(past|previous|prior)\s+(medical|surgical|health)\s+history\b",
        r"\bmedical history\b",
        r"\b(chronic|pre[-\s]?existing)\s+condition(s)?\b",
        r"\b(been diagnosed|diagnosed with|ever had)\b",
        r"\b(hospitalized|hospitalization|surgery|surgeries|operation)\b",
    ],
    "Social_History": [
        r"\b(smoke|smoking|tobacco|cigarette|vape|vaping)\b",
        r"\b(drink|drinking|alcohol|beer|wine|liquor)\b",
        r"\b(drug use|recreational|illicit|marijuana|cocaine|heroin)\b",
        r"\b(occupation|job|work|profession|employed)\b",
        r"\b(live with|living situation|married|relationship)\b",
        r"\b(exercise|diet|sleep habits)\b",
    ],
    "Family_History": [
        r"\bfamily history\b",
        r"\b(mother|father|mom|dad|sister|brother|parent|sibling|grandparent)\b.*\b(have|has|had|run|runs)\b",
        r"\banyone in (your|the) family\b",
        r"\bruns in (your|the|their) family\b",
    ],
    "HPI": [
        r"\b(when did.*(start|begin))\b",
        r"\bhow long\b.*\b(have|has)\b",
        r"\b(describe|tell me about).*\b(pain|symptom|feeling)\b",
        r"\b(what makes|anything makes).*\b(better|worse)\b",
        r"\bon a scale\b.*(pain|severity)",
        r"\b(radiating|radiate|spread)\b",
    ],
    "ROS": [
        r"\b(any other symptoms|other symptoms|anything else)\b",
        r"\b(fever|chills|nausea|vomiting|headache|dizziness|fatigue|weakness)\b.*\?",
        r"\b(shortness of breath|chest pain|abdominal pain|back pain)\b.*\?",
        r"\b(bowel|bladder|urinate|urination|stool)\b",
    ],
}

# Compile once
_COMPILED_RULES: dict[str, list[re.Pattern]] = {
    domain: [re.compile(pat, re.IGNORECASE) for pat in pats]
    for domain, pats in KEYWORD_RULES.items()
}


def classify_by_keywords(message: str) -> list[str]:
    """Return list of domains matched by keyword rules (may be empty or multi-label)."""
    matches = []
    for domain, patterns in _COMPILED_RULES.items():
        if any(pat.search(message) for pat in patterns):
            matches.append(domain)
    return matches


CLASSIFIER_PROMPT = """You classify nursing-student questions into clinical assessment domains.

Domains (choose 1-3 that apply):
- HPI: History of Present Illness — current symptoms, onset, severity, character, radiation, aggravating/alleviating factors
- ROS: Review of Systems — systematic check for symptoms in other body systems not part of chief complaint
- PMH: Past Medical History — prior diagnoses, surgeries, hospitalizations, chronic conditions
- Medications: current prescriptions, OTC drugs, supplements
- Allergies: drug, food, or environmental allergies
- Social_History: smoking, alcohol, drugs, occupation, living situation, exercise
- Family_History: medical conditions in relatives
- conversational: greetings, rapport-building, not an assessment question

Student question: "{message}"

Respond with JSON only:
{{
    "domains": ["Domain1", "Domain2"],
    "confidence": 0.0-1.0
}}

Rules:
- If it's not an assessment question, return {{"domains": ["conversational"], "confidence": 1.0}}
- Multi-label only when the question genuinely spans domains (e.g., "Do you or anyone in your family have heart disease?" = PMH + Family_History)
- Keep confidence honest — low confidence for vague questions like "tell me more"
"""


class DomainClassifier:
    """Two-stage classifier: keywords first, LLM fallback."""

    def __init__(self):
        # Provider-agnostic — fast tier, deterministic (temp=0)
        self._llm = create_chat_model(temperature=0.0)

    async def classify(self, message: str) -> ClassificationResult:
        """Classify a student question into one or more domains."""
        # Stage 1: keyword rules
        kw_matches = classify_by_keywords(message)
        if kw_matches:
            return ClassificationResult(
                domains=kw_matches,
                confidence=0.95,
                source="keyword",
            )

        # Stage 2: LLM fallback
        try:
            response = await self._llm.ainvoke(
                [
                    SystemMessage(
                        content="You are a precise clinical-domain classifier. Always respond with valid JSON."
                    ),
                    HumanMessage(content=CLASSIFIER_PROMPT.format(message=message)),
                ]
            )
            data = json.loads(response.content)
            return ClassificationResult(
                domains=data.get("domains", []),
                confidence=float(data.get("confidence", 0.0)),
                source="llm",
            )
        except (json.JSONDecodeError, Exception):
            return ClassificationResult(domains=[], confidence=0.0, source="none")


# Singleton
domain_classifier = DomainClassifier()
