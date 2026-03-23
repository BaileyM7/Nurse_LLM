from app.models.assessment import ASSESSMENT_DOMAINS, AssessmentResult, DomainCoverage


class AssessmentTracker:
    """
    Tracks which clinical assessment domains a student has explored during a session.

    Updated after each patient response using the inline domain classification
    from the LLM's structured output.
    """

    def __init__(self):
        self.result = AssessmentResult(
            domains={
                domain: DomainCoverage(domain=domain)
                for domain in ASSESSMENT_DOMAINS
            }
        )

    def update(self, domain_explored: str, confidence: float, student_message: str) -> None:
        """Record that a student explored a given domain."""
        if domain_explored == "conversational" or confidence < 0.3:
            return

        # Normalize domain name to match our standard list
        domain_key = self._normalize_domain(domain_explored)
        if domain_key not in self.result.domains:
            return

        coverage = self.result.domains[domain_key]
        coverage.covered = True
        coverage.question_count += 1
        # Store a truncated version of what they asked
        coverage.topics_asked.append(student_message[:100])
        self.result.total_questions += 1
        self._recalculate_score()

    def _normalize_domain(self, domain: str) -> str:
        """Map LLM output domain names to our standard domain keys."""
        domain_lower = domain.lower().replace(" ", "_")
        mapping = {
            "hpi": "HPI",
            "history_of_present_illness": "HPI",
            "ros": "ROS",
            "review_of_systems": "ROS",
            "pmh": "PMH",
            "past_medical_history": "PMH",
            "medications": "Medications",
            "meds": "Medications",
            "allergies": "Allergies",
            "social_history": "Social_History",
            "social_hx": "Social_History",
            "family_history": "Family_History",
            "family_hx": "Family_History",
        }
        return mapping.get(domain_lower, domain)

    def _recalculate_score(self) -> None:
        covered = sum(1 for c in self.result.domains.values() if c.covered)
        total = len(self.result.domains)
        self.result.coverage_score = round((covered / total) * 100, 1) if total > 0 else 0.0

    def get_result(self) -> AssessmentResult:
        return self.result

    def get_covered_domains(self) -> list[str]:
        return self.result.get_covered_domains()

    def get_missed_domains(self) -> list[str]:
        return self.result.get_missed_domains()
