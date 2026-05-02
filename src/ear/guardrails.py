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

# Semantic injection signals with risk weights. Weights are aggregated and clipped
# to [0.0, 1.0] to produce a deterministic risk score.
_SEMANTIC_INJECTION_SIGNALS: dict[str, tuple[re.Pattern[str], float]] = {
    "INJ_OVERRIDE_INSTRUCTIONS": (
        re.compile(r"ignore\s+(all\s+)?(previous|prior|earlier)\s+instructions?", re.IGNORECASE),
        0.80,
    ),
    "INJ_ROLE_REDEFINITION": (
        re.compile(r"you\s+are\s+now\s+(?:a\s+)?(?:different|new)\s+(?:ai|model|assistant)", re.IGNORECASE),
        0.70,
    ),
    "INJ_DISABLE_SAFETY": (
        re.compile(r"(?:disable|bypass|turn\s+off)\s+(?:all\s+)?(?:safety|guardrails|policy)", re.IGNORECASE),
        0.80,
    ),
    "INJ_SYSTEM_PROMPT_EXFIL": (
        re.compile(
            r"(?:reveal|show|print|leak)\s+(?:your\s+)?(?:hidden\s+system|system|hidden)\s+(?:prompt|instructions?)",
            re.IGNORECASE,
        ),
        0.45,
    ),
    "INJ_TOOL_OVERRIDE": (
        re.compile(r"ignore\s+tool\s+rules?|skip\s+validation|force\s+tool\s+call", re.IGNORECASE),
        0.50,
    ),
    "INJ_JAILBREAK": (
        re.compile(r"jailbreak|do\s+anything\s+now|dan\b", re.IGNORECASE),
        0.75,
    ),
}

INJECTION_ELEVATED_THRESHOLD: float = 0.40
INJECTION_BLOCK_THRESHOLD: float = 0.70

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
        injection_risk_score, injection_reason_codes = self._score_semantic_injection(prompt)
        injection_detected = injection_risk_score >= INJECTION_ELEVATED_THRESHOLD
        pii_detected = self._detect_pii(prompt)

        if injection_risk_score >= INJECTION_BLOCK_THRESHOLD:
            return GuardrailResult(
                passed=False,
                injection_detected=True,
                pii_detected=pii_detected,
                reason="Prompt injection risk exceeded block threshold.",
                reason_codes=[*injection_reason_codes, "INJECTION_BLOCKED"],
                risk_score=injection_risk_score,
            )

        if injection_detected:
            return GuardrailResult(
                passed=True,
                injection_detected=True,
                pii_detected=pii_detected,
                reason="Elevated prompt injection risk detected; route with caution.",
                reason_codes=[*injection_reason_codes, "INJECTION_RISK_ELEVATED"],
                risk_score=injection_risk_score,
            )

        if pii_detected:
            return GuardrailResult(
                passed=True,
                injection_detected=False,
                pii_detected=True,
                reason="PII detected; restrict routing to vetted providers.",
                reason_codes=["PII_DETECTED"],
                risk_score=injection_risk_score,
            )

        return GuardrailResult(
            passed=True,
            injection_detected=False,
            pii_detected=False,
            reason=None,
            reason_codes=[],
            risk_score=injection_risk_score,
        )

    def _detect_injection(self, prompt: str) -> bool:
        """Return True if any injection pattern matches the prompt."""
        score, _ = self._score_semantic_injection(prompt)
        return score >= INJECTION_ELEVATED_THRESHOLD

    def _score_semantic_injection(self, prompt: str) -> tuple[float, list[str]]:
        """Return a deterministic injection risk score and matched reason codes.

        The score is computed from weighted semantic signals and clipped to [0, 1].
        """
        lowered = prompt.lower()

        score = 0.0
        reason_codes: set[str] = set()

        for reason_code, (pattern, weight) in _SEMANTIC_INJECTION_SIGNALS.items():
            if pattern.search(lowered) is not None:
                score += weight
                reason_codes.add(reason_code)

        # Backward-compatible hard-pattern pass so legacy patterns still influence risk.
        if any(pattern.search(lowered) is not None for pattern in INJECTION_PATTERNS):
            score += 0.40
            reason_codes.add("INJ_LEGACY_PATTERN")

        bounded_score = min(1.0, max(0.0, score))
        return bounded_score, sorted(reason_codes)

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
