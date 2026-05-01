"""Tests for ear.metrics — RouteMetric collection and SessionSummary aggregation.

Stubs: full implementation tests added in M3 (E7).
"""
from __future__ import annotations

import pytest

from ear.metrics import MetricsCollector
from ear.models import RouteMetric, TaskType


class TestMetricsCollectorInit:
    def test_instantiation(self) -> None:
        collector = MetricsCollector()
        assert collector is not None

    def test_record_not_implemented(self) -> None:
        collector = MetricsCollector()
        metric = RouteMetric(
            model_id="openai/gpt-4o",
            latency_ms=120.0,
            estimated_cost_usd=0.001,
            task_type=TaskType.SIMPLE,
            success=True,
        )
        with pytest.raises(NotImplementedError):
            collector.record(metric)

    def test_summary_not_implemented(self) -> None:
        collector = MetricsCollector()
        with pytest.raises(NotImplementedError):
            collector.summary()

    def test_reset_not_implemented(self) -> None:
        collector = MetricsCollector()
        with pytest.raises(NotImplementedError):
            collector.reset()
