"""Tests for AssessmentTracker depth-weighted scoring and domain coverage."""

from app.models.assessment import ASSESSMENT_DOMAINS, depth_label, depth_score
from app.services.assessment_service import AssessmentTracker


def test_depth_label_zero():
    assert depth_label(0) == "Missed"


def test_depth_label_one():
    assert depth_label(1) == "Surface"


def test_depth_label_two():
    assert depth_label(2) == "Explored"


def test_depth_label_three():
    assert depth_label(3) == "Explored"


def test_depth_label_four():
    assert depth_label(4) == "Deep"


def test_depth_label_ten():
    assert depth_label(10) == "Deep"


def test_depth_score_zero():
    assert depth_score(0) == 0.0


def test_depth_score_one():
    assert depth_score(1) == 50.0


def test_depth_score_two():
    assert depth_score(2) == 80.0


def test_depth_score_three():
    assert depth_score(3) == 80.0


def test_depth_score_four():
    assert depth_score(4) == 100.0


def test_fresh_tracker_has_zero_score():
    tracker = AssessmentTracker()
    result = tracker.get_result()
    assert result.coverage_score == 0.0
    assert result.total_questions == 0


def test_fresh_tracker_all_domains_missed():
    tracker = AssessmentTracker()
    missed = tracker.get_missed_domains()
    assert set(missed) == set(ASSESSMENT_DOMAINS)


def test_update_single_domain_marks_covered():
    tracker = AssessmentTracker()
    tracker.update(
        ["HPI"], confidence=0.9, student_message="When did your chest pain start?"
    )
    assert "HPI" in tracker.get_covered_domains()


def test_update_increments_total_questions():
    tracker = AssessmentTracker()
    tracker.update(
        ["HPI"], confidence=0.9, student_message="When did your chest pain start?"
    )
    tracker.update(
        ["PMH"], confidence=0.95, student_message="Any past medical history?"
    )
    assert tracker.get_result().total_questions == 2


def test_update_multi_label_counts_once_total():
    """Multi-label update on one message should add 1 to total_questions, not 2."""
    tracker = AssessmentTracker()
    tracker.update(
        ["HPI", "ROS"], confidence=0.9, student_message="Any other symptoms?"
    )
    assert tracker.get_result().total_questions == 1


def test_update_low_confidence_skipped():
    """Questions below 0.3 confidence should be silently ignored."""
    tracker = AssessmentTracker()
    tracker.update(["HPI"], confidence=0.2, student_message="tell me more")
    assert tracker.get_result().total_questions == 0
    assert tracker.get_result().coverage_score == 0.0


def test_update_exactly_threshold_confidence():
    """Confidence exactly 0.3 is below the strict threshold (< 0.3 is skipped)."""
    tracker = AssessmentTracker()
    tracker.update(["HPI"], confidence=0.3, student_message="When did it start?")
    # 0.3 is NOT < 0.3, so it should be credited
    assert tracker.get_result().total_questions == 1


def test_depth_surface_after_one_question():
    tracker = AssessmentTracker()
    tracker.update(["HPI"], confidence=0.9, student_message="When did the pain start?")
    hpi_coverage = tracker.get_result().domains["HPI"]
    assert hpi_coverage.depth == "Surface"
    assert hpi_coverage.question_count == 1


def test_depth_explored_after_two_questions():
    tracker = AssessmentTracker()
    tracker.update(["HPI"], confidence=0.9, student_message="When did it start?")
    tracker.update(["HPI"], confidence=0.9, student_message="Does it radiate anywhere?")
    hpi_coverage = tracker.get_result().domains["HPI"]
    assert hpi_coverage.depth == "Explored"
    assert hpi_coverage.question_count == 2


def test_depth_deep_after_four_questions():
    tracker = AssessmentTracker()
    for i in range(4):
        tracker.update(["HPI"], confidence=0.9, student_message=f"HPI question {i+1}")
    hpi_coverage = tracker.get_result().domains["HPI"]
    assert hpi_coverage.depth == "Deep"
    assert hpi_coverage.question_count == 4


def test_coverage_score_one_surface_domain():
    """One domain at Surface (50.0) / 7 domains = ~7.1."""
    tracker = AssessmentTracker()
    tracker.update(["HPI"], confidence=0.9, student_message="When did it start?")
    expected = round(50.0 / 7, 1)
    assert tracker.get_result().coverage_score == expected


def test_coverage_score_all_seven_deep():
    """All 7 domains at Deep should give 100.0."""
    tracker = AssessmentTracker()
    for domain in ASSESSMENT_DOMAINS:
        for i in range(4):
            tracker.update([domain], confidence=0.9, student_message=f"{domain} q{i+1}")
    assert tracker.get_result().coverage_score == 100.0


def test_conversational_domain_not_counted():
    """'conversational' label should not increment coverage."""
    tracker = AssessmentTracker()
    tracker.update(["conversational"], confidence=0.99, student_message="Hello!")
    assert tracker.get_result().total_questions == 0
    assert tracker.get_result().coverage_score == 0.0


def test_unknown_domain_ignored():
    """An unrecognized domain key should be silently skipped."""
    tracker = AssessmentTracker()
    tracker.update(["SomeMadeUpDomain"], confidence=0.9, student_message="test")
    assert tracker.get_result().total_questions == 0


def test_topics_asked_truncated_to_100():
    """Long student messages should be stored truncated to 100 chars."""
    long_msg = "A" * 200
    tracker = AssessmentTracker()
    tracker.update(["HPI"], confidence=0.9, student_message=long_msg)
    stored = tracker.get_result().domains["HPI"].topics_asked[0]
    assert len(stored) == 100


def test_get_covered_and_missed_disjoint():
    """covered + missed should always equal all 7 domains."""
    tracker = AssessmentTracker()
    tracker.update(["HPI"], confidence=0.9, student_message="q1")
    tracker.update(["PMH"], confidence=0.9, student_message="q2")
    covered = set(tracker.get_covered_domains())
    missed = set(tracker.get_missed_domains())
    assert covered | missed == set(ASSESSMENT_DOMAINS)
    assert covered & missed == set()
