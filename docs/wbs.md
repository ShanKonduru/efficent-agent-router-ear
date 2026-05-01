# EAR Work Breakdown Structure (WBS)

## How to Use This Document

Track delivery using the status column for every item.

| Symbol | Meaning |
| --- | --- |
| `[ ]` | Yet to start |
| `[~]` | In progress |
| `[x]` | Completed |

**Priority scale:** P1 Critical · P2 High · P3 Medium · P4 Low

**Effort scale (Fibonacci story points):** 1 · 2 · 3 · 5 · 8

---

## Epic Overview

| ID | Epic | Priority | Points | Milestone | Status |
| --- | --- | --- | --- | --- | --- |
| E1 | Foundation and Project Setup | P1 | 5 | M1 | `[x]` |
| E2 | Model Registry and Metadata Management | P1 | 10 | M1 | `[x]` |
| E3 | Predictive Routing Engine | P1 | 13 | M2 | `[x]` |
| E4 | CLI Experience and Operator Workflow | P1 | 6 | M2 | `[x]` |
| E5 | Reliability and Cascade Fallback | P1 | 8 | M2 | `[x]` |
| E6 | Safety and Guardrails | P2 | 9 | M3 | `[x]` |
| E7 | Observability and Cost/Latency Metrics | P2 | 5 | M3 | `[x]` |
| E8 | MCP Server and Tool Exposure | P3 | 8 | M4 | `[x]` |
| E9 | CI/CD and Security Automation | P2 | 4 | M4 | `[x]` |
| E10 | Execution Plane and Adaptive Routing Intelligence | P1 | 13 | M5 | `[ ]` |
| E11 | Leadership Demo Frontend and GTM Showcase | P2 | 8 | M6 | `[~]` |
| | **Total** | | **89** | | |

---

## Milestone Map

| Milestone | Target | Epics | Exit Criteria | Status |
| --- | --- | --- | --- | --- |
| M1 — Foundation and Registry | Week 1 | E1, E2 | Skeleton merged; registry client and cache tested | `[x]` |
| M2 — Router Core and CLI | Week 2–3 | E3, E4, E5 | `ear route` command stable; fallback tested; routing at 100% coverage | `[x]` |
| M3 — Guardrails and Observability | Week 4 | E6, E7 | Injection and PII policy enforced; metrics reporting available | `[x]` |
| M4 — MCP and Automation | Week 5 | E8, E9 | MCP tool live; CI pipeline gates passing | `[x]` |
| M5 — Execution and Intelligence | Week 6–7 | E10 | Real model execution active; semantic safety and adaptive intent routing validated | `[ ]` |
| M6 — Frontend and Leadership Demo | Week 8 | E11 | Web demo shows measurable business value and investor-ready narratives | `[~]` |

---

## E1 — Foundation and Project Setup

> Establish the skeleton, toolchain, and environment so all subsequent features build on a consistent base.

**Priority:** P1 · **Total Points:** 5

### Feature F0 — Project Skeleton and Toolchain

| ID | User Story | Priority | Points | Status |
| --- | --- | --- | --- | --- |
| US-0 | As a developer, I want a working Python project structure with dependencies, linting, and test infrastructure so I can develop without friction. | P1 | 5 | `[x]` |

**Acceptance Criteria**
- Given the repo is cloned, when `pip install -e .[dev]` runs, then all dependencies resolve without conflicts.
- Given a developer runs `pytest`, then the test suite discovers all tests and exits cleanly.
- Given `.env` is populated with `OPENROUTER_API_KEY`, when the config module is imported, then the key is loaded without being logged.

| Task ID | Task | Sub-tasks | Priority | Points | Status |
| --- | --- | --- | --- | --- | --- |
| T0.1 | Create `src/ear/` package layout | Add `__init__.py`, `config.py`, `models.py` stubs | P1 | 1 | `[x]` |
| T0.2 | Create `pyproject.toml` with dependencies | Pin httpx, typer, pydantic, mcp; add dev extras for pytest, bandit, pip-audit | P1 | 1 | `[x]` |
| T0.3 | Create `.env.example` and config loader | Load all env vars via Pydantic BaseSettings; fail fast on missing required keys | P1 | 1 | `[x]` |
| T0.4 | Add `pytest.ini` / `pyproject.toml` test config | Configure asyncio mode, cov source, fail under 100% | P1 | 1 | `[x]` |
| T0.5 | Smoke-test the skeleton | Add a trivial test to confirm import chain works end-to-end | P1 | 1 | `[x]` |

---

## E2 — Model Registry and Metadata Management

> Provide live, cached model metadata so routing decisions use real context window sizes and pricing.

**Priority:** P1 · **Total Points:** 10

### Feature F1 — Registry Client and Schema

| ID | User Story | Priority | Points | Status |
| --- | --- | --- | --- | --- |
| US-1 | As an operator, I want live model metadata so routing decisions use real context size and pricing. | P1 | 5 | `[x]` |

**Acceptance Criteria**
- Given the OpenRouter API is reachable, when the registry fetches models, then each entry maps to a typed `LLMSpec` with `id`, `context_length`, and `pricing`.
- Given the API returns a malformed payload, when the registry parses it, then invalid entries are skipped and a warning is logged without crashing.
- Given metadata was fetched less than TTL seconds ago, when a route request arrives, then the cache is served without a new HTTP call.

| Task ID | Task | Sub-tasks | Priority | Points | Status |
| --- | --- | --- | --- | --- | --- |
| T1.1 | Implement `RegistryClient` with httpx | Add timeout, retry with exponential back-off; raise typed errors on 4xx/5xx | P1 | 3 | `[x]` |
| T1.2 | Implement `LLMSpec` Pydantic model and normalization | Map OpenRouter fields; coerce missing pricing to `None`; validate context_length > 0 | P1 | 2 | `[x]` |
| T1.3 | Implement in-memory TTL cache | Configurable TTL via env var; stale-read on refresh failure | P1 | 2 | `[x]` |
| T1.4 | Unit tests for registry | Mock HTTP success, 429, 500, timeout, and malformed JSON; assert cache behavior | P1 | 3 | `[x]` |

---

## E3 — Predictive Routing Engine

> Select the best model for each request through deterministic scoring, intent classification, and ranked fallback.

**Priority:** P1 · **Total Points:** 13

### Feature F2 — Routing Logic and Scoring

| ID | User Story | Priority | Points | Status |
| --- | --- | --- | --- | --- |
| US-2 | As a user, I want the best model selected by task complexity, context size, and budget priority so my request is handled optimally. | P1 | 8 | `[x]` |

**Acceptance Criteria**
- Given a prompt with code blocks, when the router classifies intent, then `task_type` is `coding` and a coding-specialist model is ranked first.
- Given a prompt longer than 100k characters, when the router evaluates candidates, then only mega-context models are eligible.
- Given `budget_priority=low`, when the router scores candidates, then cost weight is amplified and the cheapest qualifying model wins.
- Given two models with the same suitability score, when the router breaks the tie, then the lower-latency model is preferred.

| Task ID | Task | Sub-tasks | Priority | Points | Status |
| --- | --- | --- | --- | --- | --- |
| T2.1 | Implement intent classifier | Rule-based: detect code blocks, length thresholds, keyword signals for planning/research | P1 | 3 | `[x]` |
| T2.2 | Implement suitability scoring function | Compute `S = Quality / (Cost * Latency)`; normalize inputs; apply budget weight multiplier | P1 | 3 | `[x]` |
| T2.3 | Implement candidate ranking and fallback chain | Rank all eligible models; build ordered fallback list; filter by context floor | P1 | 2 | `[x]` |
| T2.4 | Unit tests for every branch and tie-breaker | Empty model list, single model, all models fail eligibility, tie-breaking, each task type | P1 | 5 | `[x]` |

---

## E4 — CLI Experience and Operator Workflow

> Give developers a clean command-line interface that calls the routing engine and returns human and machine-readable output.

**Priority:** P1 · **Total Points:** 6

### Feature F3 — Typer CLI App

| ID | User Story | Priority | Points | Status |
| --- | --- | --- | --- | --- |
| US-3 | As a developer, I want a simple CLI command to route and execute prompts so I can use EAR from my terminal. | P1 | 5 | `[x]` |

**Acceptance Criteria**
- Given `ear route "my prompt" --task coding --budget medium`, when executed, then the selected model and reasoning are printed.
- Given `ear route "my prompt" --json`, when executed, then a valid JSON object is printed and exit code is 0.
- Given an empty prompt string, when executed, then a clear error message is printed and exit code is non-zero.
- Given `ear inspect-models`, when executed, then all cached models with context and pricing are listed.

| Task ID | Task | Sub-tasks | Priority | Points | Status |
| --- | --- | --- | --- | --- | --- |
| T3.1 | Implement Typer app with `route` command | Accept `prompt`, `--task`, `--budget`, `--json` options; wire to router engine | P1 | 2 | `[x]` |
| T3.2 | Implement `inspect-models` and `stats` commands | `inspect-models` lists registry; `stats` prints session metrics summary | P2 | 2 | `[x]` |
| T3.3 | Add output formatter | Human-readable table for terminal; compact JSON for `--json` mode | P1 | 1 | `[x]` |
| T3.4 | CLI integration tests | Test each command path, error conditions, and JSON output shape | P1 | 2 | `[x]` |

---

## E5 — Reliability and Cascade Fallback

> Ensure resilient execution when providers return errors or become unavailable.

**Priority:** P1 · **Total Points:** 8

### Feature F5 — Fallback Execution Pipeline

| ID | User Story | Priority | Points | Status |
| --- | --- | --- | --- | --- |
| US-5 | As a user, I want resilient execution when a provider fails so my request succeeds or I get a clear failure report. | P1 | 5 | `[x]` |

**Acceptance Criteria**
- Given a primary model returns 429, when the fallback pipeline runs, then the next ranked model is tried automatically.
- Given all candidates are exhausted, when the pipeline terminates, then a structured error with full fallback path is returned.
- Given a transient 5xx, when the retry policy applies, then at most `MAX_RETRIES` attempts are made before cascading.

| Task ID | Task | Sub-tasks | Priority | Points | Status |
| --- | --- | --- | --- | --- | --- |
| T5.1 | Implement failure classifier | Classify 429, 5xx, timeout, and malformed response as transient or fatal | P1 | 2 | `[x]` |
| T5.2 | Implement fallback execution pipeline | Ordered iteration over fallback chain; per-model retry with back-off; aggregate error log | P1 | 3 | `[x]` |
| T5.3 | Tests for all failure scenarios | Mock 429, 500, timeout per model; assert correct model selected on each cascade step | P1 | 3 | `[x]` |

---

## E6 — Safety and Guardrails

> Prevent unsafe prompts and PII from being forwarded to models that are not cleared for sensitive data.

**Priority:** P2 · **Total Points:** 9

### Feature F4 — Injection and PII Policy

| ID | User Story | Priority | Points | Status |
| --- | --- | --- | --- | --- |
| US-4 | As a security owner, I want unsafe prompts and PII to be handled safely before model routing so no sensitive data leaks to unvetted providers. | P2 | 8 | `[x]` |

**Acceptance Criteria**
- Given a prompt containing a jailbreak pattern, when the guardrail runs, then routing is blocked and a reason code is returned.
- Given a prompt containing PII signals (email, SSN pattern), when the guardrail evaluates providers, then only vetted private models are eligible.
- Given a clean prompt, when the guardrail runs, then routing proceeds without delay.

| Task ID | Task | Sub-tasks | Priority | Points | Status |
| --- | --- | --- | --- | --- | --- |
| T4.1 | Implement prompt injection precheck | Rule-based pattern library; configurable sensitivity threshold; return signal with reason | P2 | 3 | `[x]` |
| T4.2 | Implement PII detector and provider policy matrix | Detect common PII patterns; map detection to provider allowlist; block disallowed candidates | P2 | 3 | `[x]` |
| T4.3 | Add sanitization layer before model call | Strip or mask detected PII for logging; never log raw prompts in plaintext | P2 | 1 | `[x]` |
| T4.4 | Policy-enforcement unit tests | Test each injection pattern, PII type, and allowlist filtering scenario | P2 | 3 | `[x]` |

---

## E7 — Observability and Cost/Latency Metrics

> Track cost and latency per model and session so operators can measure efficiency.

**Priority:** P2 · **Total Points:** 5

### Feature F6 — Metrics Collector

| ID | User Story | Priority | Points | Status |
| --- | --- | --- | --- | --- |
| US-6 | As an operator, I want to track cost and latency by session and model so I can monitor token burn and performance. | P2 | 3 | `[x]` |

**Acceptance Criteria**
- Given a route decision is made, when it completes, then cost and latency are emitted to the collector.
- Given `ear stats`, when executed, then a summary of session totals and per-model breakdown is shown.
- Given the collector is reset, when new route calls are made, then only those calls appear in the next report.

| Task ID | Task | Sub-tasks | Priority | Points | Status |
| --- | --- | --- | --- | --- | --- |
| T6.1 | Define `RouteMetric` and `SessionSummary` schemas | Pydantic models for per-call and aggregated metrics | P2 | 1 | `[x]` |
| T6.2 | Implement in-process metrics collector | Accumulate cost and latency; expose session totals; thread-safe reset | P2 | 2 | `[x]` |
| T6.3 | Hook collector into router and fallback pipeline | Emit metrics on success and on each fallback step | P2 | 1 | `[x]` |
| T6.4 | Unit tests for accumulation and reset | Test multiple route calls; assert totals; assert reset clears state | P2 | 2 | `[x]` |

---

## E8 — MCP Server and Tool Exposure

> Expose the validated routing engine to other agents through the Model Context Protocol.

**Priority:** P3 · **Total Points:** 8

### Feature F7 — MCP Transport and Tools

| ID | User Story | Priority | Points | Status |
| --- | --- | --- | --- | --- |
| US-7 | As an agent consumer, I want to call EAR as an MCP tool so I can route prompts programmatically from another agent. | P3 | 5 | `[x]` |

**Acceptance Criteria**
- Given an MCP client calls `route_and_execute` with `task_description` and `budget_priority`, then the server returns the selected model ID and routing rationale.
- Given the MCP resource for model stats is requested, then the current session metrics are returned as a structured object.
- Given the router engine logic changes, then no changes to the MCP transport layer are required.

| Task ID | Task | Sub-tasks | Priority | Points | Status |
| --- | --- | --- | --- | --- | --- |
| T7.1 | Build MCP server transport layer | Wire stdio transport; register tool and resource handlers; delegate to router engine | P3 | 2 | `[x]` |
| T7.2 | Implement `route_and_execute` tool endpoint | Validate typed input with Pydantic; call router; return structured response | P3 | 2 | `[x]` |
| T7.3 | Implement model stats resource endpoint | Return current `SessionSummary` as MCP resource | P3 | 1 | `[x]` |
| T7.4 | MCP integration tests | Test tool call, resource read, missing field errors, and engine failure propagation | P3 | 3 | `[x]` |

---

## E9 — CI/CD and Security Automation

> Prevent regressions and vulnerabilities through automated pipeline checks on every pull request.

**Priority:** P2 · **Total Points:** 4

### Feature F8 — GitHub Actions Pipeline

| ID | User Story | Priority | Points | Status |
| --- | --- | --- | --- | --- |
| US-8 | As a maintainer, I want automated checks on every PR so regressions and vulnerabilities are caught before merge. | P2 | 3 | `[x]` |

**Acceptance Criteria**
- Given a PR is opened, when CI runs, then pytest must pass with 100% coverage or the build fails.
- Given a PR is opened, when CI runs, then `bandit -r src/` and `pip-audit` must both exit cleanly or the build fails.
- Given a PR introduces a dependency with a known CVE, when `pip-audit` runs, then the build breaks with the CVE listed.
- Given security workflows run, when sec-report-kit rendering completes, then HTML reports exist as workflow artifacts for both pip-audit and trivy.

| Task ID | Task | Sub-tasks | Priority | Points | Status |
| --- | --- | --- | --- | --- | --- |
| T8.1 | Add GitHub Actions workflow | Trigger on PR and push to main; run on ubuntu-latest with Python 3.12 | P2 | 2 | `[x]` |
| T8.2 | Configure test, coverage, and security steps | `pytest --cov=src/ear --cov-fail-under=100`; `bandit -r src/`; `pip-audit` | P2 | 1 | `[x]` |
| T8.3 | Validate workflow with forced failure | Temporarily drop coverage below threshold; confirm build breaks | P2 | 1 | `[x]` |

---

## E10 — Execution Plane and Adaptive Routing Intelligence

> Close the delivery gap between model recommendation and real model execution so EAR provides measurable end-user value.

**Priority:** P1 · **Total Points:** 13

### Feature F9 — Unified Execution Runtime (LiteLLM)

| ID | User Story | Priority | Points | Status |
| --- | --- | --- | --- | --- |
| US-9 | As a user, I want EAR to execute the selected model and return the final answer so routing directly improves my workflow. | P1 | 8 | `[ ]` |

**Acceptance Criteria**
- Given `ear route --execute`, when a model is selected, then EAR calls the model and returns generated content with route metadata.
- Given MCP `route_and_execute`, when called, then a response payload includes selected model, output text, and fallback trace.
- Given a 429/5xx/timeout on primary model, when execution runs, then fallback candidates are attempted and recorded.
- Given a successful completion, when metrics are emitted, then real latency and token/cost usage are captured from provider response usage fields.

| Task ID | Task | Sub-tasks | Priority | Points | Status |
| --- | --- | --- | --- | --- | --- |
| T9.1 | Add LiteLLM execution adapter | Create provider-agnostic request/response interface; map OpenRouter models; configure auth/timeouts | P1 | 2 | `[ ]` |
| T9.2 | Implement execution orchestration service | Compose guardrails, router, executor, and fallback into one deterministic pipeline | P1 | 3 | `[ ]` |
| T9.3 | Extend CLI and MCP contracts for execution mode | Add explicit execute flag and output schema fields for response text and execution metadata | P1 | 2 | `[ ]` |
| T9.4 | Emit real execution telemetry | Record actual end-to-end latency, token usage, cost estimate, and fallback attempt counts | P1 | 2 | `[ ]` |
| T9.5 | Add integration tests for execution paths | Mock success, 429, 5xx, timeout, and malformed payloads; assert fallback and telemetry correctness | P1 | 3 | `[ ]` |

### Feature F10 — Adaptive Intent and Semantic Safety

| ID | User Story | Priority | Points | Status |
| --- | --- | --- | --- | --- |
| US-10 | As a security and platform owner, I want semantic intent/injection analysis so routing quality improves and policy evasion risk drops. | P1 | 5 | `[ ]` |

**Acceptance Criteria**
- Given ambiguous prompts, when intent classification runs, then embedding/flash-model classification outperforms keyword baseline on evaluation set.
- Given jailbreak-style prompts, when semantic injection analysis runs, then high-risk prompts are blocked or downgraded with reason codes.
- Given execution requests, when mini-controller mode is enabled, then a small model can provide route hints in strict JSON and routing remains deterministic.

| Task ID | Task | Sub-tasks | Priority | Points | Status |
| --- | --- | --- | --- | --- | --- |
| T9.6 | Add advanced intent classifier | Integrate local embedding classifier or flash-model intent endpoint with deterministic fallback to heuristics | P1 | 2 | `[ ]` |
| T9.7 | Implement semantic prompt-injection detector | Add risk scoring pipeline and policy thresholds; return machine-readable reason codes | P1 | 3 | `[ ]` |
| T9.8 | Add mini-controller routing hints | Define strict JSON schema for controller output; validate and merge with deterministic scoring rules | P2 | 2 | `[ ]` |
| T9.9 | Build evaluation harness and benchmark suite | Compare precision/recall vs current heuristics for intent and injection detection | P2 | 3 | `[ ]` |

---

## E11 — Leadership Demo Frontend and GTM Showcase

> Demonstrate business value clearly to leadership and investors through an interactive product narrative instead of code artifacts.

**Priority:** P2 · **Total Points:** 8

### Feature F11 — Interactive Value Demonstration App

| ID | User Story | Priority | Points | Status |
| --- | --- | --- | --- | --- |
| US-11 | As a leadership stakeholder, I want a visual, interactive EAR demo so I can quickly understand cost, reliability, and safety benefits. | P2 | 5 | `[~]` |

**Acceptance Criteria**
- Given a demo scenario, when a prompt is executed, then UI shows selected model, answer, fallback timeline, and safety decisions.
- Given baseline and EAR modes, when results are compared, then cost/latency deltas and reliability gains are visualized.
- Given leadership presentation mode, when run on desktop or mobile, then the flow is stable, polished, and non-technical stakeholders can follow it end-to-end.
- Given investor review, when viewing the dashboard, then KPI panels highlight ROI signals (cost saved, failure avoided, policy violations blocked).

| Task ID | Task | Sub-tasks | Priority | Points | Status |
| --- | --- | --- | --- | --- | --- |
| T10.1 | Build frontend shell and design system | Implement responsive web app with scenario selector, run panel, metrics cards, and narrative timeline (current: `docs/llm_explorer.html` live comparison UI) | P2 | 3 | `[~]` |
| T10.2 | Expose demo backend endpoints | Add API layer for route/execute, baseline compare mode, and replay datasets for deterministic demonstrations | P2 | 2 | `[ ]` |
| T10.3 | Implement value storytelling views | Add before/after comparison charts, safety incident feed, and executive summary mode | P2 | 2 | `[ ]` |
| T10.4 | Add demo readiness validation | Seed golden scenarios, add smoke tests, and create one-click script for leadership walkthrough | P2 | 1 | `[ ]` |

---

## WBS Summary

| Metric | Value |
| --- | --- |
| Total Epics | 11 |
| Total Features | 12 |
| Total User Stories | 12 |
| Total Tasks | 48 |
| Total Story Points | 89 |
| Estimated Timeline | 6–8 weeks |
| Weekly Capacity Assumption | 10–14 points/week |

## Priority Order for Development

From the current project state, the remaining execution order is:

1. E10 F9 — implement true route-and-execute runtime via LiteLLM with telemetry and fallback
2. E10 F10 — add semantic intent/injection intelligence and mini-controller evaluation harness
3. E11 F11 — deliver leadership/investor frontend demo with baseline-vs-EAR value comparison
4. Keep branch synchronization policy (`master` and `main`) enforced for every release change
5. Continue dependency and security posture monitoring in scheduled workflows
