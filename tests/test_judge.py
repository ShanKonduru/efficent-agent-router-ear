"""Tests for ear.judge — judge-based routing with local LLM decision-making.

Coverage targets:
- JudgeDecision model validation
- JudgeRoutingClassifier.decide() with successful judge responses
- Judge failure and fallback to heuristics
- Integration with orchestrator candidate filtering
- Edge cases: timeout, invalid JSON, malformed responses
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ear.config import EARConfig
from ear.judge import JudgeDecision, JudgeRoutingClassifier
from ear.models import BudgetPriority, TaskType


# ---------------------------------------------------------------------------
# JudgeDecision Model Tests
# ---------------------------------------------------------------------------

class TestJudgeDecision:
    """Test JudgeDecision model validation."""

    def test_valid_decision_prefer_local(self):
        """Valid decision preferring local routing."""
        decision = JudgeDecision(
            prefer_local=True,
            confidence=0.9,
            reasoning="Simple query, local is sufficient",
            complexity_score=0.2,
            privacy_score=0.0,
            quality_requirement=0.3,
        )
        assert decision.prefer_local is True
        assert decision.confidence == 0.9
        assert "Simple query" in decision.reasoning

    def test_valid_decision_prefer_cloud(self):
        """Valid decision preferring cloud routing."""
        decision = JudgeDecision(
            prefer_local=False,
            confidence=0.85,
            reasoning="Complex research task needs cloud capabilities",
            complexity_score=0.9,
            privacy_score=0.0,
            quality_requirement=0.8,
        )
        assert decision.prefer_local is False
        assert decision.complexity_score == 0.9

    def test_confidence_must_be_in_range(self):
        """Confidence must be between 0.0 and 1.0."""
        with pytest.raises(ValueError, match="confidence"):
            JudgeDecision(
                prefer_local=True,
                confidence=1.5,  # Invalid
                reasoning="test",
            )

    def test_default_scores(self):
        """Default scores are applied when not provided."""
        decision = JudgeDecision(
            prefer_local=True,
            confidence=0.7,
            reasoning="test",
        )
        assert decision.complexity_score == 0.5
        assert decision.privacy_score == 0.0
        assert decision.quality_requirement == 0.5


# ---------------------------------------------------------------------------
# JudgeRoutingClassifier Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config() -> EARConfig:
    """Mock EAR configuration for testing."""
    return EARConfig(
        openrouter_api_key="test-key",
        ear_ollama_base_url="http://localhost:11434",
        ear_request_timeout_seconds=30,
        ear_judge_enabled=True,
        ear_judge_model="llama3.2",
        ear_judge_confidence_threshold=0.6,
    )


class TestJudgeRoutingClassifier:
    """Test JudgeRoutingClassifier decision logic."""

    @pytest.mark.asyncio
    async def test_judge_decides_prefer_local_for_simple_query(self, mock_config: EARConfig):
        """Judge decides to prefer local for simple queries."""
        judge = JudgeRoutingClassifier(mock_config)

        # Mock the Ollama API response
        mock_response = {
            "prefer_local": True,
            "confidence": 0.9,
            "reasoning": "Simple greeting, local model sufficient",
            "complexity_score": 0.1,
            "privacy_score": 0.0,
            "quality_requirement": 0.2,
        }

        with patch.object(judge, "_call_judge", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            decision = await judge.decide("Hello, how are you?")

            assert decision.prefer_local is True
            assert decision.confidence == 0.9
            assert "Simple greeting" in decision.reasoning

    @pytest.mark.asyncio
    async def test_judge_decides_prefer_cloud_for_complex_task(self, mock_config: EARConfig):
        """Judge decides to prefer cloud for complex research tasks."""
        judge = JudgeRoutingClassifier(mock_config)

        mock_response = {
            "prefer_local": False,
            "confidence": 0.95,
            "reasoning": "Complex legal analysis requires expert knowledge",
            "complexity_score": 0.95,
            "privacy_score": 0.0,
            "quality_requirement": 0.9,
        }

        with patch.object(judge, "_call_judge", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            decision = await judge.decide(
                "Analyze the implications of GDPR Article 17 on data retention policies",
                task_type=TaskType.RESEARCH,
            )

            assert decision.prefer_local is False
            assert decision.confidence == 0.95
            assert decision.complexity_score == 0.95

    @pytest.mark.asyncio
    async def test_judge_considers_budget_priority(self, mock_config: EARConfig):
        """Judge receives and considers budget priority in context."""
        judge = JudgeRoutingClassifier(mock_config)

        mock_response = {
            "prefer_local": True,
            "confidence": 0.8,
            "reasoning": "Low budget priority favors local execution",
            "complexity_score": 0.5,
            "privacy_score": 0.0,
            "quality_requirement": 0.4,
        }

        with patch.object(judge, "_call_judge", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            decision = await judge.decide(
                "Generate a draft blog post about Python",
                budget_priority=BudgetPriority.LOW,
            )

            assert decision.prefer_local is True
            # Verify budget priority was passed in the prompt
            call_args = mock_call.call_args[0][0]
            assert "Budget Priority: low" in call_args

    @pytest.mark.asyncio
    async def test_judge_fallback_on_timeout(self, mock_config: EARConfig):
        """Judge falls back to heuristics on timeout."""
        judge = JudgeRoutingClassifier(mock_config, fallback_to_heuristic=True)

        with patch.object(judge, "_call_judge", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = RuntimeError("Judge model timeout after 10s")

            decision = await judge.decide("What is the capital of France?")

            # Should fall back to heuristic
            assert isinstance(decision, JudgeDecision)
            assert "Heuristic fallback" in decision.reasoning

    @pytest.mark.asyncio
    async def test_judge_fallback_on_invalid_json(self, mock_config: EARConfig):
        """Judge falls back to heuristics on invalid JSON response."""
        judge = JudgeRoutingClassifier(mock_config, fallback_to_heuristic=True)

        with patch.object(judge, "_call_judge", new_callable=AsyncMock) as mock_call:
            # Return malformed JSON
            mock_call.return_value = {"invalid": "response"}

            with patch.object(judge, "_parse_judge_response") as mock_parse:
                mock_parse.side_effect = ValueError("Invalid judge response format")

                decision = await judge.decide("Test prompt")

                assert isinstance(decision, JudgeDecision)
                assert "Heuristic fallback" in decision.reasoning

    @pytest.mark.asyncio
    async def test_judge_raises_error_when_fallback_disabled(self, mock_config: EARConfig):
        """Judge raises error when fallback is disabled and judge fails."""
        judge = JudgeRoutingClassifier(mock_config, fallback_to_heuristic=False)

        with patch.object(judge, "_call_judge", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = RuntimeError("Judge failed")

            with pytest.raises(RuntimeError, match="fallback is disabled"):
                await judge.decide("Test prompt")

    @pytest.mark.asyncio
    async def test_heuristic_fallback_short_prompt(self, mock_config: EARConfig):
        """Heuristic fallback prefers local for short prompts."""
        judge = JudgeRoutingClassifier(mock_config)

        decision = judge._heuristic_fallback("Hi", BudgetPriority.MEDIUM)

        assert decision.prefer_local is True
        assert "short prompt" in decision.reasoning.lower()

    @pytest.mark.asyncio
    async def test_heuristic_fallback_long_prompt(self, mock_config: EARConfig):
        """Heuristic fallback prefers cloud for very long prompts."""
        judge = JudgeRoutingClassifier(mock_config)

        long_prompt = "a" * 6000  # > 5000 chars
        decision = judge._heuristic_fallback(long_prompt, BudgetPriority.MEDIUM)

        assert decision.prefer_local is False
        assert "long prompt" in decision.reasoning.lower()

    @pytest.mark.asyncio
    async def test_heuristic_fallback_low_budget(self, mock_config: EARConfig):
        """Heuristic fallback prefers local for low budget priority."""
        judge = JudgeRoutingClassifier(mock_config)

        # Use a medium-length prompt (between 50 and 5000 chars)
        medium_prompt = "This is a medium length prompt that should trigger budget-based routing. " * 5
        decision = judge._heuristic_fallback(medium_prompt, BudgetPriority.LOW)

        assert decision.prefer_local is True
        assert "low" in decision.reasoning.lower()

    @pytest.mark.asyncio
    async def test_heuristic_fallback_high_budget(self, mock_config: EARConfig):
        """Heuristic fallback allows cloud for high budget priority."""
        judge = JudgeRoutingClassifier(mock_config)

        # Use a medium-length prompt (between 50 and 5000 chars)
        medium_prompt = "This is a medium length prompt that should trigger budget-based routing. " * 5
        decision = judge._heuristic_fallback(medium_prompt, BudgetPriority.HIGH)

        assert decision.prefer_local is False


# ---------------------------------------------------------------------------
# Integration with Orchestrator
# ---------------------------------------------------------------------------

class TestJudgeOrchestrationIntegration:
    """Test judge integration with ExecutionOrchestrator."""

    @pytest.mark.asyncio
    async def test_orchestrator_uses_judge_for_candidate_filtering(self, mock_config: EARConfig):
        """Orchestrator uses judge to filter candidates when no security concerns exist."""
        from ear.models import LLMSpec, RoutingRequest
        from ear.orchestrator import ExecutionOrchestrator

        ollama_model = LLMSpec(id="ollama/llama3", name="llama3", context_length=8_192, trusted=True)
        cloud_model = LLMSpec(id="openai/gpt-4o-mini", name="mini", context_length=16_000)
        models = [ollama_model, cloud_model]

        # Mock judge to prefer local
        mock_judge = MagicMock(spec=JudgeRoutingClassifier)
        mock_judge.decide = AsyncMock(
            return_value=JudgeDecision(
                prefer_local=True,
                confidence=0.9,
                reasoning="Simple task, local preferred",
            )
        )

        # Setup orchestrator with mocked components
        from ear.guardrails import GuardrailsChecker
        from ear.metrics import get_metrics_collector
        from ear.router_engine import RouterEngine
        from unittest.mock import Mock

        mock_pipeline = Mock()
        mock_pipeline.execute = AsyncMock()

        orch = ExecutionOrchestrator(
            guardrails=GuardrailsChecker(),
            router=RouterEngine(),
            pipeline=mock_pipeline,
            metrics=get_metrics_collector(),
            judge=mock_judge,
        )

        request = RoutingRequest(prompt="Hello, how are you?", budget_priority=BudgetPriority.MEDIUM)

        # Mock the execution to avoid real API calls
        from ear.fallback import FallbackResult, FallbackAttempt
        from ear.models import ExecutionResponse

        mock_pipeline.execute.return_value = FallbackResult(
            response=ExecutionResponse(
                model="ollama/llama3",
                content="I'm doing well, thanks!",
                prompt_tokens=10,
                completion_tokens=15,
                total_tokens=25,
            ),
            model_used="ollama/llama3",
            attempts=[],
        )

        # Call the orchestrator
        candidates = await orch._determine_candidates_via_judge(request, models, [ollama_model])

        # Verify judge was consulted
        mock_judge.decide.assert_called_once()

        # Verify only Ollama models returned when judge prefers local
        assert len(candidates) == 1
        assert candidates[0].id == "ollama/llama3"

    @pytest.mark.asyncio
    async def test_orchestrator_falls_back_when_judge_confidence_low(self, mock_config: EARConfig):
        """Orchestrator uses all models when judge confidence is below threshold."""
        from ear.models import LLMSpec, RoutingRequest
        from ear.orchestrator import ExecutionOrchestrator
        from ear.guardrails import GuardrailsChecker
        from ear.metrics import get_metrics_collector
        from ear.router_engine import RouterEngine
        from unittest.mock import Mock

        ollama_model = LLMSpec(id="ollama/llama3", name="llama3", context_length=8_192, trusted=True)
        cloud_model = LLMSpec(id="openai/gpt-4o-mini", name="mini", context_length=16_000)
        models = [ollama_model, cloud_model]

        # Mock judge with LOW confidence
        mock_judge = MagicMock(spec=JudgeRoutingClassifier)
        mock_judge.decide = AsyncMock(
            return_value=JudgeDecision(
                prefer_local=True,
                confidence=0.3,  # Below threshold (0.6)
                reasoning="Not confident in this decision",
            )
        )

        mock_pipeline = Mock()
        orch = ExecutionOrchestrator(
            guardrails=GuardrailsChecker(),
            router=RouterEngine(),
            pipeline=mock_pipeline,
            metrics=get_metrics_collector(),
            judge=mock_judge,
        )

        request = RoutingRequest(prompt="Ambiguous query", budget_priority=BudgetPriority.MEDIUM)

        candidates = await orch._determine_candidates_via_judge(request, models, [ollama_model])

        # Should use ALL models when confidence is low
        assert len(candidates) == 2
        assert ollama_model in candidates
        assert cloud_model in candidates


# ---------------------------------------------------------------------------
# Judge Prompt Building Tests
# ---------------------------------------------------------------------------

class TestJudgePromptBuilding:
    """Test judge prompt construction."""

    def test_build_judge_prompt_with_context(self, mock_config: EARConfig):
        """Judge prompt includes task type and budget context."""
        judge = JudgeRoutingClassifier(mock_config)

        prompt = judge._build_judge_prompt(
            "Write a function to sort a list",
            task_type=TaskType.CODING,
            budget_priority=BudgetPriority.HIGH,
        )

        assert "Task Type: coding" in prompt
        assert "Budget Priority: high" in prompt
        assert "Write a function to sort a list" in prompt

    def test_build_judge_prompt_truncates_long_prompts(self, mock_config: EARConfig):
        """Judge prompt truncates very long user prompts."""
        judge = JudgeRoutingClassifier(mock_config)

        long_prompt = "a" * 2000  # Very long
        prompt = judge._build_judge_prompt(long_prompt, None, BudgetPriority.MEDIUM)

        # Should be truncated to ~1000 chars plus ellipsis
        assert "..." in prompt
        assert len(prompt) < len(long_prompt) + 500  # Not the full original length


# ---------------------------------------------------------------------------
# HTTP Call and Error Handling Tests
# ---------------------------------------------------------------------------

class TestJudgeHttpCalls:
    """Test judge HTTP call implementation and error handling."""

    @pytest.mark.asyncio
    async def test_call_judge_makes_correct_http_request(self, mock_config: EARConfig):
        """Verify HTTP request is constructed correctly."""
        judge = JudgeRoutingClassifier(mock_config)

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={
            "message": {
                "content": '{"prefer_local": true, "confidence": 0.9, "reasoning": "test"}'
            }
        })
        mock_response.raise_for_status = MagicMock()

        with patch.object(judge._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            result = await judge._call_judge("test prompt")

            # Verify the HTTP call was made correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == f"{mock_config.ear_ollama_base_url}/api/chat"
            payload = call_args[1]["json"]
            assert payload["model"] == "llama3.2"
            assert payload["format"] == "json"
            assert payload["stream"] is False

    @pytest.mark.asyncio
    async def test_call_judge_raises_on_empty_content(self, mock_config: EARConfig):
        """Judge raises error when response content is empty."""
        judge = JudgeRoutingClassifier(mock_config)

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={"message": {"content": ""}})
        mock_response.raise_for_status = MagicMock()

        with patch.object(judge._client, "post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(RuntimeError, match="Empty response from judge model"):
                await judge._call_judge("test prompt")

    @pytest.mark.asyncio
    async def test_call_judge_raises_on_timeout(self, mock_config: EARConfig):
        """Judge raises RuntimeError on timeout."""
        judge = JudgeRoutingClassifier(mock_config)

        with patch.object(judge._client, "post", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(RuntimeError, match="Judge model timeout after"):
                await judge._call_judge("test prompt")

    @pytest.mark.asyncio
    async def test_call_judge_raises_on_http_error(self, mock_config: EARConfig):
        """Judge raises RuntimeError on HTTP error."""
        judge = JudgeRoutingClassifier(mock_config)

        mock_response = MagicMock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError("error", request=MagicMock(), response=mock_response)

        with patch.object(judge._client, "post", new_callable=AsyncMock, side_effect=error):
            with pytest.raises(RuntimeError, match="Judge model HTTP error: 500"):
                await judge._call_judge("test prompt")

    @pytest.mark.asyncio
    async def test_call_judge_raises_on_invalid_json(self, mock_config: EARConfig):
        """Judge raises RuntimeError when response is invalid JSON."""
        judge = JudgeRoutingClassifier(mock_config)

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={"message": {"content": "not valid json {"}})
        mock_response.raise_for_status = MagicMock()

        with patch.object(judge._client, "post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(RuntimeError, match="Judge model returned invalid JSON"):
                await judge._call_judge("test prompt")

    @pytest.mark.asyncio
    async def test_call_judge_raises_on_generic_exception(self, mock_config: EARConfig):
        """Judge raises RuntimeError on unexpected exceptions."""
        judge = JudgeRoutingClassifier(mock_config)

        with patch.object(judge._client, "post", new_callable=AsyncMock, side_effect=Exception("unexpected error")):
            with pytest.raises(RuntimeError, match="Judge model call failed"):
                await judge._call_judge("test prompt")

    @pytest.mark.asyncio
    async def test_parse_judge_response_raises_on_invalid_format(self, mock_config: EARConfig):
        """Parse raises ValueError when response doesn't match JudgeDecision schema."""
        judge = JudgeRoutingClassifier(mock_config)

        invalid_response = {"invalid": "data", "missing": "required fields"}

        with pytest.raises(ValueError, match="Invalid judge response format"):
            judge._parse_judge_response(invalid_response)

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self, mock_config: EARConfig):
        """Close method closes the HTTP client."""
        judge = JudgeRoutingClassifier(mock_config)

        with patch.object(judge._client, "aclose", new_callable=AsyncMock) as mock_close:
            await judge.close()
            mock_close.assert_called_once()


# ---------------------------------------------------------------------------
# Orchestrator Edge Cases with Judge
# ---------------------------------------------------------------------------

class TestOrchestratorJudgeEdgeCases:
    """Test edge cases in orchestrator judge integration."""

    @pytest.mark.asyncio
    async def test_orchestrator_warns_when_judge_enabled_without_ollama(self):
        """Orchestrator warns and disables judge when Ollama is not enabled."""
        from ear.orchestrator import ExecutionOrchestrator

        config = EARConfig(
            openrouter_api_key="test-key",
            ear_judge_enabled=True,  # Judge enabled
            ear_ollama_enabled=False,  # But Ollama disabled
        )

        with patch("ear.orchestrator.logger") as mock_logger:
            orch = ExecutionOrchestrator.from_config(config)

            # Should have warned about judge requiring Ollama
            mock_logger.warning.assert_called_once()
            assert "Judge routing requires Ollama" in str(mock_logger.warning.call_args)

            # Judge should not be initialized
            assert orch._judge is None

    @pytest.mark.asyncio
    async def test_orchestrator_with_judge_disabled(self):
        """Orchestrator does not initialize judge when judge is disabled."""
        from ear.orchestrator import ExecutionOrchestrator

        config = EARConfig(
            openrouter_api_key="test-key",
            ear_judge_enabled=False,  # Judge disabled
            ear_ollama_enabled=True,  # Ollama enabled (doesn't matter)
        )

        with patch("ear.orchestrator.logger") as mock_logger:
            orch = ExecutionOrchestrator.from_config(config)

            # Should not have logged anything about judge
            mock_logger.info.assert_not_called()
            mock_logger.warning.assert_not_called()

            # Judge should not be initialized
            assert orch._judge is None

    @pytest.mark.asyncio
    async def test_judge_recommends_local_but_no_ollama_available(self, mock_config: EARConfig):
        """When judge prefers local but no Ollama models exist, fall back to cloud."""
        from ear.models import LLMSpec, RoutingRequest
        from ear.orchestrator import ExecutionOrchestrator
        from ear.guardrails import GuardrailsChecker
        from ear.metrics import get_metrics_collector
        from ear.router_engine import RouterEngine
        from unittest.mock import Mock

        cloud_model = LLMSpec(id="openai/gpt-4o-mini", name="mini", context_length=16_000)
        models = [cloud_model]  # No Ollama models

        mock_judge = MagicMock(spec=JudgeRoutingClassifier)
        mock_judge.decide = AsyncMock(
            return_value=JudgeDecision(
                prefer_local=True,
                confidence=0.9,
                reasoning="Prefer local",
            )
        )

        mock_pipeline = Mock()
        orch = ExecutionOrchestrator(
            guardrails=GuardrailsChecker(),
            router=RouterEngine(),
            pipeline=mock_pipeline,
            metrics=get_metrics_collector(),
            judge=mock_judge,
        )

        request = RoutingRequest(prompt="Test", budget_priority=BudgetPriority.MEDIUM)

        candidates = await orch._determine_candidates_via_judge(request, models, [])

        # Should fall back to all models (cloud)
        assert len(candidates) == 1
        assert candidates[0].id == "openai/gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_judge_recommends_cloud_but_no_cloud_available(self, mock_config: EARConfig):
        """When judge prefers cloud but only Ollama exists, fall back to Ollama."""
        from ear.models import LLMSpec, RoutingRequest
        from ear.orchestrator import ExecutionOrchestrator
        from ear.guardrails import GuardrailsChecker
        from ear.metrics import get_metrics_collector
        from ear.router_engine import RouterEngine
        from unittest.mock import Mock

        ollama_model = LLMSpec(id="ollama/llama3", name="llama3", context_length=8_192, trusted=True)
        models = [ollama_model]  # Only Ollama models

        mock_judge = MagicMock(spec=JudgeRoutingClassifier)
        mock_judge.decide = AsyncMock(
            return_value=JudgeDecision(
                prefer_local=False,
                confidence=0.9,
                reasoning="Prefer cloud",
            )
        )

        mock_pipeline = Mock()
        orch = ExecutionOrchestrator(
            guardrails=GuardrailsChecker(),
            router=RouterEngine(),
            pipeline=mock_pipeline,
            metrics=get_metrics_collector(),
            judge=mock_judge,
        )

        request = RoutingRequest(prompt="Test", budget_priority=BudgetPriority.MEDIUM)

        candidates = await orch._determine_candidates_via_judge(request, models, [ollama_model])

        # Should fall back to Ollama
        assert len(candidates) == 1
        assert candidates[0].id == "ollama/llama3"

    @pytest.mark.asyncio
    async def test_judge_exception_falls_back_to_all_models(self, mock_config: EARConfig):
        """When judge throws exception, fall back to all available models."""
        from ear.models import LLMSpec, RoutingRequest
        from ear.orchestrator import ExecutionOrchestrator
        from ear.guardrails import GuardrailsChecker
        from ear.metrics import get_metrics_collector
        from ear.router_engine import RouterEngine
        from unittest.mock import Mock

        ollama_model = LLMSpec(id="ollama/llama3", name="llama3", context_length=8_192, trusted=True)
        cloud_model = LLMSpec(id="openai/gpt-4o-mini", name="mini", context_length=16_000)
        models = [ollama_model, cloud_model]

        mock_judge = MagicMock(spec=JudgeRoutingClassifier)
        mock_judge.decide = AsyncMock(side_effect=Exception("Judge failed"))

        mock_pipeline = Mock()
        orch = ExecutionOrchestrator(
            guardrails=GuardrailsChecker(),
            router=RouterEngine(),
            pipeline=mock_pipeline,
            metrics=get_metrics_collector(),
            judge=mock_judge,
        )

        request = RoutingRequest(prompt="Test", budget_priority=BudgetPriority.MEDIUM)

        candidates = await orch._determine_candidates_via_judge(request, models, [ollama_model])

        # Should use all models on exception
        assert len(candidates) == 2

    @pytest.mark.asyncio
    async def test_judge_recommends_cloud_with_cloud_models_available(self, mock_config: EARConfig):
        """When judge prefers cloud and cloud models exist, use cloud models."""
        from ear.models import LLMSpec, RoutingRequest
        from ear.orchestrator import ExecutionOrchestrator
        from ear.guardrails import GuardrailsChecker
        from ear.metrics import get_metrics_collector
        from ear.router_engine import RouterEngine
        from unittest.mock import Mock

        ollama_model = LLMSpec(id="ollama/llama3", name="llama3", context_length=8_192, trusted=True)
        cloud_model = LLMSpec(id="openai/gpt-4o-mini", name="mini", context_length=16_000)
        models = [ollama_model, cloud_model]  # Both types available

        mock_judge = MagicMock(spec=JudgeRoutingClassifier)
        mock_judge.decide = AsyncMock(
            return_value=JudgeDecision(
                prefer_local=False,
                confidence=0.9,
                reasoning="Prefer cloud",
            )
        )

        mock_pipeline = Mock()
        orch = ExecutionOrchestrator(
            guardrails=GuardrailsChecker(),
            router=RouterEngine(),
            pipeline=mock_pipeline,
            metrics=get_metrics_collector(),
            judge=mock_judge,
        )

        request = RoutingRequest(prompt="Test", budget_priority=BudgetPriority.MEDIUM)

        candidates = await orch._determine_candidates_via_judge(request, models, [ollama_model])

        # Should use only cloud models
        assert len(candidates) == 1
        assert candidates[0].id == "openai/gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_orchestrator_initializes_judge_when_both_enabled(self):
        """Orchestrator initializes judge when both judge and Ollama are enabled."""
        from ear.orchestrator import ExecutionOrchestrator

        config = EARConfig(
            openrouter_api_key="test-key",
            ear_judge_enabled=True,
            ear_ollama_enabled=True,
            ear_judge_model="llama3.2",
            ear_judge_confidence_threshold=0.6,
        )

        with patch("ear.orchestrator.logger") as mock_logger:
            orch = ExecutionOrchestrator.from_config(config)

            # Should have logged judge initialization
            mock_logger.info.assert_called_once()
            assert "Judge-based routing enabled" in str(mock_logger.info.call_args)

            # Judge should be initialized
            assert orch._judge is not None
