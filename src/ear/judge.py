"""Judge-based routing — uses a local LLM to decide local vs cloud routing.

The Judge pattern:
1. Sends the user prompt to a lightweight local Ollama model (e.g., llama3.2, mistral)
2. The judge analyzes: complexity, privacy sensitivity, quality requirements, etc.
3. Returns a structured decision: prefer_local, confidence, reasoning
4. Falls back to heuristic routing on judge failure (timeout, error, unavailable)

This provides adaptive, intelligent routing while maintaining deterministic fallback.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from ear.config import EARConfig
from ear.models import BudgetPriority, TaskType

logger = logging.getLogger(__name__)


class JudgeDecision(BaseModel):
    """Routing decision made by the judge LLM."""

    prefer_local: bool = Field(
        ...,
        description="True if the prompt should be routed to local Ollama, False for cloud LLM.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this decision (0.0 to 1.0).",
    )
    reasoning: str = Field(
        ...,
        description="Human-readable explanation of the routing decision.",
    )
    complexity_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Estimated task complexity (0=simple, 1=very complex).",
    )
    privacy_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Privacy sensitivity detected (0=none, 1=highly sensitive).",
    )
    quality_requirement: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Quality requirement level (0=draft ok, 1=expert quality needed).",
    )


class JudgeRoutingClassifier:
    """Uses a local LLM judge to make intelligent local vs cloud routing decisions.

    The judge model receives a structured prompt asking it to analyze the user's
    question and return a JSON decision about whether to route locally or to cloud.

    Features:
    - Adaptive, context-aware routing decisions
    - No latency/cost for judge calls (runs locally)
    - Deterministic fallback if judge is unavailable or fails
    - Can be fine-tuned over time with specialized judge models
    """

    _JUDGE_SYSTEM_PROMPT = """You are an intelligent routing judge for an LLM router system.
Your job is to analyze user prompts and decide whether they should be processed by:
- LOCAL: A local Ollama model (fast, private, free, but less capable)
- CLOUD: A cloud-based LLM (slower, costs money, but more powerful and knowledgeable)

Analyze the prompt and return a JSON decision with these factors:

**Use LOCAL when:**
- Simple questions, casual chat, basic information retrieval
- Privacy-sensitive content (PII, personal data, confidential info)
- Tasks where speed matters more than perfection
- Draft generation, brainstorming, simple formatting
- Cost is a major concern
- Simple code completion or syntax help

**Use CLOUD when:**
- Complex reasoning, multi-step problem solving
- Specialized domain knowledge required (legal, medical, scientific)
- High accuracy/quality is critical
- Creative writing requiring expert-level output
- Complex code architecture or system design
- Large context that needs deep understanding
- Research synthesis from multiple domains

Return ONLY valid JSON with this exact structure:
{
  "prefer_local": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "brief explanation",
  "complexity_score": 0.0 to 1.0,
  "privacy_score": 0.0 to 1.0,
  "quality_requirement": 0.0 to 1.0
}"""

    def __init__(
        self,
        config: EARConfig,
        judge_model: str = "llama3.2",
        fallback_to_heuristic: bool = True,
    ) -> None:
        """Initialize the judge routing classifier.

        Args:
            config: EAR configuration with Ollama base URL and settings.
            judge_model: Ollama model ID to use as judge (default: llama3.2).
                        Should be a lightweight, fast model.
            fallback_to_heuristic: If True, fall back to heuristic routing on judge failure.
        """
        self._config = config
        self._judge_model = judge_model
        self._fallback_to_heuristic = fallback_to_heuristic
        self._ollama_base_url = config.ear_ollama_base_url.rstrip("/")
        self._timeout_seconds = min(config.ear_request_timeout_seconds, 10)  # Cap judge timeout
        self._client = httpx.AsyncClient(timeout=self._timeout_seconds)

    async def decide(
        self,
        prompt: str,
        task_type: TaskType | None = None,
        budget_priority: BudgetPriority = BudgetPriority.MEDIUM,
    ) -> JudgeDecision:
        """Ask the judge LLM to make a routing decision.

        Args:
            prompt: The user's prompt to analyze.
            task_type: Optional task type hint to provide context to judge.
            budget_priority: Budget priority from the routing request.

        Returns:
            JudgeDecision with prefer_local, confidence, and reasoning.

        Raises:
            RuntimeError: If judge fails and fallback is disabled.
        """
        try:
            # Build the judge prompt with context
            judge_prompt = self._build_judge_prompt(prompt, task_type, budget_priority)

            # Call local Ollama judge model
            decision_json = await self._call_judge(judge_prompt)

            # Parse and validate the decision
            decision = self._parse_judge_response(decision_json)

            logger.info(
                "Judge routing decision: prefer_local=%s confidence=%.2f reasoning=%s",
                decision.prefer_local,
                decision.confidence,
                decision.reasoning,
            )
            return decision

        except Exception as e:
            logger.warning("Judge routing failed: %s. Using fallback strategy.", e)

            if not self._fallback_to_heuristic:
                raise RuntimeError(f"Judge routing failed and fallback is disabled: {e}") from e

            # Fallback to heuristic decision
            return self._heuristic_fallback(prompt, budget_priority)

    def _build_judge_prompt(
        self,
        prompt: str,
        task_type: TaskType | None,
        budget_priority: BudgetPriority,
    ) -> str:
        """Build the structured prompt for the judge model."""
        context_parts = []

        if task_type:
            context_parts.append(f"Task Type: {task_type.value}")

        context_parts.append(f"Budget Priority: {budget_priority.value}")

        context_section = "\n".join(context_parts) if context_parts else "No additional context."

        # Truncate very long prompts to avoid judge timeout
        prompt_excerpt = prompt[:1000] + ("..." if len(prompt) > 1000 else "")

        return f"""Context about this routing request:
{context_section}

User Prompt to Analyze:
\"\"\"
{prompt_excerpt}
\"\"\"

Analyze this prompt and return your routing decision as JSON."""

    async def _call_judge(self, judge_prompt: str) -> dict[str, Any]:
        """Call the local Ollama judge model and return raw JSON response."""
        url = f"{self._ollama_base_url}/api/chat"

        payload = {
            "model": self._judge_model,
            "messages": [
                {"role": "system", "content": self._JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": judge_prompt},
            ],
            "stream": False,
            "format": "json",  # Request JSON response from Ollama
            "options": {
                "temperature": 0.1,  # Low temperature for consistent decisions
                "num_predict": 256,  # Limit tokens for faster response
            },
        }

        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

            # Ollama returns message in result['message']['content']
            content = result.get("message", {}).get("content", "")
            if not content:
                raise ValueError("Empty response from judge model")

            return json.loads(content)

        except httpx.TimeoutException as e:
            raise RuntimeError(f"Judge model timeout after {self._timeout_seconds}s") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Judge model HTTP error: {e.response.status_code}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Judge model returned invalid JSON: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Judge model call failed: {e}") from e

    def _parse_judge_response(self, response_json: dict[str, Any]) -> JudgeDecision:
        """Parse and validate the judge's JSON response into a JudgeDecision."""
        try:
            return JudgeDecision(**response_json)
        except Exception as e:
            raise ValueError(f"Invalid judge response format: {e}") from e

    def _heuristic_fallback(
        self,
        prompt: str,
        budget_priority: BudgetPriority,
    ) -> JudgeDecision:
        """Deterministic fallback when judge is unavailable or fails.

        Simple heuristics:
        - LOW budget priority → prefer local (cost-sensitive)
        - Very short prompts (< 50 chars) → prefer local (likely simple)
        - Very long prompts (> 5000 chars) → prefer cloud (needs context)
        - Default → prefer based on budget
        """
        prompt_len = len(prompt)

        # Simple/short queries → local
        if prompt_len < 50:
            return JudgeDecision(
                prefer_local=True,
                confidence=0.7,
                reasoning="Heuristic fallback: short prompt suggests simple query",
                complexity_score=0.2,
                privacy_score=0.0,
                quality_requirement=0.3,
            )

        # Very long context → cloud
        if prompt_len > 5000:
            return JudgeDecision(
                prefer_local=False,
                confidence=0.7,
                reasoning="Heuristic fallback: long prompt needs cloud context handling",
                complexity_score=0.8,
                privacy_score=0.0,
                quality_requirement=0.7,
            )

        # Budget-driven default
        prefer_local = budget_priority == BudgetPriority.LOW
        return JudgeDecision(
            prefer_local=prefer_local,
            confidence=0.5,
            reasoning=f"Heuristic fallback: budget priority {budget_priority.value}",
            complexity_score=0.5,
            privacy_score=0.0,
            quality_requirement=0.5,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
