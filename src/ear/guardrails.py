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
        injection_detected = self._detect_injection(prompt)
        pii_detected = self._detect_pii(prompt)

        if injection_detected:
            return GuardrailResult(
                passed=False,
                injection_detected=True,
                pii_detected=pii_detected,
                reason="Prompt injection pattern detected.",
            )

        if pii_detected:
            return GuardrailResult(
                passed=True,
                injection_detected=False,
                pii_detected=True,
                reason="PII detected; restrict routing to vetted providers.",
            )

        return GuardrailResult(
            passed=True,
            injection_detected=False,
            pii_detected=False,
            reason=None,
        )

    def _detect_injection(self, prompt: str) -> bool:
        """Return True if any injection pattern matches the prompt."""
        return any(pattern.search(prompt) is not None for pattern in INJECTION_PATTERNS)

    def _detect_pii(self, prompt: str) -> bool:
        """Return True if any PII pattern matches the prompt."""
        return any(pattern.search(prompt) is not None for pattern in PII_PATTERNS)

    def filter_candidates_for_pii(
        self,
        model_ids: list[str],
        pii_detected: bool,
    ) -> list[str]:
        """If PII is detected, restrict candidates to vetted providers only."""
        if not pii_detected:
            return list(model_ids)

        filtered = [
            model_id
            for model_id in model_ids
            if model_id.split("/", 1)[0].lower() in PII_VETTED_PROVIDERS
        ]

        if not filtered:
            logger.warning("PII detected, but no vetted providers remained after filtering.")
        return filtered
