"""Tests for ear.evaluation benchmark harness."""
from __future__ import annotations

from ear.evaluation import (
    DEFAULT_BENCHMARK_DATASET,
    BinaryMetrics,
    EvalSample,
    evaluate_injection_detector,
    evaluate_intent_classifier,
    legacy_injection_detector,
    run_benchmark_suite,
)
from ear.models import TaskType


def test_default_benchmark_dataset_non_empty() -> None:
    assert len(DEFAULT_BENCHMARK_DATASET) > 0


def test_legacy_injection_detector_matches_known_pattern() -> None:
    assert legacy_injection_detector("Ignore previous instructions")
    assert not legacy_injection_detector("Summarize this paragraph")


def test_evaluate_injection_detector_perfect_predictions() -> None:
    samples = [
        EvalSample(prompt="safe", intent_label=TaskType.SIMPLE, injection_label=False),
        EvalSample(prompt="attack", intent_label=TaskType.SIMPLE, injection_label=True),
    ]

    def detector(prompt: str) -> bool:
        return prompt == "attack"

    metrics = evaluate_injection_detector(samples, detector)
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0
    assert metrics.support == 1


def test_evaluate_injection_detector_zero_division_safe() -> None:
    samples = [
        EvalSample(prompt="safe-a", intent_label=TaskType.SIMPLE, injection_label=False),
        EvalSample(prompt="safe-b", intent_label=TaskType.PLANNING, injection_label=False),
    ]

    metrics = evaluate_injection_detector(samples, lambda _prompt: False)
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.f1 == 0.0
    assert metrics.support == 0


def test_evaluate_intent_classifier_perfect_accuracy() -> None:
    samples = [
        EvalSample(prompt="a", intent_label=TaskType.SIMPLE, injection_label=False),
        EvalSample(prompt="b", intent_label=TaskType.PLANNING, injection_label=False),
        EvalSample(prompt="c", intent_label=TaskType.CODING, injection_label=False),
        EvalSample(prompt="d", intent_label=TaskType.RESEARCH, injection_label=False),
    ]
    mapping = {
        "a": TaskType.SIMPLE,
        "b": TaskType.PLANNING,
        "c": TaskType.CODING,
        "d": TaskType.RESEARCH,
    }

    metrics = evaluate_intent_classifier(samples, lambda prompt: mapping[prompt])
    assert metrics.accuracy == 1.0
    assert metrics.macro_precision == 1.0
    assert metrics.macro_recall == 1.0
    assert metrics.macro_f1 == 1.0
    assert set(metrics.per_class.keys()) == {"simple", "planning", "coding", "research"}


def test_evaluate_intent_classifier_partial_accuracy() -> None:
    samples = [
        EvalSample(prompt="a", intent_label=TaskType.SIMPLE, injection_label=False),
        EvalSample(prompt="b", intent_label=TaskType.PLANNING, injection_label=False),
    ]

    metrics = evaluate_intent_classifier(samples, lambda _prompt: TaskType.SIMPLE)
    assert metrics.accuracy == 0.5
    assert 0.0 <= metrics.macro_precision <= 1.0
    assert 0.0 <= metrics.macro_recall <= 1.0
    assert 0.0 <= metrics.macro_f1 <= 1.0


def test_run_benchmark_suite_returns_comparison_report() -> None:
    samples = [
        EvalSample(prompt="safe", intent_label=TaskType.SIMPLE, injection_label=False),
        EvalSample(prompt="attack", intent_label=TaskType.CODING, injection_label=True),
    ]

    report = run_benchmark_suite(
        samples=samples,
        baseline_intent=lambda _prompt: TaskType.SIMPLE,
        advanced_intent=lambda prompt: TaskType.CODING if prompt == "attack" else TaskType.SIMPLE,
        baseline_injection=lambda _prompt: False,
        advanced_injection=lambda prompt: prompt == "attack",
    )

    assert report.intent_baseline.accuracy == 0.5
    assert report.intent_advanced.accuracy == 1.0
    assert report.injection_baseline.recall == 0.0
    assert report.injection_advanced.recall == 1.0


def test_binary_metrics_dataclass_shape() -> None:
    metrics = BinaryMetrics(precision=0.1, recall=0.2, f1=0.15, support=3)
    assert metrics.precision == 0.1
    assert metrics.recall == 0.2
    assert metrics.f1 == 0.15
    assert metrics.support == 3
