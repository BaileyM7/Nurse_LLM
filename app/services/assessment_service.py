from app.models.assessment import (
    ASSESSMENT_DOMAINS,
    AssessmentResult,
    DomainCoverage,
    depth_score,
)


class AssessmentTracker:
    """Tracks per-domain coverage; emits a depth-weighted score."""

    def __init__(self):
        self.result = AssessmentResult(
            domains={
                domain: DomainCoverage(domain=domain) for domain in ASSESSMENT_DOMAINS
            }
        )

    def update(
        self, domains: list[str], confidence: float, student_message: str
    ) -> None:
        """Record that a student explored one or more domains; skips if confidence < 0.3."""
        if confidence < 0.3:
            return

        credited_any = False
        for domain_name in domains:
            if domain_name == "conversational":
                continue
            domain_key = self._normalize_domain(domain_name)
            if domain_key not in self.result.domains:
                continue

            coverage = self.result.domains[domain_key]
            coverage.covered = True
            coverage.question_count += 1
            coverage.topics_asked.append(student_message[:100])
            credited_any = True

        if credited_any:
            self.result.total_questions += 1
            self._recalculate_score()

    def _normalize_domain(self, domain: str) -> str:
        """Map classifier output domain names to our standard domain keys."""
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
        """Depth-weighted coverage: each domain contributes 0-100 based on depth,
        then average across all 7 domains."""
        if not self.result.domains:
            self.result.coverage_score = 0.0
            return
        total = sum(depth_score(c.question_count) for c in self.result.domains.values())
        self.result.coverage_score = round(total / len(self.result.domains), 1)

    def get_result(self) -> AssessmentResult:
        return self.result

    def get_covered_domains(self) -> list[str]:
        return self.result.get_covered_domains()

    def get_missed_domains(self) -> list[str]:
        return self.result.get_missed_domains()
