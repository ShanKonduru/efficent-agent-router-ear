"""Tests for ear.guardrails — injection detection and PII policy.

Stubs: full implementation tests added in M3 (E6).
"""
from __future__ import annotations

import pytest

from ear.guardrails import GuardrailsChecker


class TestGuardrailsCheckerInit:
    def test_instantiation(self) -> None:
        checker = GuardrailsChecker()
        assert checker is not None

    def test_check_not_implemented(self) -> None:
        checker = GuardrailsChecker()
        with pytest.raises(NotImplementedError):
            checker.check("Hello world")
