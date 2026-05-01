"""Tests for ear.metrics — RouteMetric collection and SessionSummary aggregation."""
from __future__ import annotations

from ear.metrics import MetricsCollector
from ear.models import RouteMetric, TaskType


class TestMetricsCollectorInit:
    def test_instantiation(self) -> None:
        collector = MetricsCollector()
        assert collector is not None

    def test_record_adds_metric(self) -> None:
        collector = MetricsCollector()
        metric = RouteMetric(
            model_id="openai/gpt-4o",
            latency_ms=120.0,
            estimated_cost_usd=0.001,
            task_type=TaskType.SIMPLE,
            success=True,
        )
        collector.record(metric)
        summary = collector.summary()
        assert summary.total_calls == 1
        assert summary.calls_by_model == {"openai/gpt-4o": 1}

    def test_summary_aggregates_multiple_calls(self) -> None:
        collector = MetricsCollector()
        collector.record(
            RouteMetric(
                model_id="openai/gpt-4o",
                latency_ms=100.0,
                estimated_cost_usd=0.002,
                task_type=TaskType.CODING,
                success=True,
            )
        )
        collector.record(
            RouteMetric(
                model_id="openai/gpt-4o-mini",
                latency_ms=80.0,
                estimated_cost_usd=0.001,
                task_type=TaskType.SIMPLE,
                success=True,
            )
        )
        collector.record(
            RouteMetric(
                model_id="openai/gpt-4o",
                latency_ms=70.0,
                estimated_cost_usd=0.003,
                task_type=TaskType.RESEARCH,
                success=False,
            )
        )

        summary = collector.summary()
        assert summary.total_calls == 3
        assert summary.total_latency_ms == 250.0
        assert summary.total_cost_usd == 0.006
        assert summary.calls_by_model == {
            "openai/gpt-4o": 2,
            "openai/gpt-4o-mini": 1,
        }

    def test_reset_clears_metrics(self) -> None:
        collector = MetricsCollector()
        collector.record(
            RouteMetric(
                model_id="openai/gpt-4o",
                latency_ms=10.0,
                estimated_cost_usd=0.0001,
                task_type=TaskType.SIMPLE,
                success=True,
            )
        )

        collector.reset()

        summary = collector.summary()
        assert summary.total_calls == 0
        assert summary.total_cost_usd == 0.0
        assert summary.total_latency_ms == 0.0
        assert summary.calls_by_model == {}
