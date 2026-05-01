---
applyTo: "**/*.py"
description: "Python implementation rules for EAR router, registry, CLI, MCP transport, and testability."
---

# Python Router Instructions

## Architecture
- Keep modules focused:
  - router engine: decision policy and scoring
  - registry: model metadata retrieval and caching
  - CLI and MCP: transport and I/O only
- Do not call external providers directly from CLI or MCP handlers; delegate to services.

## Typing and Models
- Use strict type hints for all public functions and methods.
- Use Pydantic v2 models for external payloads, configuration, and tool inputs/outputs.
- Prefer immutable domain objects where possible.

## Async and I/O
- Use asyncio-native patterns.
- Use httpx.AsyncClient with explicit timeout and retry policy wrappers.
- Never block the event loop with synchronous network calls.

## Reliability and Fallback
- Route decisions must include an ordered fallback chain.
- Handle provider errors explicitly (429, timeout, 5xx, malformed JSON).
- Surface failure reasons with actionable messages.

## Security
- Add prompt-injection and unsafe-content prechecks before routing.
- Enforce PII safeguards before sending any prompt to external models.
- Avoid logging secrets or full user prompts in plaintext.

## Testing
- Add or update tests for every logic branch.
- Include tests for empty input, oversize input, code-detection branches, and API failure cases.
- Keep tests deterministic by mocking external dependencies.
