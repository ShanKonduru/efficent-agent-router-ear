# EAR — Project History Report

**Repository:** `efficient-agent-router-ear`  
**Author:** SHAN (ShanKonduru@gmail.com)  
**Baseline Commit:** `e48d7eafe2268139f812a651c99972c73bb919e0`  
**Latest Commit:** `afa1f1b423194f980124205e9b9f33b49aa56daa`  
**Total Commits Since Baseline:** 64  
**Report Generated:** 2026-05-03  

---

## Overview

The Efficient Agent Router (EAR) project was conceived and fully delivered between **2026-05-01** and **2026-05-03** — a 3-day sprint from blank workspace to a production-ready Python package with CLI, MCP server, live web console, fallback pipelines, guardrails, metrics, security tooling, and demo infrastructure.

---

## Baseline — Foundation Planning

| Field | Value |
|---|---|
| **Commit** | `e48d7eafe2268139f812a651c99972c73bb919e0` |
| **Date / Time** | 2026-05-01 08:10:02 +0530 |
| **Subject** | `chore: baseline planning and workspace setup` |

**What was established:**
- `.gitignore` (excluding `.env`)
- `README.md` with architecture, stack, and delivery strategy
- `docs/system_prompt.md` — reformatted to Markdown
- `docs/execution_plan.md` — features, stories, tasks, milestones (9 epics, 35 tasks)
- `docs/wbs.md` — full Work Breakdown Structure with status markers and estimates
- `docs/adr/0001` — Architecture Decision Record: asyncio, Typer, CLI-first, clean architecture
- `.github/copilot-instructions.md` — project-wide coding guidelines
- `.github/instructions/python-router.instructions.md` — Python file rules
- `.github/prompts/` — user story breakdown and routing rule drafting prompts
- `.github/skills/ear-delivery-planning/SKILL.md` — planning workflow skill

**Files added:** 11 files, 929 insertions

---

## Day 1 — 2026-05-01

### 08:11:37 — Commit `984b4912`
**`chore: replace minimal .gitignore with standard Python gitignore`**  
Replaced the placeholder `.gitignore` with a comprehensive standard Python ignore ruleset.

---

### 08:13:03 — Commit `0589c36f`
**`fix: re-encode .gitignore as UTF-8 without BOM`**  
Fixed `.gitignore` encoding so Git parses ignore rules correctly (BOM was silently preventing pattern matching).

---

### 08:23:59 — Commit `0e7b8295` — **E1: Foundation Complete**
**`feat: project scaffolding — E1 Foundation complete`**

First substantive feature commit — full package scaffold stood up:

| Added | Detail |
|---|---|
| `pyproject.toml` | Full dependency set: `httpx`, `typer`, `pydantic-settings`, `mcp` |
| `.env.example` | All required/optional config vars documented |
| `src/ear/__init__.py` | Package root |
| `src/ear/config.py` | Pydantic-settings configuration model |
| `src/ear/models.py` | Domain models: `ModelSpec`, `RoutingRequest`, `RoutingDecision`, `TaskType`, `BudgetPriority` |
| `src/ear/registry.py` | Model registry (initial stub) |
| `src/ear/router_engine.py` | Router engine (initial scaffold) |
| `src/ear/guardrails.py` | Guardrails stub |
| `src/ear/fallback.py` | Fallback stub |
| `src/ear/metrics.py` | Metrics stub |
| `src/ear/cli.py` | Typer CLI scaffold |
| `src/ear/mcp_server.py` | MCP server stub |
| `tests/conftest.py` | Shared fixtures |
| `tests/test_*.py` | Initial test files for all modules |

**Result:** 36 scaffold tests pass; E1 exit criteria met.  
**Files added:** 21 files, 1,033 insertions

---

### 08:45:34 — Commit `cc527f2f` — **CI & OOP Registry**
**`ci: add scripts, workflows, and OOP registry`**

Complete CI/CD pipeline and automation layer established:

| Category | Detail |
|---|---|
| **Local scripts** | `run_tests.bat/sh` — pytest with branch coverage + HTML/XML/JSON reports |
| | `run_pip_audit.bat/sh` — pip-audit with JSON and CycloneDX SBOM |
| | `run_trivy.bat/sh` — Trivy filesystem scan (table, JSON, SARIF) |
| **GitHub Actions** | `ci.yml` — pytest on 3 OS × 2 Python versions + Codecov upload |
| | `pip-audit.yml` — daily dependency vulnerability scan |
| | `trivy.yml` — weekly filesystem scan; SARIF uploaded to GitHub Security tab |
| | `publish-testpypi.yml` — build + publish on pre-release tags |
| | `publish-pypi.yml` — build + publish on stable tags, creates GitHub Release |
| **Registry refactor** | `BaseModelRegistry` ABC, `OpenRouterRegistry`, `RegistryFactory` (open/closed principle), `RegistryClient` backward-compat alias |
| **Git attributes** | `.gitattributes` — LF for `.sh/.py/.yml`, CRLF for `.bat` |

**Files added/modified:** 14 files, 1,140 insertions

---

### 09:41:41 — Commit `e1b9aa2e` — **100% Branch Coverage**
**`test+fix: reach 100% branch coverage`**

- Fixed registry `X-Title` header: em-dash replaced with ASCII hyphen (httpx enforces ASCII header values; `UnicodeEncodeError` on U+2014)
- Expanded `test_registry.py` from 2 stubs to 14 deterministic mocked tests (cache hit/miss/stale, `parse_model` edge cases, headers, factory)
- Added `tests/test_cli.py` with 6 tests covering app, command stubs, `main()`, `__main__`
- Added missing `NotImplemented` branch tests in `test_fallback`, `test_guardrails`, `test_router_engine`

**Result:** 62/62 tests pass, **100% branch coverage achieved**  
**Files modified:** 6 files, 282 insertions

---

### 09:41:55 — Commit `d7652e67`
**`fix: stabilize Trivy scripts for reliable local execution`**

- Single-pass JSON scan (was triple: table + JSON + SARIF) to avoid timeouts
- Default skip-dirs: `.venv`, `.git`, `coverage_reports`, `security_reports`
- Scanners: `vuln,misconfig` (secret scanning disabled to avoid `.pyc` parse errors)
- Windows `.bat`: `EnableDelayedExpansion` + `!TRIVY_EXE!` inside `IF` block to fix PATH miss
- **Result:** `run_trivy.bat` completes cleanly, 0 HIGH/CRITICAL findings

**Files modified:** 2 files, 29 insertions, 81 deletions

---

### 11:06:20 — Commit `1912926d`
**`fix(ci): eliminate warning-driven pytest failures`**

- Stabilized `test_cli.py` `__main__` execution by removing `ear.cli` from `sys.modules` before `runpy.run_module`
- Set `pytest-asyncio` default fixture loop scope explicitly to `function`
- Silenced known coverage module-not-measured warning for deterministic CI logs

**Files modified:** 2 files, 6 insertions

---

### 11:10:48 — Commit `f1eae128`
**`ci: gate PyPI/TestPyPI publish on 100% test coverage`**

- PyPI publish now requires stable tag and enforces `pyproject` version == tag version
- PyPI: `--cov-fail-under=100` must pass before publish runs
- TestPyPI: triggered on every push with same 100% coverage gate

**Files modified:** 2 workflow files, 85 insertions, 21 deletions

---

### 11:11:55 — Commit `9713052e`
**`test: fix flaky stale-cache registry assertion in CI`**

Used TTL-relative monotonic timestamp in stale-cache test instead of hardcoded `0.0` so cache refresh is deterministically attempted across all CI runners.

**Files modified:** 1 file, 3 insertions

---

### 16:44:36 — Commit `9d361a5c` — **E3: Predictive Routing Engine**
**`feat(E3): implement Predictive Routing Engine`**

Core routing intelligence implemented:

| Component | Detail |
|---|---|
| **IntentClassifier (T2.1)** | Rule-based `classify()`: fenced code blocks → CODING; keyword vote across CODING/PLANNING/RESEARCH; tie or no signal → SIMPLE |
| **SuitabilityScorer (T2.2)** | Score formula: `S = quality / (cost_weighted + ε)`; quality = log-normalized context_length + 0.3 affinity bonus for preferred coding models; cost weighted by `BUDGET_COST_WEIGHTS[budget_priority]` |
| **RouterEngine (T2.3)** | `_filter_eligible()`: mega-context guard for prompts >100k chars → restricted to Gemini 1.5 Pro, Claude Opus/Sonnet; `_rank_candidates()`: descending score, tie-break by ascending context_length; `decide()`: classify → filter → score → rank → `RoutingDecision` with fallback chain |
| **Tests (T2.4)** | 28 new tests replacing 8 stubs; all 4 `TaskType` branches, scoring affinity, filter logic, ranking, `decide()` end-to-end |

**Files modified:** 2 files, 393 insertions, 48 deletions

---

### 18:38:12 — Commit `f181cee4`
**`updated version to 0.3.0`**  
Version bump to `0.3.0` in `pyproject.toml`.

---

### 19:02:49 — Commit `03a18539`
**`fix(release): rename distribution to ear-shankonduru for PyPI/TestPyPI`**  
Unique publishable name for PyPI namespace conflict avoidance.

---

### 19:06:18 — Commit `8083dfc8`
**`chore(release): rename distribution to efficient-agent-router-ear`**  
Final canonical distribution name set in `pyproject.toml` and CI workflows.

---

### 19:23:37 — Commit `e871a62f`
**`chore(release): finalize 0.5.0 publish configuration`**  
Version bump to `0.5.0`; TestPyPI workflow simplified.

---

### 19:41:24 — Commit `7a6ebfad`
**`fix(ci): accept 0.5.0 and v0.5.0 release tags`**  
PyPI publish workflow updated to accept both prefixed and non-prefixed tag formats.

---

### 19:55:37 — Commit `6539aa11`
**`chore(release): bump version to 0.7.0`**  
Version bump to `0.7.0`.

---

### 20:10:19 — Commit `41216343`
**`fix(ci): ignore CVE-2026-3219 in pip-audit gate`**  
Added explicit CVE allowlist entry in `pip-audit.yml` to unblock CI while upstream fix is tracked.

---

### 20:12:20 — Commit `5758ba71`
**`fix(ci): run PyPI publish step by wiring verify job outputs`**  
Fixed job output wiring so the publish step actually runs after verification succeeds.

---

### 20:14:08 — Commit `25d0b272`
**`chore(release): prepare 0.8.0`**  
Version bump to `0.8.0`.

---

### 21:13:37 — Commit `4a6fe565`
**`chore(release): bump version to 0.10.0`**  
Version jump to `0.10.0` reflecting feature completeness milestone.

---

### 21:38:36 — Commit `49b92df6`
**`docs(ci): add release playbook, preflight workflow, and v0.10.0 notes draft`**

| Added | Detail |
|---|---|
| `.github/workflows/release-preflight.yml` | Pre-publish checklist workflow (115 lines) |
| `docs/release-playbook.md` | Step-by-step release procedures (163 lines) |
| `docs/releases/v0.10.0-release-notes-draft.md` | Draft release notes for v0.10.0 (82 lines) |

**Files added:** 3 files, 360 insertions

---

### 21:40:55 — Commit `a601939c`
**`docs: add complete env sample and align config variable docs`**  
Added `env.sample` with all config variables; updated `README.md`.

---

### 21:46:38 — Commit `a67fa9c3`
**`removed unwanted files`**  
Removed `env.sample` (superseded by `.env.example`); minor README cleanup.

---

### 21:50:07 — Commit `fe3d3f50` — **E5: Fallback Pipeline**
**`feat(E5): implement fallback pipeline with retries and cascade`**

Production-grade failure handling implemented:

| Component | Detail |
|---|---|
| **FailureClassifier** | Transient detection: HTTP 429/5xx + timeout |
| **FallbackPipeline.execute()** | Ordered candidate chain with bounded exponential backoff per model |
| **Retry budget** | Per-model retry budget enforced |
| **De-duplication** | Fallback chain de-duplicated |
| **AllCandidatesExhausted** | Exception raised with full attempt history |
| **Tests** | Comprehensive branch-complete E5 tests replacing stubs |

**Files modified:** 2 files, 326 insertions, 23 deletions

---

### 22:05:49 — Commit `f2dca1f0`
**`chore(release): bump version to 0.10.1`**

---

### 23:57:32 — Commit `c3d4f360` — **Security Reporting**
**`feat(security): add sec-report-kit HTML reporting and MCP config`**

| Added | Detail |
|---|---|
| `.vscode/mcp.json` | MCP server config for sec-report-kit local tooling |
| CI enhancements | HTML report generation from pip-audit and Trivy JSON in both CI workflows |
| Local scripts | HTML generation wrappers: `run_security_audits.bat/sh` |
| README | Documents local and CI HTML reporting behavior |

**Files added/modified:** 10 files, 219 insertions

---

## Day 2 — 2026-05-02

### 00:04:07 — Commit `f6a7273b`
**`docs(planning): refresh WBS and execution plan status inline`**  
E1/E2/E3/E5 marked completed; E9 and related milestones marked in-progress; E4/E6/E7/E8 remain pending; milestone map updated.

---

### 00:04:57 — Commit `d4a58939`
**`docs(planning): set current execution order`**  
Aligned recommended order: E4 → E6 → E7 → E8 → CI hardening; reflected in both WBS and execution plan.

---

### 00:13:34 — Commit `04349a9c` — **E4/E6/E7/E8: CLI, Guardrails, Metrics, MCP**
**`feat(delivery): implement E4-E8 with tests and harden CI gates`**

Four epics delivered in one commit:

| Epic | Components |
|---|---|
| **E4 — CLI** | `route`, `inspect-models`, `stats` commands with JSON and human-readable output; per-route metrics recorded on CLI decision path |
| **E6 — Guardrails** | Prompt-injection detection; PII detection; vetted-provider filtering enforced for PII scenarios |
| **E7 — Metrics** | Thread-safe metrics collector; summary, reset, and singleton accessor |
| **E8 — MCP** | Full MCP server implementation with tool handlers and transport layer |

---

### 00:17:29 — Commit `e811ec19`
**`docs(progress): refresh project status and release docs`**  
Progress documentation updated to reflect E4–E8 delivery.

---

### 00:34:54 — Commit `4f1a2ecf` — **E9: Security CI Hardening**
**`ci(security): close E9 validation and remove temporary exceptions`**  
Removed all temporary CVE allow-list exceptions; final CI security gates closed.

---

### 00:38:48 — Commit `ae9f22b4`
**`docs(wbs): mark E9 and M4 complete — all epics now delivered`**  
WBS updated: E9 complete, Milestone 4 complete. All 9 originally planned epics delivered.

---

### 00:44:10 — Commit `1859ba77`
**`chore(release): bump version to 0.10.2`**

---

### 01:17:00 — Commit `cf70daa4` — **Live LLM Explorer UI**
**`feat(ui): add live OpenRouter LLM explorer and roadmap extensions`**

- `docs/llm_explorer.html` — standalone browser-based live LLM model explorer
  - Fetches live model data from OpenRouter API
  - Filters by capability, pricing tier, and context window
  - Visualizes model suitability scores in real-time
- Roadmap extensions documented for future phases

---

### 01:20:03 — Commit `10207c1f`
**`docs(sync): align roadmap and release notes with 0.10.3 state`**  
Documentation synchronized with current feature state.

---

### 01:23:47 — Commit `e49d0e2a`
**`chore: add release.py automation script`**  
Release automation script added.

---

### 01:43:44 — Commit `ab1b1ea8`
**`Revert "chore: add release.py automation script"`**  
Release script reverted (premature; caused CI complications).

---

### 01:47:28 — Commit `dcfe2942`
**`chore: add dev setup prompt and update dependencies`**  
Development setup prompt added; dependencies updated in `pyproject.toml`.

---

### 01:50:30 — Commit `b231e1be`
**`chore: add /init-project prompt for blank project bootstrap`**  
Copilot prompt added for bootstrapping new projects from scratch.

---

### 22:13:38 — Commit `f9677361` — **E10: Unified Execution Runtime**
**`feat: implement unified execution runtime (E10 F9)`**

- Unified async execution runtime integrating router, fallback, guardrails, and metrics into a single call path
- Orchestrator layer connecting all components end-to-end
- Tests covering full orchestration flow

---

### 22:40:33 — Commit `85d45bf9` — **T9.6: Advanced Intent Classifier**
**`feat(T9.6): add advanced intent classifier with embedding/fallback support`**

- Extended `IntentClassifier` with embedding-based classification support
- Graceful fallback to rule-based classification when embeddings unavailable
- Configurable similarity thresholds per task type

---

### 23:03:11 — Commit `c1b1c519` — **T9.7: Semantic Injection Risk Scoring**
**`feat(T9.7): add semantic injection risk scoring with reason codes`**

- Semantic injection risk scorer added to guardrails layer
- Risk scored on sliding scale with structured reason codes
- Reason codes logged in structured form for audit trail

---

### 23:04:07 — Commit `f34e91f8`
**`chore: bump version to 0.10.5`**

---

### 23:07:15 — Commit `a91852b7` — **T9.8: Mini-Controller Routing Hints**
**`feat(T9.8): add strict mini-controller routing hints`**

- Mini-controller layer added: inspects routing decisions and emits override hints
- Hints consumed by `RouterEngine` for latency-sensitive and cost-sensitive fast paths
- Fully tested with deterministic hint scenarios

---

### 23:08:55 — Commit `dd860468` — **T9.9: Evaluation Harness**
**`feat(T9.9): add evaluation harness and benchmark suite`**

- Evaluation harness (`src/ear/evaluation.py`) for offline routing quality benchmarking
- Benchmark suite with labeled routing scenarios and expected model selections
- Precision/recall metrics computed per task type and budget priority
- Results output as structured JSON for CI comparison

---

### 23:11:38 — Commit `c3fa58f8`
**`chore: bump version to 0.10.6`**

---

### 23:16:13 — Commit `24461a70` — **E11: Demo Backend & Value Storytelling**
**`feat(E11): add demo backend endpoints and value storytelling views`**

- `src/ear/demo_backend.py` — demo routing endpoints with 10 replay scenarios
- Value story views per scenario: cost savings, latency improvements, safety enforcement
- Live API routes: `/demo/route`, `/demo/story`, `/demo/scenarios`
- HTML views in `docs/llm_explorer.html` updated with Value Story section

---

### 23:17:01 — Commit `f0a7051b`
**`chore(E11): add one-click demo walkthrough scripts`**

- `run_demo_walkthrough.bat` / `run_demo_walkthrough.sh` — launches demo server and opens browser
- Walks through all 10 routing scenarios automatically

---

### 23:17:56 — Commit `ab53f2bb`
**`chore: bump version to 0.10.7`**

---

### 23:24:48 — Commit `32f705ec`
**`feat(E11): expose local demo server and complete walkthrough`**

- `src/ear/demo_server.py` — `uvicorn`-backed local HTTP server exposing all demo endpoints
- Walkthrough scripts updated to target local server
- 35 tests pass; 100% coverage on `demo_backend.py` and `demo_server.py`

---

### 23:44:47 — Commit `8525c1ce`
**`chore(release): bump version to 0.10.8`**

---

### 23:49:06 — Commit `c3255a83`
**`chore(release): bump version to 0.10.9`**

---

### 23:51:01 — Commit `4ecb5626`
**`chore(release): bump version to 0.10.10`**

---

## Day 3 — 2026-05-03

### 07:15:16 — Commit `3caa65c1`
**`fix(llm_explorer): display human-friendly label for guardrail-blocked scenarios`**

- `llm_explorer.html` updated to render "Blocked by Guardrails" label instead of raw internal model ID for safety-rejected routing scenarios

---

### 07:22:00 — Commit `f507795d`
**`docs(planning): add E12-E16 post-launch next steps to WBS and execution plan`**

- WBS extended with E12–E16 roadmap epics: analytics dashboard, multi-tenant API, fine-tuned router model, streaming support, plugin architecture
- Execution plan updated with sequencing rationale for post-launch phases

---

### 07:41:15 — Commit `c076f6dd` — **E17: Ollama Private Provider**
**`feat(ollama): implement private provider integration for safety routing (E17)`**

- Ollama local model provider registered in `RegistryFactory`
- `ollama/llama3` eligible as on-premise routing target
- Safety-sensitive scenarios can route to local Ollama instead of being hard-blocked
- Enforces data-residency requirements (no PII sent to cloud providers)

---

### 07:55:14 — Commit `572f8822` — **Demo: Ollama Routing Mode**
**`feat(demo): add routing-mode toggle for standard vs Ollama private story`**

- `OLLAMA_REPLAY_SCENARIOS` added to `demo_backend.py`: same 10 scenarios but the three attack scenarios route to `ollama/llama3` instead of hard-blocking
- `_replay_route_response` handles `ollama/` prefix with on-premise narrative
- `DemoRequestRouter` accepts `?mode=ollama` query param for all `/demo/*` endpoints
- `llm_explorer.html`: segmented toggle (Standard / Ollama Private) in Value Story section
- `FALLBACK_SCENARIOS_OLLAMA` client-side fallback dataset added
- `formatEarModel` pretty-prints `ollama/` prefix; routing narrative updated
- 35 tests pass; 100% coverage maintained

---

### 08:12:42 — Commit `33add0ae` — **CLI Aliases**
**`feat(cli): add command aliases and default route command`**

- Short aliases added for all CLI commands (e.g., `ear r` for `ear route`, `ear im` for `ear inspect-models`, `ear s` for `ear stats`)
- Default command: bare `ear` invocation now routes with sensible defaults

---

### 08:15:35 — Commit `26d8e85d`
**`chore: bump version to 0.10.11`**

---

### 08:21:38 — Commit `ae1134ed`
**`test: restore 100% coverage after CLI alias changes`**  
Test suite updated to cover new alias entry points and default command path.

---

### 08:22:13 — Commit `3d9995fb`
**`chore: bump version to 0.10.12`**

---

### 11:24:21 — Commit `4311c7de` — **E12: Live React Web Console**
**`feat(web): add live EAR React console and launchers`**

- `webapp/` directory added with full React/Vite application
  - `webapp/src/` — React components for live routing console
  - `webapp/package.json` — Vite, React dependencies
  - `webapp/vite.config.js` — Vite configuration
- `run_live_webapp.bat` / `run_live_webapp.sh` — one-click launchers
- Console connects to local demo server; real-time routing visualization

---

### 11:27:56 — Commit `c5e16a08`
**`fix(web): wait for Vite before opening browser`**  
Launcher scripts updated to wait for Vite dev server readiness before opening the browser window.

---

### 11:38:54 — Commit `afa1f1b4` — **Latest**
**`feat(ui): add processing progress log and quiet client disconnects`**

- Progress log panel added to `llm_explorer.html`: shows step-by-step routing decisions as they happen
- Client disconnect events (e.g., browser tab close) handled gracefully — no noisy server-side exceptions logged
- UX polish: loading indicators, step timestamps, collapse/expand log panel

---

## Summary Statistics

| Metric | Value |
|---|---|
| **Total commits since baseline** | 64 |
| **Active development days** | 3 (2026-05-01 to 2026-05-03) |
| **First commit date/time** | 2026-05-01 08:10:02 +0530 |
| **Latest commit date/time** | 2026-05-03 11:38:54 +0530 |
| **Final version** | 0.10.12 |

### Epics Delivered

| Epic | Description | Status |
|---|---|---|
| E1 | Foundation — package scaffold, domain models, config | ✅ Complete |
| E2 | OOP Registry with OpenRouter integration | ✅ Complete |
| E3 | Predictive Routing Engine — intent classification, suitability scoring | ✅ Complete |
| E4 | CLI — route, inspect-models, stats commands | ✅ Complete |
| E5 | Fallback Pipeline — retries, cascade, exponential backoff | ✅ Complete |
| E6 | Guardrails — prompt injection detection, PII filtering | ✅ Complete |
| E7 | Metrics — thread-safe collector, summary, reset | ✅ Complete |
| E8 | MCP Server — transport layer and tool handlers | ✅ Complete |
| E9 | Security CI Hardening — pip-audit, Trivy, HTML reports | ✅ Complete |
| E10 | Unified Execution Runtime — orchestrator, async pipeline | ✅ Complete |
| E11 | Demo Infrastructure — backend, server, walkthrough scripts | ✅ Complete |
| E12 | Live React Web Console — Vite/React routing visualizer | ✅ Complete |
| E17 | Ollama Private Provider — on-premise safety routing | ✅ Complete |
| T9.6 | Advanced Intent Classifier with embedding support | ✅ Complete |
| T9.7 | Semantic Injection Risk Scoring with reason codes | ✅ Complete |
| T9.8 | Mini-Controller Routing Hints | ✅ Complete |
| T9.9 | Evaluation Harness and Benchmark Suite | ✅ Complete |

### CI/CD Gates Established

- `pytest` on 3 OS × 2 Python versions (GitHub Actions)
- **100% statement and branch coverage** enforced as publish gate
- Daily `pip-audit` with JSON + CycloneDX SBOM artifacts
- Weekly Trivy filesystem scan with SARIF upload to GitHub Security tab
- Release preflight workflow with version-tag consistency check
- HTML security reports generated in CI and locally

### Key Architectural Decisions

- **asyncio** for all I/O-bound operations (OpenRouter API, model calls)
- **Typer** for CLI with command aliases and JSON output mode
- **Pydantic v2** for all domain models and configuration (fail-closed on invalid input)
- **httpx** async client for model provider HTTP calls
- **Clean architecture**: transport layer (CLI/MCP) contains zero routing logic
- **Open/closed registry**: new providers added via `RegistryFactory` without modifying existing code
- **Fail-closed guardrails**: malformed inputs and unvetted providers rejected by default
- **Structured decision logging**: every routing decision records intent, candidates, scores, and selected model
