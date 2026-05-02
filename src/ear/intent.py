"""Advanced intent classification with learned embedding/flash model and deterministic fallback.

This module provides two implementations:
- `HeuristicIntentClassifier`: keyword-based deterministic classification (fallback).
- `AdvancedIntentClassifier`: embedding-based or flash-model classification with automatic
  fallback to heuristics on error or unavailability.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

import httpx

from ear.config import EARConfig
from ear.models import TaskType

logger = logging.getLogger(__name__)

# Keyword sets used by fallback classifier.
_CODING_KEYWORDS: frozenset[str] = frozenset(
    {
        "def ", "class ", "import ", "function ", "algorithm", "debug",
        "refactor", "implement", "code", "script", "program", "=>",
    }
)

_PLANNING_KEYWORDS: frozenset[str] = frozenset(
    {
        "plan", "roadmap", "strategy", "step by step", "steps to", "outline",
        "design", "architecture", "sequence", "schedule", "milestone",
    }
)

_RESEARCH_KEYWORDS: frozenset[str] = frozenset(
    {
        "research", "survey", "summarize", "compare", "difference between",
        "explain", "what is", "literature", "study", "analyze", "review",
    }
)


class IntentClassifier(ABC):
    """Abstract base for intent classifiers."""

    @abstractmethod
    def classify(self, prompt: str) -> TaskType:
        """Classify the prompt into a TaskType."""
        pass  # pragma: no cover


class HeuristicIntentClassifier(IntentClassifier):
    """Keyword-based deterministic intent classification (fallback)."""

    def classify(self, prompt: str) -> TaskType:
        """Return the TaskType for the given prompt using keyword heuristics.

        Detection order (highest specificity first):
        1. Any fenced code block (triple-backtick) → CODING
        2. Keyword vote among CODING / PLANNING / RESEARCH sets; winner wins.
        3. Tie or no signals → SIMPLE.
        """
        # Fenced code block is an unambiguous coding signal.
        if "```" in prompt:
            return TaskType.CODING

        lower = prompt.lower()
        coding_hits = sum(1 for kw in _CODING_KEYWORDS if kw in lower)
        planning_hits = sum(1 for kw in _PLANNING_KEYWORDS if kw in lower)
        research_hits = sum(1 for kw in _RESEARCH_KEYWORDS if kw in lower)

        max_hits = max(coding_hits, planning_hits, research_hits)

        if max_hits == 0:
            return TaskType.SIMPLE
        if coding_hits == max_hits:
            return TaskType.CODING
        if planning_hits == max_hits:
            return TaskType.PLANNING
        return TaskType.RESEARCH


class AdvancedIntentClassifier(IntentClassifier):
    """Embedding-based or flash-model intent classification with fallback to heuristics.

    Attempts to classify using a remote embedding model or flash classifier endpoint.
    On error, timeout, or misconfiguration, falls back to keyword-based heuristics.
    """

    def __init__(
        self,
        config: EARConfig,
        fallback: IntentClassifier | None = None,
    ) -> None:
        """Initialize advanced classifier.

        Args:
            config: EAR configuration with OpenRouter base URL and API key.
            fallback: Optional fallback classifier. Defaults to HeuristicIntentClassifier.
        """
        self._config = config
        self._fallback = fallback or HeuristicIntentClassifier()
        self._base_url = config.ear_openrouter_base_url.rstrip("/")
        self._api_key = config.openrouter_api_key
        self._timeout_seconds = config.ear_request_timeout_seconds
        self._model_id = "openrouter/text-embedding-3-small"  # Flash embedding model for intent

    async def classify_async(self, prompt: str) -> TaskType:
        """Asynchronously classify using embedding model, fall back to heuristics on error.

        Args:
            prompt: The prompt to classify.

        Returns:
            TaskType classification result.
        """
        # Skip advanced classification if API key is missing.
        if not self._api_key:
            logger.debug("No OpenRouter API key; using heuristic fallback for intent classification")
            return self._fallback.classify(prompt)

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                result = await self._call_embedding_model(client, prompt)
                return result
        except Exception as e:
            logger.warning(
                "Advanced intent classification failed (error=%s); falling back to heuristics",
                type(e).__name__,
            )
            return self._fallback.classify(prompt)

    def classify(self, prompt: str) -> TaskType:
        """Synchronous classify that falls back to heuristics.

        Note: This is a synchronous method for compatibility with existing code.
        For best results with the advanced classifier, use ``classify_async``.
        """
        return self._fallback.classify(prompt)

    async def _call_embedding_model(self, client: httpx.AsyncClient, prompt: str) -> TaskType:
        """Call the embedding model to generate embeddings and classify.

        Maps embedding patterns to TaskType labels:
        - Coding-like embeddings cluster → CODING
        - Planning-like embeddings cluster → PLANNING
        - Research-like embeddings cluster → RESEARCH
        - Default → SIMPLE
        """
        # Create reference prompts for each task type
        coding_prompt = "def function(): pass  # write a python function to solve an algorithm problem"
        planning_prompt = "create a plan and roadmap with steps to achieve the goal"
        research_prompt = "research and analyze the differences in a comprehensive survey"
        simple_prompt = "answer a simple question"

        # Embed the input prompt and all reference prompts
        prompts_to_embed = [prompt, coding_prompt, planning_prompt, research_prompt, simple_prompt]
        embeddings = await self._get_embeddings(client, prompts_to_embed)

        if not embeddings or len(embeddings) < 5:
            raise ValueError("Failed to get embeddings for all reference prompts")

        input_emb = embeddings[0]
        coding_emb = embeddings[1]
        planning_emb = embeddings[2]
        research_emb = embeddings[3]
        simple_emb = embeddings[4]

        # Compute cosine similarity to each reference prompt
        coding_sim = self._cosine_similarity(input_emb, coding_emb)
        planning_sim = self._cosine_similarity(input_emb, planning_emb)
        research_sim = self._cosine_similarity(input_emb, research_emb)
        simple_sim = self._cosine_similarity(input_emb, simple_emb)

        # Select the task type with highest similarity
        similarities = {
            TaskType.CODING: coding_sim,
            TaskType.PLANNING: planning_sim,
            TaskType.RESEARCH: research_sim,
            TaskType.SIMPLE: simple_sim,
        }
        selected = max(similarities, key=similarities.get)

        logger.debug(
            "Advanced intent classification: prompt=%s similarities=%s selected=%s",
            prompt[:50],
            {k.value: f"{v:.3f}" for k, v in similarities.items()},
            selected.value,
        )

        return selected

    async def _get_embeddings(self, client: httpx.AsyncClient, prompts: list[str]) -> list[list[float]]:
        """Get embeddings from OpenRouter embedding model endpoint.

        Args:
            client: Async HTTP client.
            prompts: List of text prompts to embed.

        Returns:
            List of embedding vectors (each a list of floats).

        Raises:
            httpx.HTTPError: On HTTP errors.
            ValueError: On invalid response format.
        """
        url = f"{self._base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model_id,
            "input": prompts,
        }

        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        embeddings_data = data.get("data", [])

        if not embeddings_data:
            raise ValueError("No embeddings in response")

        # Sort by index and extract embedding vectors
        embeddings_data.sort(key=lambda x: x.get("index", 0))
        embeddings = [item.get("embedding", []) for item in embeddings_data]

        return embeddings

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        mag_a = sum(a * a for a in vec_a) ** 0.5
        mag_b = sum(b * b for b in vec_b) ** 0.5

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot_product / (mag_a * mag_b)
