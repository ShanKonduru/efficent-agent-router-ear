"""Guardrails — prompt injection detection and PII policy enforcement."""
from __future__ import annotations

import logging
import re

from ear.models import GuardrailResult

logger = logging.getLogger(__name__)

# Providers considered vetted for PII-containing prompts.
PII_VETTED_PROVIDERS: frozenset[str] = frozenset(
    {
        "anthropic",
        "openai",
    }
)

# Regex patterns that signal potential prompt injection attempts.
INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?prior\s+(instructions?|context)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a\s+)?(?:different|new)\s+(?:ai|model|assistant)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(?:if\s+you\s+are\s+)?(?:an?\s+)?unrestricted", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"do\s+anything\s+now", re.IGNORECASE),
]

# Regex patterns for common PII signals.
PII_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),           # SSN
    re.compile(r"\b\d{16}\b"),                         # Credit card (simplified)
    re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),  # Email
    re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),  # Phone (US)
]


class GuardrailsChecker:
    """Runs safety prechecks on a prompt before it is forwarded to any model."""

    def check(self, prompt: str) -> GuardrailResult:
        """Return a GuardrailResult indicating whether the prompt is safe to route."""
        raise NotImplementedError

    def _detect_injection(self, prompt: str) -> bool:
        """Return True if any injection pattern matches the prompt."""
        raise NotImplementedError

    def _detect_pii(self, prompt: str) -> bool:
        """Return True if any PII pattern matches the prompt."""
        raise NotImplementedError

    def filter_candidates_for_pii(
        self,
        model_ids: list[str],
        pii_detected: bool,
    ) -> list[str]:
        """If PII is detected, restrict candidates to vetted providers only."""
        raise NotImplementedError
