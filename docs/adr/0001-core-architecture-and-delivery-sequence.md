# ADR 0001: Core Architecture and Delivery Sequence

- Status: Accepted
- Date: 2026-05-01
- Owners: EAR architecture team

## Context
EAR is being built from scratch and must optimize model selection under cost, latency, quality, and safety constraints. The system must serve both direct CLI users and downstream agents through MCP.

The project needed early decisions on async runtime, CLI framework, and delivery order to reduce integration risk.

## Decision
1. Use asyncio as the asynchronous runtime.
2. Use Typer for the CLI framework.
3. Deliver in two phases:
- Phase 1: router core and CLI until fully tested.
- Phase 2: MCP server integration on top of validated core.
4. Keep architecture cleanly separated:
- Domain and routing logic in engine modules.
- Transport adapters for CLI and MCP.
5. Enforce quality and security gates:
- 100% statement and branch coverage for routing logic.
- bandit and pip-audit included in CI.

## Why These Decisions
### asyncio
- Built into Python with no additional runtime dependency.
- Fits expected network-bound workflow (metadata fetch, model calls).
- Reduces operational complexity for initial delivery.

### Typer
- Strong fit with type-hinted Python codebase.
- Faster development with low boilerplate.
- Produces maintainable command interfaces with good help output.

### CLI-First Sequence
- Lowest integration surface to validate routing behavior.
- Faster feedback loop for scoring heuristics and fallback logic.
- Avoids coupling transport concerns before core rules stabilize.

### Clean Architecture Boundary
- Prevents logic duplication across CLI and MCP transports.
- Improves testability and reliability of the router core.
- Enables future transport extensions with minimal refactor.

### Strict Quality and Security Gates
- Routing service is a control-plane component and a high-impact failure point.
- Full branch coverage is needed for edge cases (timeouts, 429, malformed responses, policy blocks).
- Security scanning reduces risk from dependencies and unsafe coding patterns.

## Consequences
### Positive
- Predictable development path and lower rework risk.
- Clear ownership boundaries between core logic and adapters.
- Better confidence for production readiness through mandatory gates.

### Negative
- 100% coverage and security gates increase initial delivery effort.
- CLI-first approach delays MCP availability until core stabilization.

### Neutral
- Decision can be revisited if advanced structured concurrency requirements emerge.

## Alternatives Considered
1. AnyIO instead of asyncio
- Rejected for initial phase due to added abstraction and dependency overhead.

2. Click instead of Typer
- Rejected because Typer provides cleaner type-driven developer experience for this project.

3. Build CLI and MCP in parallel
- Rejected to avoid duplicating unstable routing interfaces across two transports.

## Follow-Up Actions
1. Implement project skeleton matching this ADR.
2. Add CI workflow with coverage and security gates.
3. Add ADR updates for future major architecture shifts.
