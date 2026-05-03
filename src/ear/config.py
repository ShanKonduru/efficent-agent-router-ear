"""EAR configuration — loads settings from environment variables."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EARConfig(BaseSettings):
    """All runtime configuration for Efficient Agent Router.

    Values are loaded from environment variables or a .env file.
    Missing required fields cause a fast-fail at startup.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openrouter_api_key: str = Field(
        ...,
        description="OpenRouter API key — required for metadata and routing calls.",
    )

    ear_openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL for the OpenRouter API.",
    )

    ear_registry_ttl_seconds: int = Field(
        default=300,
        ge=1,
        description="Seconds before the cached model list is refreshed.",
    )

    ear_default_budget: str = Field(
        default="medium",
        description="Default budget priority: low | medium | high.",
    )

    ear_max_retries: int = Field(
        default=3,
        ge=1,
        description="Maximum retry attempts per model before cascading.",
    )

    ear_request_timeout_seconds: int = Field(
        default=30,
        ge=1,
        description="HTTP timeout in seconds for all outbound requests.",
    )

    ear_ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for the local Ollama API.",
    )

    ear_ollama_enabled: bool = Field(
        default=False,
        description="Enable Ollama as a private provider for sensitive and blocked prompts.",
    )

    ear_judge_enabled: bool = Field(
        default=False,
        description="Enable judge-based routing using a local LLM to make intelligent routing decisions.",
    )

    ear_judge_model: str = Field(
        default="llama3.2",
        description="Ollama model ID to use as the routing judge (e.g., 'llama3.2', 'mistral').",
    )

    ear_judge_confidence_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for judge decisions. Below this, fall back to heuristics.",
    )


def get_config() -> EARConfig:
    """Return a validated EARConfig loaded from the environment."""
    return EARConfig()  # type: ignore[call-arg]
