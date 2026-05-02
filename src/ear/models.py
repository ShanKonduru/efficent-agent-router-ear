"""EAR domain models — typed data structures used across all layers."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskType(str, Enum):
    """Supported task classification types."""

    SIMPLE = "simple"
    PLANNING = "planning"
    CODING = "coding"
    RESEARCH = "research"


class BudgetPriority(str, Enum):
    """Budget priority levels controlling cost vs quality tradeoff."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ControllerHint(BaseModel):
    """Strict mini-controller hint payload used to guide deterministic routing."""

    model_config = ConfigDict(extra="forbid")

    task_type: Optional[TaskType] = Field(
        default=None,
        description="Optional task-type hint from mini-controller.",
    )
    preferred_model: Optional[str] = Field(
        default=None,
        description="Optional preferred model ID hint.",
    )
    allowed_models: list[str] = Field(
        default_factory=list,
        description="Optional allow-list for candidate models.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for the hint payload.",
    )

    @field_validator("preferred_model")
    @classmethod
    def preferred_model_must_not_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("ControllerHint.preferred_model must not be blank.")
        return value

    @field_validator("allowed_models")
    @classmethod
    def allowed_models_must_not_contain_blanks(cls, value: list[str]) -> list[str]:
        if any(not model_id.strip() for model_id in value):
            raise ValueError("ControllerHint.allowed_models must not contain blank model IDs.")
        return value


class LLMPricing(BaseModel):
    """Per-token pricing for a model (costs in USD per token)."""

    prompt: float = Field(..., ge=0, description="Cost per prompt token in USD.")
    completion: float = Field(..., ge=0, description="Cost per completion token in USD.")


class LLMSpec(BaseModel):
    """Specification for a single LLM available via OpenRouter."""

    id: str = Field(..., description="OpenRouter model identifier.")
    name: Optional[str] = Field(default=None, description="Human-readable model name.")
    context_length: int = Field(..., gt=0, description="Maximum context window in tokens.")
    pricing: Optional[LLMPricing] = Field(default=None, description="Pricing data if available.")

    @field_validator("id")
    @classmethod
    def id_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("LLMSpec.id must not be blank.")
        return v


class RoutingRequest(BaseModel):
    """Incoming routing request from a CLI call or MCP tool invocation."""

    prompt: str = Field(..., description="The user prompt to route.")
    task_type: Optional[TaskType] = Field(
        default=None,
        description="Explicit task type hint; auto-classified if omitted.",
    )
    budget_priority: BudgetPriority = Field(
        default=BudgetPriority.MEDIUM,
        description="Desired cost vs quality tradeoff.",
    )
    controller_hint: Optional[ControllerHint] = Field(
        default=None,
        description="Optional mini-controller hint payload.",
    )

    @field_validator("prompt")
    @classmethod
    def prompt_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("RoutingRequest.prompt must not be blank.")
        return v


class RoutingDecision(BaseModel):
    """Outcome of the routing engine's candidate evaluation."""

    selected_model: str = Field(..., description="Model ID chosen for this request.")
    fallback_chain: list[str] = Field(
        default_factory=list,
        description="Ordered list of fallback model IDs if the primary fails.",
    )
    task_type: TaskType = Field(..., description="Resolved task classification.")
    suitability_score: float = Field(..., description="Score of the selected model.")
    reason: str = Field(..., description="Human-readable routing rationale.")


class GuardrailResult(BaseModel):
    """Result of the safety precheck before routing."""

    passed: bool = Field(..., description="True if the prompt is safe to route.")
    injection_detected: bool = Field(default=False)
    pii_detected: bool = Field(default=False)
    reason: Optional[str] = Field(default=None, description="Explanation if not passed.")
    reason_codes: list[str] = Field(
        default_factory=list,
        description="Machine-readable policy reason codes.",
    )
    risk_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Semantic injection risk score in [0, 1].",
    )


class RouteMetric(BaseModel):
    """Per-call metric captured after a routing decision."""

    model_id: str
    latency_ms: float = Field(..., ge=0)
    estimated_cost_usd: float = Field(..., ge=0)
    task_type: TaskType
    success: bool
    prompt_tokens: int = Field(default=0, ge=0, description="Prompt tokens used (0 if route-only).")
    completion_tokens: int = Field(default=0, ge=0, description="Completion tokens used (0 if route-only).")
    fallback_attempts: int = Field(default=0, ge=0, description="Number of fallback candidates tried before success.")


class SessionSummary(BaseModel):
    """Aggregated metrics for the current session."""

    total_calls: int = Field(default=0, ge=0)
    total_cost_usd: float = Field(default=0.0, ge=0)
    total_latency_ms: float = Field(default=0.0, ge=0)
    calls_by_model: dict[str, int] = Field(default_factory=dict)


class ExecutionResponse(BaseModel):
    """Raw response from executing a prompt against a model provider."""

    model: str = Field(..., description="Model ID that produced the response.")
    content: str = Field(..., description="Generated text content.")
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class ExecutionResult(BaseModel):
    """Full result of a route-and-execute operation."""

    decision: RoutingDecision = Field(..., description="Routing decision made before execution.")
    response: ExecutionResponse = Field(..., description="Response from the chosen model.")
    fallback_trace: list[str] = Field(
        default_factory=list,
        description="Ordered list of model IDs attempted (including the successful one).",
    )
    end_to_end_latency_ms: float = Field(..., ge=0, description="Wall-clock time from request to response.")
    estimated_cost_usd: float = Field(..., ge=0, description="Estimated cost based on token usage and pricing.")
    guardrail_result: GuardrailResult = Field(..., description="Safety check outcome.")
