"""
Generate patient scenario cases using OpenAI API.

Usage:
    python scripts/generate_cases.py --count 10 --category cardiac
    python scripts/generate_cases.py --count 30  # all categories
    python scripts/generate_cases.py --list-categories

Requires OPENAI_API_KEY in .env or environment.
"""
import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from dotenv import load_dotenv

from app.models.scenario import PatientScenario

load_dotenv()

CATEGORIES = {
    "cardiac": {
        "conditions": [
            "Acute MI / STEMI",
            "Unstable Angina",
            "Heart Failure Exacerbation",
            "Atrial Fibrillation with Rapid Ventricular Response",
            "Hypertensive Emergency",
            "Pericarditis",
            "Deep Vein Thrombosis",
        ],
        "count_target": 8,
    },
    "respiratory": {
        "conditions": [
            "COPD Exacerbation",
            "Asthma Exacerbation",
            "Pulmonary Embolism",
            "Pneumothorax",
            "Pleural Effusion",
            "Acute Respiratory Distress Syndrome",
        ],
        "count_target": 7,
    },
    "gi": {
        "conditions": [
            "Acute Appendicitis",
            "GI Bleed (Upper)",
            "Acute Pancreatitis",
            "Small Bowel Obstruction",
            "Cholecystitis",
        ],
        "count_target": 5,
    },
    "neuro": {
        "conditions": [
            "Acute Ischemic Stroke",
            "Subarachnoid Hemorrhage",
            "Meningitis",
            "Seizure (New Onset)",
            "Migraine with Aura",
        ],
        "count_target": 5,
    },
    "infectious": {
        "conditions": [
            "Sepsis (Urinary Source)",
            "Cellulitis with Systemic Symptoms",
            "Diabetic Foot Infection",
            "Influenza with Complications",
        ],
        "count_target": 5,
    },
    "musculoskeletal": {
        "conditions": [
            "Hip Fracture (Elderly Fall)",
            "Acute Low Back Pain with Red Flags",
            "Compartment Syndrome",
        ],
        "count_target": 3,
    },
    "endocrine": {
        "conditions": [
            "Diabetic Ketoacidosis",
            "Hypoglycemia",
            "Thyroid Storm",
        ],
        "count_target": 3,
    },
    "psych": {
        "conditions": [
            "Acute Anxiety / Panic Attack",
            "Suicidal Ideation Assessment",
            "Acute Alcohol Withdrawal",
        ],
        "count_target": 3,
    },
    "renal": {
        "conditions": [
            "Acute Kidney Injury",
            "Kidney Stones (Nephrolithiasis)",
        ],
        "count_target": 2,
    },
}

GENERATION_PROMPT = """Generate a detailed patient scenario for a nursing assessment training simulation.

The patient has: {condition}
Category: {category}

Create a realistic, clinically accurate patient case. The scenario should be appropriate for
nursing students to practice their assessment skills.

Requirements:
- Varied demographics (mix ages 18-90, different sexes, ethnicities)
- Realistic vital signs for this condition
- Detailed symptom descriptions in patient language (not medical jargon)
- Complete medical history
- A distinct personality and communication style (vary these: anxious, stoic, chatty, confused, angry, scared, cooperative, dismissive)
- Symptoms the patient does NOT have (for denial when asked)
- Relevant lab results
- Assessment rubric with critical findings the student should discover

Return ONLY valid JSON matching this exact schema (no markdown, no code blocks):
{{
    "patient_id": "case_XXX",
    "name": "<realistic full name>",
    "age": <18-90>,
    "sex": "<Male or Female>",
    "ethnicity": "<varied>",
    "weight_lbs": <realistic>,
    "height_inches": <realistic>,
    "chief_complaint": "<in patient's own words, 1 sentence>",
    "onset_description": "<when and how symptoms started>",
    "severity": "<low, medium, high, or critical>",
    "setting": "Emergency Department",
    "symptoms_present": {{
        "<symptom_name>": {{
            "description": "<how patient describes it>",
            "onset": "<when it started>",
            "character": "<nature of symptom>",
            "severity": "<patient's rating>",
            "location": "<where it's felt or null>",
            "radiation": "<where it spreads or null>",
            "aggravating_factors": ["<what makes it worse>"],
            "alleviating_factors": ["<what helps>"],
            "associated_symptoms": ["<related symptoms>"]
        }}
    }},
    "symptoms_absent": ["<symptoms patient denies, at least 10>"],
    "vitals": {{
        "heart_rate": <bpm>,
        "blood_pressure_systolic": <mmHg>,
        "blood_pressure_diastolic": <mmHg>,
        "respiratory_rate": <breaths/min>,
        "spo2": <percentage>,
        "temperature": <fahrenheit>,
        "pain_scale": <0-10>
    }},
    "labs": {{
        "<lab_name>": "<value with units and interpretation>"
    }},
    "past_medical_history": ["<conditions>"],
    "surgical_history": ["<past surgeries>"],
    "medications": ["<current meds with doses>"],
    "allergies": ["<allergies with reaction type>"],
    "social_history": {{
        "smoking": "<status>",
        "alcohol": "<use pattern>",
        "drugs": "<use or denies>",
        "occupation": "<job>",
        "living_situation": "<who they live with>",
        "exercise": "<activity level>",
        "diet": "<eating habits>"
    }},
    "family_history": {{
        "conditions": {{
            "<family_member>": "<condition>"
        }}
    }},
    "personality": "<distinct personality description>",
    "communication_style": "<how they talk to healthcare providers>",
    "pain_description_style": "<how they describe discomfort>",
    "rubric": {{
        "expected_domains": ["HPI", "ROS", "PMH", "Medications", "Allergies", "Social_History", "Family_History"],
        "critical_findings": ["<key things student must discover>"],
        "diagnosis": "<actual diagnosis>",
        "differential_diagnoses": ["<3-5 reasonable differentials>"],
        "recommended_interventions": ["<nursing interventions>"]
    }}
}}"""


def generate_case(client: OpenAI, condition: str, category: str, case_number: int) -> dict | None:
    """Generate a single patient case using the OpenAI API."""
    prompt = GENERATION_PROMPT.format(condition=condition, category=category)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a clinical nursing educator creating realistic patient scenarios. Always respond with valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,  # Higher for variety
            max_tokens=3000,
        )

        content = response.choices[0].message.content.strip()
        # Strip markdown code blocks if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]

        data = json.loads(content)
        data["patient_id"] = f"case_{case_number:03d}"

        # Validate against schema
        PatientScenario(**data)
        return data

    except json.JSONDecodeError as e:
        print(f"  ERROR: Failed to parse JSON for {condition}: {e}")
        return None
    except Exception as e:
        print(f"  ERROR: Failed to generate {condition}: {e}")
        return None


def get_existing_case_numbers(output_dir: Path) -> set[int]:
    """Find which case numbers already exist."""
    numbers = set()
    for f in output_dir.glob("case_*.json"):
        try:
            num = int(f.stem.split("_")[1])
            numbers.add(num)
        except (IndexError, ValueError):
            pass
    return numbers


def main():
    parser = argparse.ArgumentParser(description="Generate patient scenario cases")
    parser.add_argument("--count", type=int, default=0, help="Number of cases to generate (0 = fill all categories)")
    parser.add_argument("--category", type=str, default=None, help="Specific category to generate")
    parser.add_argument("--list-categories", action="store_true", help="List available categories")
    parser.add_argument("--output-dir", type=str, default="data/scenarios", help="Output directory")
    parser.add_argument("--start-number", type=int, default=0, help="Starting case number (0 = auto)")
    args = parser.parse_args()

    if args.list_categories:
        print("Available categories:")
        for cat, info in CATEGORIES.items():
            print(f"  {cat}: {info['count_target']} cases — {', '.join(info['conditions'])}")
        total = sum(c["count_target"] for c in CATEGORIES.values())
        print(f"\nTotal target: {total} cases")
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    existing = get_existing_case_numbers(output_dir)
    next_number = max(existing) + 1 if existing else 3  # Start after hand-crafted cases

    if args.start_number > 0:
        next_number = args.start_number

    client = OpenAI()

    # Determine which conditions to generate
    conditions_to_generate = []
    if args.category:
        if args.category not in CATEGORIES:
            print(f"Unknown category: {args.category}")
            print(f"Available: {', '.join(CATEGORIES.keys())}")
            return
        cat_info = CATEGORIES[args.category]
        count = args.count if args.count > 0 else cat_info["count_target"]
        for i, condition in enumerate(cat_info["conditions"][:count]):
            conditions_to_generate.append((args.category, condition))
    else:
        for cat_name, cat_info in CATEGORIES.items():
            count = args.count if args.count > 0 else cat_info["count_target"]
            for condition in cat_info["conditions"][:count]:
                conditions_to_generate.append((cat_name, condition))

    print(f"Generating {len(conditions_to_generate)} patient cases...")
    print(f"Output directory: {output_dir}")
    print()

    generated = 0
    failed = 0

    for category, condition in conditions_to_generate:
        print(f"[{generated + failed + 1}/{len(conditions_to_generate)}] Generating: {condition} ({category})...")

        data = generate_case(client, condition, category, next_number)
        if data:
            file_path = output_dir / f"case_{next_number:03d}.json"
            with open(file_path, "w") as f:
                json.dump(data, f, indent=4)
            print(f"  Saved: {file_path}")
            generated += 1
            next_number += 1
        else:
            failed += 1

    print(f"\nDone! Generated: {generated}, Failed: {failed}")
    print(f"Total cases in {output_dir}: {len(list(output_dir.glob('*.json')))}")


if __name__ == "__main__":
    main()
