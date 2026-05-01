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
        raise NotImplementedError

    def summary(self) -> SessionSummary:
        """Return an aggregated SessionSummary of all recorded metrics."""
        raise NotImplementedError

    def reset(self) -> None:
        """Clear all recorded metrics for the current session."""
        raise NotImplementedError
