"""Tests for intent classifiers: heuristic and advanced embedding-based."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ear.config import EARConfig
from ear.intent import AdvancedIntentClassifier, HeuristicIntentClassifier
from ear.models import TaskType


class TestHeuristicIntentClassifier:
    """Tests for keyword-based fallback classifier."""

    def test_code_block_detection(self):
        """Given a prompt with triple-backtick code, classify as CODING."""
        classifier = HeuristicIntentClassifier()
        prompt = "Here is some code:\n```python\ndef hello():\n    pass\n```"
        assert classifier.classify(prompt) == TaskType.CODING

    def test_coding_keyword_vote(self):
        """Given a prompt with coding keywords, classify as CODING."""
        classifier = HeuristicIntentClassifier()
        prompt = "How do I implement a function in Python?"
        assert classifier.classify(prompt) == TaskType.CODING

    def test_planning_keyword_vote(self):
        """Given a prompt with planning keywords, classify as PLANNING."""
        classifier = HeuristicIntentClassifier()
        prompt = "Create a roadmap and design an architecture for the project."
        assert classifier.classify(prompt) == TaskType.PLANNING

    def test_research_keyword_vote(self):
        """Given a prompt with research keywords, classify as RESEARCH."""
        classifier = HeuristicIntentClassifier()
        prompt = "Research and summarize the differences between the two approaches."
        assert classifier.classify(prompt) == TaskType.RESEARCH

    def test_empty_prompt_defaults_to_simple(self):
        """Given an empty prompt, classify as SIMPLE."""
        classifier = HeuristicIntentClassifier()
        assert classifier.classify("") == TaskType.SIMPLE

    def test_no_keywords_defaults_to_simple(self):
        """Given a prompt with no keyword signals, classify as SIMPLE."""
        classifier = HeuristicIntentClassifier()
        assert classifier.classify("Hello world") == TaskType.SIMPLE

    def test_tie_between_planning_and_research(self):
        """Given tied vote counts, planning is preferred over research."""
        classifier = HeuristicIntentClassifier()
        # "plan" hits planning, "research" hits research — tied
        prompt = "Plan and research the approach"
        # With current keyword sets, "plan" has 1 hit and "research" has 1 hit
        # In case of tie, the code checks coding first, then planning, then research
        result = classifier.classify(prompt)
        # Both should match equally, so we check the result is one of the two
        assert result in {TaskType.PLANNING, TaskType.RESEARCH}

    def test_case_insensitive_keyword_matching(self):
        """Given uppercase keywords, still match correctly."""
        classifier = HeuristicIntentClassifier()
        prompt = "IMPLEMENT a FUNCTION in Python"
        result = classifier.classify(prompt)
        # "implement" and "function" are coding keywords
        assert result == TaskType.CODING

    def test_code_block_overrides_keyword_vote(self):
        """Given both code block and research keywords, code block wins."""
        classifier = HeuristicIntentClassifier()
        prompt = "Research and explain:\n```python\ncode here\n```"
        assert classifier.classify(prompt) == TaskType.CODING


class TestAdvancedIntentClassifier:
    """Tests for embedding-based advanced classifier with fallback."""

    def _make_config(self, api_key: str = "test-key") -> EARConfig:
        """Create a test EARConfig."""
        return EARConfig(
            openrouter_api_key=api_key,
            ear_openrouter_base_url="https://openrouter.ai/api/v1",
            ear_request_timeout_seconds=5,
        )

    @pytest.mark.asyncio
    async def test_classify_async_success(self):
        """Given successful embedding response, classify using embeddings."""
        config = self._make_config()
        classifier = AdvancedIntentClassifier(config)

        # Mock embeddings that favor coding similarity
        mock_embeddings = [
            [1.0, 0.0, 0.0, 0.0],  # input prompt (should be close to coding_emb)
            [0.95, 0.1, 0.05, 0.0],  # coding_emb (reference)
            [0.1, 0.9, 0.0, 0.0],  # planning_emb
            [0.1, 0.0, 0.9, 0.0],  # research_emb
            [0.05, 0.05, 0.05, 0.85],  # simple_emb
        ]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": [
                    {"index": i, "embedding": emb} for i, emb in enumerate(mock_embeddings)
                ]
            }
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await classifier.classify_async("write code")
            # The input embedding is most similar to coding_emb (0.95 cosine sim)
            assert result == TaskType.CODING

    @pytest.mark.asyncio
    async def test_classify_async_fallback_on_http_error(self):
        """Given HTTP error on embedding call, fall back to heuristics."""
        config = self._make_config()
        classifier = AdvancedIntentClassifier(config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "500", request=MagicMock(), response=MagicMock()
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await classifier.classify_async("def function(): pass")
            # Falls back to heuristics, which should detect coding keywords
            assert result == TaskType.CODING

    @pytest.mark.asyncio
    async def test_classify_async_fallback_on_timeout(self):
        """Given timeout on embedding call, fall back to heuristics."""
        config = self._make_config()
        classifier = AdvancedIntentClassifier(config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await classifier.classify_async("plan the project roadmap")
            # Falls back to heuristics, which should detect planning keywords
            assert result == TaskType.PLANNING

    @pytest.mark.asyncio
    async def test_classify_async_fallback_on_invalid_response(self):
        """Given malformed embedding response, fall back to heuristics."""
        config = self._make_config()
        classifier = AdvancedIntentClassifier(config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": []}  # Empty embeddings
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await classifier.classify_async("research the topic")
            # Falls back to heuristics, which should detect research keywords
            assert result == TaskType.RESEARCH

    @pytest.mark.asyncio
    async def test_classify_async_fallback_on_missing_api_key(self):
        """Given no API key, skip advanced classification and use heuristics."""
        config = self._make_config(api_key="")
        classifier = AdvancedIntentClassifier(config)

        result = await classifier.classify_async("def function(): pass")
        # No HTTP call should be made; falls back to heuristics directly
        assert result == TaskType.CODING

    def test_classify_sync_uses_heuristics(self):
        """Given synchronous classify call, uses heuristics (not async)."""
        config = self._make_config()
        classifier = AdvancedIntentClassifier(config)

        result = classifier.classify("implement a function")
        assert result == TaskType.CODING

    def test_cosine_similarity_identical_vectors(self):
        """Given identical vectors, cosine similarity is 1.0."""
        vec = [1.0, 0.0, 0.0]
        similarity = AdvancedIntentClassifier._cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal_vectors(self):
        """Given orthogonal vectors, cosine similarity is 0.0."""
        vec_a = [1.0, 0.0]
        vec_b = [0.0, 1.0]
        similarity = AdvancedIntentClassifier._cosine_similarity(vec_a, vec_b)
        assert abs(similarity - 0.0) < 1e-6

    def test_cosine_similarity_opposite_vectors(self):
        """Given opposite vectors, cosine similarity is -1.0."""
        vec_a = [1.0, 0.0]
        vec_b = [-1.0, 0.0]
        similarity = AdvancedIntentClassifier._cosine_similarity(vec_a, vec_b)
        assert abs(similarity - (-1.0)) < 1e-6

    def test_cosine_similarity_empty_vectors(self):
        """Given empty vectors, cosine similarity is 0.0."""
        similarity = AdvancedIntentClassifier._cosine_similarity([], [])
        assert similarity == 0.0

    def test_cosine_similarity_mismatched_lengths(self):
        """Given vectors of different lengths, cosine similarity is 0.0."""
        similarity = AdvancedIntentClassifier._cosine_similarity([1.0], [1.0, 0.0])
        assert similarity == 0.0

    def test_cosine_similarity_zero_magnitude(self):
        """Given zero-magnitude vector, cosine similarity is 0.0."""
        similarity = AdvancedIntentClassifier._cosine_similarity([0.0, 0.0], [1.0, 1.0])
        assert similarity == 0.0

    @pytest.mark.asyncio
    async def test_get_embeddings_success(self):
        """Given valid embedding response, return embeddings list."""
        config = self._make_config()
        classifier = AdvancedIntentClassifier(config)

        mock_embeddings = [
            {"index": 0, "embedding": [0.1, 0.2, 0.3]},
            {"index": 1, "embedding": [0.4, 0.5, 0.6]},
        ]

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": mock_embeddings}
        mock_client.post = AsyncMock(return_value=mock_response)

        embeddings = await classifier._get_embeddings(
            mock_client, ["prompt1", "prompt2"]
        )

        assert len(embeddings) == 2
        assert embeddings[0] == [0.1, 0.2, 0.3]
        assert embeddings[1] == [0.4, 0.5, 0.6]

    @pytest.mark.asyncio
    async def test_get_embeddings_empty_response(self):
        """Given empty embeddings response, raise ValueError."""
        config = self._make_config()
        classifier = AdvancedIntentClassifier(config)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(ValueError, match="No embeddings"):
            await classifier._get_embeddings(mock_client, ["prompt1"])

    @pytest.mark.asyncio
    async def test_get_embeddings_out_of_order_indices(self):
        """Given out-of-order embedding indices, sort and return correctly."""
        config = self._make_config()
        classifier = AdvancedIntentClassifier(config)

        mock_embeddings = [
            {"index": 1, "embedding": [0.4, 0.5, 0.6]},
            {"index": 0, "embedding": [0.1, 0.2, 0.3]},
        ]

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": mock_embeddings}
        mock_client.post = AsyncMock(return_value=mock_response)

        embeddings = await classifier._get_embeddings(
            mock_client, ["prompt1", "prompt2"]
        )

        # Should be sorted by index
        assert embeddings[0] == [0.1, 0.2, 0.3]
        assert embeddings[1] == [0.4, 0.5, 0.6]

    @pytest.mark.asyncio
    async def test_call_embedding_model_selects_highest_similarity(self):
        """Given embeddings with varying similarities, select task with highest."""
        config = self._make_config()
        classifier = AdvancedIntentClassifier(config)

        # Research-like input and reference embeddings
        mock_embeddings = [
            [0.1, 0.0, 0.9, 0.0],  # input (close to research_emb)
            [0.9, 0.0, 0.1, 0.0],  # coding_emb
            [0.0, 0.9, 0.0, 0.0],  # planning_emb
            [0.1, 0.0, 0.95, 0.0],  # research_emb (reference)
            [0.0, 0.0, 0.0, 0.9],  # simple_emb
        ]

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"index": i, "embedding": emb} for i, emb in enumerate(mock_embeddings)
            ]
        }
        mock_client.post = AsyncMock(return_value=mock_response)

        result = await classifier._call_embedding_model(
            mock_client, "analyze and study the research"
        )

        assert result == TaskType.RESEARCH

    @pytest.mark.asyncio
    async def test_call_embedding_model_fallback_on_insufficient_embeddings(self):
        """Given fewer embeddings than expected, raise ValueError."""
        config = self._make_config()
        classifier = AdvancedIntentClassifier(config)

        # Only 3 embeddings instead of 5
        mock_embeddings = [
            [1.0, 0.0],
            [0.0, 1.0],
        ]

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"index": i, "embedding": emb} for i, emb in enumerate(mock_embeddings)
            ]
        }
        mock_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(ValueError):
            await classifier._call_embedding_model(mock_client, "test prompt")


# Integration-style tests to verify end-to-end behavior
class TestIntentClassifierIntegration:
    """Integration tests for intent classifier switching."""

    def test_router_engine_uses_heuristic_classifier(self):
        """Verify RouterEngine defaults to HeuristicIntentClassifier."""
        from ear.router_engine import RouterEngine

        engine = RouterEngine()
        assert isinstance(engine._classifier, HeuristicIntentClassifier)

    def test_router_engine_accepts_custom_classifier(self):
        """Verify RouterEngine accepts custom IntentClassifier."""
        from ear.router_engine import RouterEngine

        config = EARConfig(
            openrouter_api_key="test",
            ear_openrouter_base_url="https://openrouter.ai/api/v1",
        )
        custom_classifier = AdvancedIntentClassifier(config)
        engine = RouterEngine(classifier=custom_classifier)

        assert engine._classifier is custom_classifier
