"""Metrics — collects and aggregates per-call cost and latency data."""
from __future__ import annotations

import logging
import threading

from ear.models import RouteMetric, SessionSummary

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Thread-safe in-process metrics collector for EAR sessions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics: list[RouteMetric] = []

    def record(self, metric: RouteMetric) -> None:
        """Append a single route metric to the session."""
        with self._lock:
            self._metrics.append(metric)

    def summary(self) -> SessionSummary:
        """Return an aggregated SessionSummary of all recorded metrics."""
        with self._lock:
            total_calls = len(self._metrics)
            total_cost = sum(m.estimated_cost_usd for m in self._metrics)
            total_latency = sum(m.latency_ms for m in self._metrics)
            calls_by_model: dict[str, int] = {}
            for metric in self._metrics:
                calls_by_model[metric.model_id] = calls_by_model.get(metric.model_id, 0) + 1

        return SessionSummary(
            total_calls=total_calls,
            total_cost_usd=total_cost,
            total_latency_ms=total_latency,
            calls_by_model=calls_by_model,
        )

    def reset(self) -> None:
        """Clear all recorded metrics for the current session."""
        with self._lock:
            self._metrics.clear()


_SESSION_COLLECTOR = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Return the process-wide session metrics collector."""
    return _SESSION_COLLECTOR
