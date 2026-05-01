"""Shared pytest fixtures for EAR test suite."""
from __future__ import annotations

import pytest

from ear.config import EARConfig
from ear.models import BudgetPriority, LLMPricing, LLMSpec, TaskType


@pytest.fixture()
def config(monkeypatch: pytest.MonkeyPatch) -> EARConfig:
    """Return a minimal EARConfig with a fake API key for testing."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
    return EARConfig()  # type: ignore[call-arg]


@pytest.fixture()
def sample_llm_spec() -> LLMSpec:
    """Return a single LLMSpec suitable for unit tests."""
    return LLMSpec(
        id="openai/gpt-4o",
        name="GPT-4o",
        context_length=128_000,
        pricing=LLMPricing(prompt=0.000005, completion=0.000015),
    )


@pytest.fixture()
def cheap_llm_spec() -> LLMSpec:
    """Return a cheap, small-context LLMSpec for budget tests."""
    return LLMSpec(
        id="openai/gpt-4o-mini",
        name="GPT-4o-mini",
        context_length=16_000,
        pricing=LLMPricing(prompt=0.0000001, completion=0.0000002),
    )


@pytest.fixture()
def mega_context_spec() -> LLMSpec:
    """Return a mega-context LLMSpec for large-prompt routing tests."""
    return LLMSpec(
        id="google/gemini-1.5-pro",
        name="Gemini 1.5 Pro",
        context_length=2_000_000,
        pricing=LLMPricing(prompt=0.000007, completion=0.000021),
    )


@pytest.fixture()
def model_catalog(
    sample_llm_spec: LLMSpec,
    cheap_llm_spec: LLMSpec,
    mega_context_spec: LLMSpec,
) -> list[LLMSpec]:
    """Return a multi-model catalog covering all routing scenarios."""
    return [sample_llm_spec, cheap_llm_spec, mega_context_spec]
