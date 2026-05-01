# EAR Engineering Instructions

This repository builds Efficient Agent Router (EAR): a Python CLI and MCP server that routes tasks to the best LLM under quality, latency, cost, and safety constraints.

## Core Principles
- Keep strict separation of concerns: transport layer (CLI and MCP) must not contain routing heuristics.
- Favor deterministic, testable routing rules first; add learned routing as an extension point.
- Optimize for token efficiency without reducing safety posture.
- Treat security as a first-class acceptance criterion.

## Technology Defaults
- Python: 3.12+
- Async: asyncio
- CLI: Typer
- Validation and config: Pydantic v2
- HTTP client: httpx (async)
- Testing: pytest, pytest-asyncio, pytest-cov

## Quality Gates
- 100% unit test statement and branch coverage for routing and decision logic.
- Fail closed for malformed inputs or untrusted model metadata.
- Implement cascade fallback on transient model failures (429, 5xx, timeout).
- No PII may be routed to unvetted providers.

## Project Conventions
- Prefer small pure functions for scoring and rule evaluation.
- Use explicit domain models for model specs, routing requests, and routing outcomes.
- Log decision reasons in structured form for debuggability.
- Never store secrets in source code; load from environment configuration.
