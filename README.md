# Efficient Agent Router (EAR)

Efficient Agent Router (EAR) is a Python-first orchestration service that selects and executes the best LLM for a request based on quality, cost, latency, context window, and safety constraints.

## Goals
- Route each request to the most suitable model for the task.
- Reduce token burn through cost-aware model ranking.
- Protect sensitive input with prompt-injection and PII safeguards.
- Provide a clean CLI first, then expose the same logic through MCP.

## Current Delivery Strategy
1. Build and validate core routing engine through CLI.
2. Harden reliability, guardrails, and observability.
3. Expose stable capabilities through MCP server.

## Tech Stack
- Python 3.12+
- asyncio
- Typer CLI
- Pydantic v2
- httpx for OpenRouter model metadata
- pytest, pytest-asyncio, pytest-cov
- bandit and pip-audit for security controls

## Planned Repository Layout
- docs/
  - system_prompt.md
  - execution_plan.md
  - adr/
- src/
  - ear/
    - router_engine.py
    - registry.py
    - guardrails.py
    - fallback.py
    - metrics.py
    - cli.py
    - mcp_server.py
- tests/
  - test_registry.py
  - test_router_engine.py
  - test_guardrails.py
  - test_fallback.py
  - test_cli.py
  - test_mcp_server.py

## Core Workflow
1. Accept user task input and options (task hint, budget priority, context profile).
2. Run safety prechecks (injection and PII policy).
3. Load model metadata from OpenRouter registry cache.
4. Compute suitability score and candidate ranking.
5. Execute via selected model and apply cascade fallback if needed.
6. Return result with routing rationale and metric snapshot.

## Routing Model
The router evaluates candidate models using a weighted suitability function:

S = Quality / (Cost * Latency)

Where score inputs are normalized and constrained by policy:
- Context window threshold
- Budget priority
- Safety allowlist and PII policy
- Task-specific boosts (coding, planning, research)

## CLI Design (Phase 1)
Expected commands:
- ear route "<prompt>" --task coding --budget medium
- ear inspect-models
- ear stats --session

Expected output modes:
- Human-readable summary
- JSON output for scripting pipelines

## MCP Design (Phase 2)
- Tool: route_and_execute
- Resources: model performance metrics, cost per session
- Transport: stdio first, optional SSE extension

## Configuration
Environment variables (minimum):
- OPENROUTER_API_KEY
- EAR_REGISTRY_TTL_SECONDS
- EAR_DEFAULT_BUDGET
- EAR_MAX_RETRIES

Recommended local setup steps:
1. Create and activate virtual environment.
2. Install dependencies.
3. Populate .env with OPENROUTER_API_KEY.
4. Run tests and quality checks before first run.

## Quality and Security Requirements
- 100% statement and branch coverage for routing core.
- Deterministic tests with mocked external dependencies.
- Security linting with bandit.
- Dependency auditing with pip-audit.
- No plaintext secret logging.

## Milestones
- M1: Registry and schema baseline
- M2: Router core and CLI
- M3: Guardrails and metrics
- M4: MCP server and CI/CD gates

## Contributing Expectations
- Preserve clean architecture boundaries.
- Add tests for every logic branch touched.
- Update ADRs when making architecture-affecting decisions.
- Keep operational docs current with behavior changes.
