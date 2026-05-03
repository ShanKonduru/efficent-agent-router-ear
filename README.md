# Efficient Agent Router (EAR)

Efficient Agent Router (EAR) is a Python-first orchestration service that selects and executes the best LLM for a request based on quality, cost, latency, context window, and safety constraints.

## Goals
- Route each request to the most suitable model for the task.
- Reduce token burn through cost-aware model ranking.
- Protect sensitive input with prompt-injection and PII safeguards.
- Provide a clean CLI first, then expose the same logic through MCP.

## Current Delivery Status (v0.11.0)

| Epic | Description | Status |
|---|---|---|
| E1 | Foundation and Project Setup | ✅ Complete |
| E2 | Model Registry and Metadata Management | ✅ Complete |
| E3 | Predictive Routing Engine | ✅ Complete |
| E4 | CLI Experience and Operator Workflow | ✅ Complete |
| E5 | Reliability and Cascade Fallback | ✅ Complete |
| E6 | Safety and Guardrails | ✅ Complete |
| E7 | Observability and Cost/Latency Metrics | ✅ Complete |
| E8 | MCP Server and Tool Exposure | ✅ Complete |
| E9 | CI/CD and Security Automation | ✅ Complete |
| E10 | Execution Plane and Adaptive Routing Intelligence | ✅ Complete |
| E11 | Leadership Demo Frontend and GTM Showcase | ✅ Complete |
| E17 | Ollama Private Provider Integration | ✅ Complete |
| E18 | Live React Web Console | ✅ Complete |
| E19 | CLI Aliases and UX Polish | ✅ Complete |
| E20 | Judge-Based Intelligent Routing with Local LLM | ✅ Complete |
| E12–E16 | Post-launch hardening (PyPI verify, canary, benchmarks, ADRs) | ⏳ Pending |

## Current Delivery Strategy
1. Build and validate core routing engine through CLI. ✅
2. Harden reliability, guardrails, and observability. ✅
3. Expose stable capabilities through MCP server. ✅
4. Add real execution runtime and adaptive intent/injection intelligence. ✅
5. Ship interactive leadership demo with value storytelling. ✅
6. Add Ollama private provider for on-premise safety routing. ✅
7. Ship live React web console for developer-facing routing visualization. ✅
8. Add judge-based intelligent routing with local LLM for context-aware decisions. ✅
9. Post-launch: verify PyPI release, run live canary, publish benchmarks, backfill ADRs.

## Tech Stack
- Python 3.12+
- asyncio
- Typer CLI
- Pydantic v2
- httpx for OpenRouter model metadata
- pytest, pytest-asyncio, pytest-cov
- bandit and pip-audit for security controls

## Repository Layout

```
src/
  ear/
    __init__.py          # Package root, version
    config.py            # Pydantic-settings configuration (EARConfig)
    models.py            # Domain models: ModelSpec, RoutingRequest, RoutingDecision
    registry.py          # OpenRouterRegistry, OllamaRegistry, RegistryFactory
    router_engine.py     # IntentClassifier, SuitabilityScorer, RouterEngine
    guardrails.py        # Prompt-injection detector, PII policy, semantic risk scorer
    fallback.py          # FailureClassifier, FallbackPipeline
    metrics.py           # MetricsCollector, SessionSummary
    executor.py          # LLMExecutor, OllamaExecutor, CompositeExecutor
    orchestrator.py      # Unified execution orchestration pipeline
    intent.py            # Advanced intent classifier (embedding + heuristic fallback)
    judge.py             # Judge-based routing classifier using local LLM
    evaluation.py        # Evaluation harness and benchmark suite
    cli.py               # Typer CLI: route, inspect-models, stats (+ aliases)
    mcp_server.py        # MCP stdio transport and tool/resource handlers
    demo_backend.py      # Demo routing replay scenarios and value storytelling
    demo_server.py       # uvicorn-backed local demo HTTP server
tests/
  conftest.py
  test_config.py
  test_models.py
  test_registry.py
  test_router_engine.py
  test_guardrails.py
  test_fallback.py
  test_metrics.py
  test_executor.py
  test_orchestrator.py
  test_intent.py
  test_judge.py
  test_evaluation.py
  test_cli.py
  test_mcp_server.py
  test_demo_backend.py
  test_demo_server.py
webapp/
  package.json           # React + Vite dependencies
  vite.config.js
  src/                   # React routing console components
docs/
  system_prompt.md
  execution_plan.md
  wbs.md
  release-playbook.md
  llm_explorer.html      # Standalone browser-based LLM explorer and demo UI
  usage-guide.md
  project-history.md     # Full commit history and delivery log
  adr/
  releases/
```

## Core Workflow
1. Accept user task input and options (task hint, budget priority, context profile).
2. Run safety prechecks (injection and PII policy).
3. Load model metadata from OpenRouter registry cache.
4. Compute suitability score and candidate ranking.
5. Return model recommendation, rationale, and fallback chain (execution runtime is tracked in E10).
6. Emit session metrics snapshot for observability.

## Routing Model
The router evaluates candidate models using a weighted suitability function:

S = Quality / (Cost * Latency)

Where score inputs are normalized and constrained by policy:
- Context window threshold
- Budget priority
- Safety allowlist and PII policy
- Task-specific boosts (coding, planning, research)

## CLI Commands

Full command names and short aliases are both supported:

```bash
# Route a prompt (full and alias)
ear route "explain quicksort" --task coding --budget medium
ear r "explain quicksort" --task coding --budget medium

# JSON output for scripting
ear route "explain quicksort" --json

# Execute the routed model call
ear route "explain quicksort" --execute

# Inspect cached models
ear inspect-models
ear im

# Session metrics
ear stats
ear s

# Bare invocation: routes with sensible defaults
ear "explain quicksort"
```

## MCP Design
- Tool: `route_and_execute`
- Resources: model performance metrics, cost per session
- Transport: stdio

## Ollama Private Provider

EAR routes PII-containing and injection-risk prompts to a local Ollama instance, ensuring sensitive data never reaches cloud providers.

Configuration:
```bash
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_ENABLED=true
```

Behavior:
- `ollama/<model>` models appear in the registry with `trusted=True` and zero pricing.
- Guardrail-blocked prompts route to Ollama when available instead of hard-blocking.
- PII prompts are restricted to Ollama and vetted cloud providers only.
- If Ollama is unavailable and a prompt is blocked, `GuardrailsBlockedError` is raised (fail-closed).

## Interactive LLM Explorer and Demo UI
- File: `docs/llm_explorer.html`
- Purpose: interactive OpenRouter model table, routing demo, and value storytelling for leadership and investor demos.

What it includes:
- Live model fetch from OpenRouter (`/api/v1/models`) with auto-refresh and last-updated indicator.
- Search, provider pills, min-context, max-cost, and priced/unpriced filters.
- Excel-style sortable table with per-column filters.
- Side-by-side comparison cards for selected models (up to 4).
- Value Story section with 10 routing scenarios: cost savings, latency gains, and safety enforcement.
- **Routing-mode toggle** (Standard / Ollama Private): shows attack scenarios routing to `ollama/llama3` for on-premise data-residency demonstration.
- **Processing progress log**: step-by-step routing decisions with timestamps.

How to run:
1. Open `docs/llm_explorer.html` directly in a browser, or
2. Start the local demo server: `python -m ear.demo_server` (default port 7861)

## Live React Web Console
- Directory: `webapp/`
- Purpose: developer-facing real-time routing visualization built with React and Vite.

How to run:
```bash
# Windows
run_live_webapp.bat

# Linux / macOS
bash run_live_webapp.sh
```
The launcher waits for the Vite dev server to be ready before opening the browser.

## Demo Walkthrough
```bash
# Windows
run_demo_walkthrough.bat

# Linux / macOS
bash run_demo_walkthrough.sh
```
Runs all 10 demo routing scenarios end-to-end and opens the value storytelling view.

## Configuration

Environment variables (minimum required):
```bash
OPENROUTER_API_KEY=<your key>
EAR_REGISTRY_TTL_SECONDS=300
EAR_DEFAULT_BUDGET=medium
EAR_MAX_RETRIES=3
EAR_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
EAR_REQUEST_TIMEOUT_SECONDS=30
```

Optional Ollama private provider:
```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_ENABLED=true
```

Optional judge-based intelligent routing:
```bash
EAR_JUDGE_ENABLED=true
EAR_JUDGE_MODEL=llama3.2
EAR_JUDGE_CONFIDENCE_THRESHOLD=0.6
```

Recommended local setup:
1. Create and activate virtual environment: `python -m venv .venv && .venv\Scripts\activate`
2. Install: `pip install -e .[dev]`
3. Copy `.env.example` to `.env` and populate values.
4. Run tests: `run_tests.bat` (Windows) or `bash run_tests.sh`
5. Run security audits: `run_security_audits.bat` or `bash run_security_audits.sh`

## Quality and Security Requirements
- 100% statement and branch coverage for routing core.
- Deterministic tests with mocked external dependencies.
- Security linting with bandit.
- Dependency auditing with pip-audit.
- No plaintext secret logging.

## Security Report HTML Generation
- Security workflows generate JSON first, then render HTML using sec-report-kit.
- pip-audit workflow outputs: security_reports/pip_audit_latest.html.
- Trivy workflow outputs: security_reports/trivy_latest.html.
- Both HTML files are uploaded in the workflow artifacts alongside JSON and SARIF outputs.
- Local scripts also generate HTML from JSON:
  - run_pip_audit.bat / run_pip_audit.sh
  - run_trivy.bat / run_trivy.sh
  - one-command wrapper: run_security_audits.bat / run_security_audits.sh

## MCP Server: sec-report-kit
Install sec-report-kit locally:

```bash
pip install sec-report-kit
```

Configured MCP server command:

```bash
srk mcp serve --transport stdio
```

Workspace configuration is stored in .vscode/mcp.json.

## Milestones
- M1: Registry and schema baseline ✅
- M2: Router core and CLI ✅
- M3: Guardrails and metrics ✅
- M4: MCP server and CI/CD gates ✅
- M5: Execution runtime and adaptive routing intelligence ✅
- M6: Leadership/investor demo frontend ✅
- M8: Ollama private provider integration ✅
- M9: React console and CLI UX hardening ✅
- M7: Post-launch hardening (PyPI verify, canary, benchmarks, ADRs) ⏳ Pending

## Judge-Based Intelligent Routing

EAR can use a local Ollama LLM as an agentic judge to analyze prompts and make intelligent routing decisions between local and cloud models.

Configuration:
```bash
export EAR_JUDGE_ENABLED=true
export EAR_JUDGE_MODEL=llama3.2
export EAR_JUDGE_CONFIDENCE_THRESHOLD=0.6
```

Behavior:
- Judge analyzes prompt complexity, privacy sensitivity, and quality requirements.
- Returns routing preference (local/cloud) with confidence score and reasoning.
- Multi-dimensional scoring: complexity_score, privacy_score, quality_score.
- Heuristic fallback when judge is unavailable, times out, or returns low confidence.
- Integration with ExecutionOrchestrator filters model candidates based on judge recommendation.
- Requires Ollama to be running locally for judge to function.

Use cases:
- Simple queries → local routing for cost efficiency
- Complex analysis → cloud routing for advanced capabilities
- Privacy-sensitive data → automatic local model preference
- Budget-conscious requests → intelligent cost optimization

## Tests

- 342 tests across 17 test modules
- Enforced 100% statement and branch coverage for all routing, guardrail, judge, and execution logic
- All tests run with mocked external dependencies

```bash
run_tests.bat        # Windows
bash run_tests.sh    # Linux / macOS
```

Reports are written to `coverage_reports/` (HTML, XML, JSON).
- Use `ear r` / `ear im` / `ear s` aliases in examples for brevity.
