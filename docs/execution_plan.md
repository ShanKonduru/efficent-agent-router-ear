# EAR Execution Plan

## Planning Basis
- Delivery approach: CLI-first, MCP second
- Runtime defaults: Python 3.12+, asyncio, Typer
- Quality gates: 100% statement and branch coverage for routing logic
- Security gates: bandit and pip-audit must pass

## Feature Set
1. Model Registry and Metadata Management
2. Predictive Routing Engine
3. CLI Experience and Operator Workflow
4. Safety and Guardrails
5. Reliability and Cascade Fallback
6. Observability and Cost/Latency Metrics
7. MCP Server and Tool Exposure
8. CI/CD and Security Automation

## User Stories, Tasks, and Estimates

### F1. Model Registry and Metadata Management
- Story US-1 (5 pts): As an operator, I want live model metadata so routing decisions use real context size and pricing.
- Acceptance highlights:
  - Fetch OpenRouter models and map to typed domain model.
  - Cache metadata with TTL and refresh strategy.
  - Handle malformed payloads gracefully.
- Tasks:
  - T1.1 Implement metadata client with timeout/retry (3 pts)
  - T1.2 Implement Pydantic schemas and normalization (2 pts)
  - T1.3 Add in-memory TTL cache and stale-read strategy (2 pts)
  - T1.4 Unit tests for success/failure/parsing branches (3 pts)

### F2. Predictive Routing Engine
- Story US-2 (8 pts): As a user, I want the best model selected by task complexity, context size, and budget priority.
- Acceptance highlights:
  - Classify task intent (simple/planning/coding/research).
  - Compute suitability score with explainable factors.
  - Produce ranked candidates with fallback chain.
- Tasks:
  - T2.1 Implement deterministic heuristics (3 pts)
  - T2.2 Implement scoring function and weights (3 pts)
  - T2.3 Implement fallback chain construction (2 pts)
  - T2.4 Unit tests for every branch and tie-breaker (5 pts)

### F3. CLI Experience and Operator Workflow
- Story US-3 (5 pts): As a developer, I want a simple CLI command to route and execute prompts.
- Acceptance highlights:
  - Support route command with task and budget options.
  - Display selected model and reasoning summary.
  - Return structured JSON mode for automation.
- Tasks:
  - T3.1 Implement Typer app and commands (2 pts)
  - T3.2 Add output formatting and machine-readable mode (2 pts)
  - T3.3 Add CLI integration tests (2 pts)

### F4. Safety and Guardrails
- Story US-4 (8 pts): As a security owner, I want unsafe prompts and PII to be handled safely before model routing.
- Acceptance highlights:
  - Prompt-injection signal check.
  - PII detection and public-model routing restrictions.
  - Audit reason codes in routing response.
- Tasks:
  - T4.1 Add prompt-injection precheck rules (3 pts)
  - T4.2 Add PII detector and policy matrix (3 pts)
  - T4.3 Add policy-enforcement tests (3 pts)

### F5. Reliability and Cascade Fallback
- Story US-5 (5 pts): As a user, I want resilient execution when a provider fails.
- Acceptance highlights:
  - Retry transient failures with bounded attempts.
  - Cascade to next ranked model on persistent failures.
  - Report final status and fallback path.
- Tasks:
  - T5.1 Implement failure classifier (2 pts)
  - T5.2 Implement fallback execution pipeline (3 pts)
  - T5.3 Test 429/5xx/timeout cases (3 pts)

### F6. Observability and Cost/Latency Metrics
- Story US-6 (3 pts): As an operator, I want to track cost and latency by session and model.
- Acceptance highlights:
  - Emit structured metrics per route decision.
  - Track session totals and model-level breakdown.
- Tasks:
  - T6.1 Define metrics schema (1 pt)
  - T6.2 Implement collector and reporting hooks (2 pts)
  - T6.3 Unit tests for accumulation and reset behavior (2 pts)

### F7. MCP Server and Tool Exposure (Phase 2)
- Story US-7 (5 pts): As an agent consumer, I want EAR exposed as MCP tool route_and_execute.
- Acceptance highlights:
  - Expose route_and_execute tool with typed arguments.
  - Expose resources for model stats.
  - Reuse router engine without duplicating logic.
- Tasks:
  - T7.1 Build MCP server transport layer (2 pts)
  - T7.2 Implement tool and resource endpoints (3 pts)
  - T7.3 Add MCP integration tests (3 pts)

### F8. CI/CD and Security Automation
- Story US-8 (3 pts): As a maintainer, I want automated checks to prevent regressions and vulnerabilities.
- Acceptance highlights:
  - Run tests with enforced 100% coverage.
  - Run bandit and pip-audit on every PR.
  - Fail pipeline on any quality gate failure.
- Tasks:
  - T8.1 Add GitHub Actions workflow (2 pts)
  - T8.2 Configure coverage and security thresholds (1 pt)
  - T8.3 Validate workflow with sample failure case (1 pt)

## Milestones

### M1. Foundation and Registry (Target: Week 1)
- Scope: F1, baseline config, project skeleton
- Exit criteria:
  - Registry client merged
  - Metadata cache covered by tests

### M2. Router Core and CLI (Target: Week 2-3)
- Scope: F2, F3, F5
- Exit criteria:
  - route command stable
  - fallback path tested
  - routing coverage at 100%

### M3. Guardrails and Observability (Target: Week 4)
- Scope: F4, F6
- Exit criteria:
  - injection and PII policy enforced
  - session metric reporting available

### M4. MCP and Automation (Target: Week 5)
- Scope: F7, F8
- Exit criteria:
  - MCP tool available
  - CI pipeline gates passing

## Capacity and Sizing Summary
- Total story points: 42
- Suggested team capacity assumption: 10 to 14 points/week
- Estimated timeline: 4 to 6 weeks depending on team size and external API volatility

## Risk Register
1. OpenRouter payload changes break parsing
- Mitigation: strict schema normalization and contract tests.

2. Safety false positives reduce usability
- Mitigation: tune thresholds and provide override controls for trusted contexts.

3. Cost optimization degrades quality for complex tasks
- Mitigation: quality floor and weighted scoring guardrails.

4. 100% coverage target slows delivery
- Mitigation: parallelize test authoring with feature development.

## Definition of Done
- Feature code merged with typed interfaces.
- Unit/integration tests passing with required coverage.
- Security scans clean.
- Documentation and ADR updated.
