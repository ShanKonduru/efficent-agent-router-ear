# EAR Execution Plan

## Planning Basis
- Delivery approach: CLI-first, MCP second
- Runtime defaults: Python 3.12+, asyncio, Typer
- Quality gates: 100% statement and branch coverage for routing logic
- Security gates: bandit and pip-audit must pass

## Feature Set
1. Model Registry and Metadata Management (`[x]`)
2. Predictive Routing Engine (`[x]`)
3. CLI Experience and Operator Workflow (`[x]`)
4. Safety and Guardrails (`[x]`)
5. Reliability and Cascade Fallback (`[x]`)
6. Observability and Cost/Latency Metrics (`[x]`)
7. MCP Server and Tool Exposure (`[x]`)
8. CI/CD and Security Automation (`[x]`)
9. Execution Plane and Adaptive Routing Intelligence (`[x]`)
10. Leadership Demo Frontend and GTM Showcase (`[x]`)
11. Release, Distribution, and Branch Governance (`[ ]`)
12. Live Demo Backend ↔ Frontend Integration (`[ ]`)
13. Live Execution Canary Validation (`[ ]`)
14. Benchmark Harness Execution and Results (`[ ]`)
15. Architecture Decision Records Backfill (`[ ]`)

## Recommended Execution Order (Current State)
1. E10 F9: implement true route-and-execute runtime (LiteLLM + fallback + real telemetry) `[x]`
2. E10 F10: add semantic intent/injection intelligence and benchmark harness `[x]`
3. E11 F11: build leadership/investor frontend demo with baseline-vs-EAR value views `[x]`
4. E12 F12: verify v0.10.3 PyPI release artifacts and synchronize `master` → `main` `[ ]`
5. E14 F14: run live execution canary against real OpenRouter providers `[ ]`
6. E13 F13: wire `DemoBackendService` API endpoints to `llm_explorer.html` frontend `[ ]`
7. E15 F15: execute benchmark harness and publish precision/recall results `[ ]`
8. E16 F16: backfill ADRs for LiteLLM, guardrails, MCP transport, and demo replay `[ ]`
9. Continue release governance, branch synchronization, and security posture monitoring

## User Stories, Tasks, and Estimates

### F1. Model Registry and Metadata Management
- Story US-1 (5 pts) `[x]`: As an operator, I want live model metadata so routing decisions use real context size and pricing.
- Acceptance highlights:
  - Fetch OpenRouter models and map to typed domain model.
  - Cache metadata with TTL and refresh strategy.
  - Handle malformed payloads gracefully.
- Tasks:
  - T1.1 Implement metadata client with timeout/retry (3 pts) `[x]`
  - T1.2 Implement Pydantic schemas and normalization (2 pts) `[x]`
  - T1.3 Add in-memory TTL cache and stale-read strategy (2 pts) `[x]`
  - T1.4 Unit tests for success/failure/parsing branches (3 pts) `[x]`

### F2. Predictive Routing Engine
- Story US-2 (8 pts) `[x]`: As a user, I want the best model selected by task complexity, context size, and budget priority.
- Acceptance highlights:
  - Classify task intent (simple/planning/coding/research).
  - Compute suitability score with explainable factors.
  - Produce ranked candidates with fallback chain.
- Tasks:
  - T2.1 Implement deterministic heuristics (3 pts) `[x]`
  - T2.2 Implement scoring function and weights (3 pts) `[x]`
  - T2.3 Implement fallback chain construction (2 pts) `[x]`
  - T2.4 Unit tests for every branch and tie-breaker (5 pts) `[x]`

### F3. CLI Experience and Operator Workflow
- Story US-3 (5 pts) `[x]`: As a developer, I want a simple CLI command to route and execute prompts.
- Acceptance highlights:
  - Support route command with task and budget options.
  - Display selected model and reasoning summary.
  - Return structured JSON mode for automation.
- Tasks:
  - T3.1 Implement Typer app and commands (2 pts) `[x]`
  - T3.2 Add output formatting and machine-readable mode (2 pts) `[x]`
  - T3.3 Add CLI integration tests (2 pts) `[x]`

### F4. Safety and Guardrails
- Story US-4 (8 pts) `[x]`: As a security owner, I want unsafe prompts and PII to be handled safely before model routing.
- Acceptance highlights:
  - Prompt-injection signal check.
  - PII detection and public-model routing restrictions.
  - Audit reason codes in routing response.
- Tasks:
  - T4.1 Add prompt-injection precheck rules (3 pts) `[x]`
  - T4.2 Add PII detector and policy matrix (3 pts) `[x]`
  - T4.3 Add policy-enforcement tests (3 pts) `[x]`

### F5. Reliability and Cascade Fallback
- Story US-5 (5 pts) `[x]`: As a user, I want resilient execution when a provider fails.
- Acceptance highlights:
  - Retry transient failures with bounded attempts.
  - Cascade to next ranked model on persistent failures.
  - Report final status and fallback path.
- Tasks:
  - T5.1 Implement failure classifier (2 pts) `[x]`
  - T5.2 Implement fallback execution pipeline (3 pts) `[x]`
  - T5.3 Test 429/5xx/timeout cases (3 pts) `[x]`

### F6. Observability and Cost/Latency Metrics
- Story US-6 (3 pts) `[x]`: As an operator, I want to track cost and latency by session and model.
- Acceptance highlights:
  - Emit structured metrics per route decision.
  - Track session totals and model-level breakdown.
- Tasks:
  - T6.1 Define metrics schema (1 pt) `[x]`
  - T6.2 Implement collector and reporting hooks (2 pts) `[x]`
  - T6.3 Unit tests for accumulation and reset behavior (2 pts) `[x]`

### F7. MCP Server and Tool Exposure (Phase 2)
- Story US-7 (5 pts) `[x]`: As an agent consumer, I want EAR exposed as MCP tool route_and_execute.
- Acceptance highlights:
  - Expose route_and_execute tool with typed arguments.
  - Expose resources for model stats.
  - Reuse router engine without duplicating logic.
- Tasks:
  - T7.1 Build MCP server transport layer (2 pts) `[x]`
  - T7.2 Implement tool and resource endpoints (3 pts) `[x]`
  - T7.3 Add MCP integration tests (3 pts) `[x]`

### F8. CI/CD and Security Automation
- Story US-8 (3 pts) `[x]`: As a maintainer, I want automated checks to prevent regressions and vulnerabilities.
- Acceptance highlights:
  - Run tests with enforced 100% coverage.
  - Run bandit and pip-audit on every PR.
  - Produce HTML security reports (pip-audit and trivy) via sec-report-kit in workflow artifacts.
  - Fail pipeline on any quality gate failure.
- Tasks:
  - T8.1 Add GitHub Actions workflow (2 pts) `[x]`
  - T8.2 Configure coverage and security thresholds (1 pt) `[x]`
  - T8.3 Validate workflow with sample failure case (1 pt) `[x]`
  - T8.4 Verify ongoing branch synchronization policy for `master` and `main` (1 pt) `[x]`

### F9. Unified Execution Runtime (LiteLLM)
- Story US-9 (8 pts) `[x]`: As a user, I want EAR to execute routed model calls and return final answers with fallback transparency.
- Acceptance highlights:
  - Route decision is followed by real provider execution.
  - MCP `route_and_execute` returns model output plus route metadata.
  - 429/5xx/timeout failures trigger ordered fallback attempts.
  - Metrics capture real latency, tokens, and cost from provider usage.
- Tasks:
  - T9.1 Add LiteLLM execution adapter and provider mapping (2 pts) `[x]`
  - T9.2 Implement execution orchestration service (3 pts) `[x]`
  - T9.3 Extend CLI and MCP contracts for execute mode (2 pts) `[x]`
  - T9.4 Emit real execution telemetry (2 pts) `[x]`
  - T9.5 Add integration tests for success/failure execution paths (3 pts) `[x]`

### F10. Adaptive Intent and Semantic Safety
- Story US-10 (5 pts) `[x]`: As a platform owner, I want semantic intent and injection analysis so routing quality and safety improve beyond keyword rules.
- Acceptance highlights:
  - Advanced intent classification outperforms current heuristic baseline.
  - Semantic jailbreak analysis adds policy risk scoring and reason codes.
  - Optional mini-controller returns strict JSON route hints without breaking deterministic safeguards.
- Tasks:
  - T9.6 Integrate embedding or flash-model intent classifier (2 pts) `[x]`
  - T9.7 Implement semantic prompt-injection detector (3 pts) `[x]`
  - T9.8 Add mini-controller routing hint flow with schema validation (2 pts) `[x]`
  - T9.9 Build benchmark suite versus heuristic baseline (3 pts) `[x]`

### F11. Leadership Demo Frontend
- Story US-11 (5 pts) `[x]`: As a leadership stakeholder, I want an interactive EAR demo that clearly shows ROI and risk reduction.
- Acceptance highlights:
  - End-to-end scenario runs show selected model, response, fallback trail, and safety events.
  - Baseline versus EAR mode shows measurable deltas for cost, latency, and reliability.
  - Executive view is presentation-ready across desktop and mobile.
- Tasks:
  - T10.1 Build responsive demo UI shell and scenario flow (3 pts) `[x]`
  - T10.2 Add backend API bridge and deterministic replay data (2 pts) `[x]`
  - T10.3 Implement KPI dashboards and storytelling panels (2 pts) `[x]`
  - T10.4 Add one-click demo script and smoke tests (1 pt) `[x]`

### F12. Release, Distribution, and Branch Governance
- Story US-12 (5 pts) `[ ]`: As a maintainer, I want v0.10.3 verified on PyPI and branches synchronized so the release is officially complete.
- Acceptance highlights:
  - Wheel and sdist artifacts present on PyPI for v0.10.3.
  - Install smoke test passes from PyPI.
  - `master` mirrored to `main` with no divergence.
  - Security HTML reports attached as workflow artifacts.
- Tasks:
  - T11.1 Confirm PyPI wheel and sdist artifacts (1 pt) `[ ]`
  - T11.2 Run install and import smoke test from PyPI (1 pt) `[ ]`
  - T11.3 Mirror `master` → `main` per release playbook (1 pt) `[ ]`
  - T11.4 Attach security HTML reports as workflow artifacts (1 pt) `[ ]`
  - T11.5 Update release-playbook.md with any gaps discovered (1 pt) `[ ]`

### F13. Live Demo Backend ↔ Frontend Integration
- Story US-13 (8 pts) `[ ]`: As a leadership stakeholder, I want the demo UI to call live backend endpoints so scenario data is authoritative and the frontend never goes stale.
- Acceptance highlights:
  - `llm_explorer.html` fetches scenarios from `/api/scenarios` instead of static in-page data.
  - Compare cards update from `/api/compare/{id}` on scenario selection.
  - Graceful error banner when backend is unreachable.
  - Coverage remains at 100% after API layer is added.
- Tasks:
  - T12.1 Add FastAPI/Starlette server wrapping `DemoBackendService` (2 pts) `[ ]`
  - T12.2 Replace static JS data with `fetch()` calls in `llm_explorer.html` (3 pts) `[ ]`
  - T12.3 Add error banner and graceful degradation (1 pt) `[ ]`
  - T12.4 Add smoke tests for API endpoints (2 pts) `[ ]`

### F14. Live Execution Canary Validation
- Story US-14 (5 pts) `[ ]`: As a platform owner, I want EAR validated against real providers so execution pipeline confidence is grounded in real calls, not just mocks.
- Acceptance highlights:
  - Canary script runs against at least two real OpenRouter providers.
  - Response structure, telemetry fields (latency, tokens, cost) are non-zero.
  - Canary pass criteria documented in release-playbook.md.
- Tasks:
  - T13.1 Create canary execution script with configurable model and prompt (2 pts) `[ ]`
  - T13.2 Run canary against two real providers and assert response structure (2 pts) `[ ]`
  - T13.3 Document canary pass criteria in release-playbook.md (1 pt) `[ ]`

### F15. Benchmark Harness Execution and Results
- Story US-15 (5 pts) `[ ]`: As a platform owner, I want the evaluation harness to produce documented benchmark results so routing quality claims are backed by evidence.
- Acceptance highlights:
  - Precision, recall, and F1 recorded per intent class and injection category.
  - Semantic classifier meets or exceeds heuristic baseline on safety-critical categories.
  - Results referenced from README.
- Tasks:
  - T14.1 Run evaluation harness on full scenario set (2 pts) `[ ]`
  - T14.2 Compute and record precision/recall/F1 in `docs/benchmark_results.md` (2 pts) `[ ]`
  - T14.3 Reference benchmark results from README (1 pt) `[ ]`

### F16. Architecture Decision Records Backfill
- Story US-16 (4 pts) `[ ]`: As a contributor, I want key architecture decisions recorded in ADRs so the design intent is preserved for future maintainers.
- Acceptance highlights:
  - ADR exists for each major design decision; follows existing `0001-` naming convention.
  - Each ADR covers context, options considered, and chosen approach.
- Tasks:
  - T15.1 Write ADR for LiteLLM as execution adapter (1 pt) `[ ]`
  - T15.2 Write ADR for guardrail scoring and semantic injection detection (1 pt) `[ ]`
  - T15.3 Write ADR for MCP transport design and tool exposure (1 pt) `[ ]`
  - T15.4 Write ADR for demo backend deterministic replay design (1 pt) `[ ]`

## Milestones

### M1. Foundation and Registry (Target: Week 1) `[x]`
- Scope: F1, baseline config, project skeleton
- Exit criteria:
  - Registry client merged
  - Metadata cache covered by tests

### M2. Router Core and CLI (Target: Week 2-3) `[x]`
- Scope: F2, F3, F5
- Exit criteria:
  - route command stable
  - fallback path tested
  - routing coverage at 100%

### M3. Guardrails and Observability (Target: Week 4) `[x]`
- Scope: F4, F6
- Exit criteria:
  - injection and PII policy enforced
  - session metric reporting available

### M4. MCP and Automation (Target: Week 5) `[x]`
- Scope: F7, F8
- Exit criteria:
  - MCP tool available
  - CI pipeline gates passing

### M5. Execution and Intelligence (Target: Week 6-7) `[x]`
- Scope: F9, F10
- Exit criteria:
  - Route decisions execute real model calls with resilient fallback
  - Semantic intent/injection controls validated against benchmark set

### M6. Frontend and Leadership Demo (Target: Week 8) `[x]`
- Scope: F11
- Exit criteria:
  - Investor/leadership demo app shows measurable EAR value narrative
  - Demo flow passes scripted walkthrough and smoke tests

### M7. Post-Launch Hardening (Target: Week 9–10) `[ ]`
- Scope: F12, F13, F14, F15, F16
- Exit criteria:
  - v0.10.3 release verified on PyPI; install smoke test passes
  - `master` mirrored to `main` with no divergence
  - Live demo backend wired to `llm_explorer.html` frontend
  - Canary executed against two real providers with telemetry confirmed
  - Benchmark precision/recall results documented in `docs/benchmark_results.md`
  - ADRs filed for LiteLLM, guardrails, MCP transport, and demo replay design

## Capacity and Sizing Summary
- Total story points: 87
- Suggested team capacity assumption: 10 to 14 points/week
- Estimated timeline: 9 to 10 weeks depending on team size and external API volatility

## Risk Register
1. OpenRouter payload changes break parsing
- Mitigation: strict schema normalization and contract tests.

2. Safety false positives reduce usability
- Mitigation: tune thresholds and provide override controls for trusted contexts.

3. Cost optimization degrades quality for complex tasks
- Mitigation: quality floor and weighted scoring guardrails.

4. 100% coverage target slows delivery
- Mitigation: parallelize test authoring with feature development.

5. Execution-provider abstraction drift (OpenRouter vs LiteLLM mapping)
- Mitigation: add contract tests around request/response mapping and strict schema validation.

6. Demo fails to communicate business value to non-technical stakeholders
- Mitigation: predefine three investor-ready scenarios with KPI deltas and narrative annotations.

## Definition of Done
- Feature code merged with typed interfaces.
- Unit/integration tests passing with required coverage.
- Security scans clean.
- Documentation and ADR updated.
