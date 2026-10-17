from scripts.evaluate_mvp import source_expectation_matches


def test_eval_accepts_explicit_equivalent_primary_source():
    expected = ["hust-admission-regulation-2026"]
    alternatives = {"hust-admission-regulation-2026": ["hust-admission-guide-2026"]}

    assert source_expectation_matches(expected, alternatives, ["hust-admission-regulation-2026"])
    assert source_expectation_matches(expected, alternatives, ["hust-admission-guide-2026"])
    assert not source_expectation_matches(expected, alternatives, ["unrelated-source"])


def test_eval_still_requires_every_unrelated_expected_source():
    expected = ["admission-regulation", "english-policy"]
    alternatives = {"admission-regulation": ["admission-guide"]}

    assert not source_expectation_matches(expected, alternatives, ["admission-guide"])
    assert source_expectation_matches(expected, alternatives, ["admission-guide", "english-policy"])
