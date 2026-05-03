import React, { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_EAR_API_BASE || "";

const TEMPLATE_QUESTIONS = [
  {
    category: "General",
    prompt: "Compare blue-green and canary deployment strategies for a fintech API rollout.",
  },
  {
    category: "General",
    prompt: "Explain the difference between microservices and monolithic architecture.",
  },
  {
    category: "Coding",
    prompt: "Write a Python function to validate email addresses using regex.",
  },
  {
    category: "Research",
    prompt: "What are the latest advancements in quantum computing as of 2026?",
  },
  {
    category: "Local LLM (PII)",
    prompt: "Analyze this patient data: John Smith, SSN 123-45-6789, diagnosed with diabetes on 2026-04-15.",
  },
  {
    category: "Local LLM (Medical)",
    prompt: "Review this medical record: Patient ID 98765, blood pressure 140/90, prescribed metformin 500mg.",
  },
  {
    category: "Local LLM (Sensitive)",
    prompt: "Draft an email about employee performance review for Sarah Johnson, employee ID EMP-2024-1523.",
  },
  {
    category: "Local LLM (Financial)",
    prompt: "Calculate tax implications for income: $125,000 annual salary, account number 4532-1567-8901-2345.",
  },
];

const initialForm = {
  prompt: "",
  taskType: "auto",
  budgetPriority: "medium",
  preferredModel: "",
  execute: true,
};

function formatCurrency(value) {
  const numeric = Number(value || 0);
  return `$${numeric.toFixed(8)}`;
}

function formatMs(value) {
  const numeric = Number(value || 0);
  return `${numeric.toFixed(2)} ms`;
}

function makeLogEntry(message, kind = "info") {
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    message,
    kind,
    time: new Date().toLocaleTimeString(),
  };
}

function toNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export default function App() {
  const [models, setModels] = useState([]);
  const [stats, setStats] = useState(null);
  const [form, setForm] = useState(initialForm);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [activityLog, setActivityLog] = useState([
    makeLogEntry("Console ready. Waiting for your question."),
  ]);

  const hasOverride = useMemo(() => {
    if (!result || !result.requested_model) {
      return false;
    }
    return result.requested_model !== result.selected_model;
  }, [result]);

  const responseMessage = useMemo(() => {
    if (!result) {
      return "";
    }
    if (result.executed === false) {
      return "Route-only mode: no model execution was requested.";
    }
    if (result.response_text) {
      return result.response_text;
    }
    return "Model execution completed, but the provider returned an empty response.";
  }, [result]);

  function appendLog(message, kind = "info") {
    setActivityLog((previous) => [makeLogEntry(message, kind), ...previous].slice(0, 16));
  }

  function appendEarPhaseLogs(responsePayload) {
    const guardrails = responsePayload.guardrails || {};
    const guardrailSummary = [
      `passed=${String(guardrails.passed)}`,
      `injection=${String(guardrails.injection_detected)}`,
      `pii=${String(guardrails.pii_detected)}`,
      `risk=${toNumber(guardrails.risk_score).toFixed(2)}`,
    ].join(", ");

    appendLog(`Phase 1/4 Guardrails: ${guardrailSummary}`);
    appendLog(
      `Phase 2/4 Routing: selected ${responsePayload.selected_model} (${responsePayload.provider})`,
    );

    const fallbackTrace = responsePayload.fallback_trace || [];
    if (fallbackTrace.length > 0) {
      appendLog(
        `Phase 3/4 Execution: ${fallbackTrace.length} attempt(s) via ${fallbackTrace.join(" -> ")}`,
      );
    } else {
      appendLog("Phase 3/4 Execution: route-only preview (no provider call).", "warn");
    }

    if (responsePayload.requested_model && !responsePayload.requested_model_applied) {
      appendLog(
        `Preference override: requested ${responsePayload.requested_model}, routed to ${responsePayload.selected_model}`,
        "warn",
      );
    }

    appendLog(
      `Phase 4/4 Render: ${responsePayload.total_tokens} tokens, ${formatCurrency(responsePayload.estimated_cost_usd)}, ${formatMs(responsePayload.end_to_end_latency_ms)}`,
      "success",
    );
  }

  useEffect(() => {
    document.body.classList.toggle("app-busy", loading);
    return () => {
      document.body.classList.remove("app-busy");
    };
  }, [loading]);

  useEffect(() => {
    if (!loading) {
      setProgress((current) => (current >= 100 ? current : 0));
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      setProgress((current) => {
        if (current >= 92) {
          return current;
        }
        return current + 8;
      });
    }, 280);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [loading]);

  async function loadModels() {
    try {
      appendLog("GET /live/models - fetching available LLMs");
      const response = await fetch(`${API_BASE}/live/models`);
      const payload = await response.json();
      if (!response.ok || payload.error) {
        throw new Error(payload.reason || payload.error || "Unable to load models.");
      }
      setModels(payload.models || []);
      appendLog(`Model catalog loaded: ${payload.models?.length || 0} models available`, "success");
    } catch (loadError) {
      setError(loadError.message);
      appendLog(`Model catalog failed: ${loadError.message}`, "error");
    }
  }

  async function loadStats() {
    try {
      appendLog("GET /live/stats - refreshing session telemetry");
      const response = await fetch(`${API_BASE}/live/stats`);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error("Failed to load stats.");
      }
      setStats(payload);
      appendLog(`Stats refreshed: ${payload.total_calls} calls tracked`, "success");
    } catch {
      setStats(null);
      appendLog("Stats refresh unavailable.", "warn");
    }
  }

  useEffect(() => {
    loadModels();
    loadStats();
  }, []);

  function onChange(field, value) {
    setForm((previous) => ({
      ...previous,
      [field]: value,
    }));
  }

  async function onSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setProgress(12);
    setError("");
    setResult(null);
    appendLog("Validating prompt and building EAR request payload...");

    const payload = {
      prompt: form.prompt,
      budget_priority: form.budgetPriority,
      task_type: form.taskType === "auto" ? null : form.taskType,
      preferred_model: form.preferredModel || null,
      execute: form.execute,
    };

    try {
      appendLog("POST /live/route-execute - handing request to EAR router");
      setProgress(28);
      const response = await fetch(`${API_BASE}/live/route-execute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      appendLog("Awaiting EAR decision and provider execution...");
      setProgress(70);
      const responsePayload = await response.json();
      if (!response.ok || responsePayload.error) {
        const ERROR_LABELS = {
          live_mode_unavailable:
            "EAR could not reach the model registry. " +
            (responsePayload.reason || "Check your network connection and OPENROUTER_API_KEY."),
          all_candidates_exhausted:
            "Every model in the fallback chain failed. The provider may be overloaded — please retry.",
          guardrails_blocked:
            "Request blocked by safety guardrails: " + (responsePayload.reason || ""),
          no_models_available:
            "No models are currently available from the registry. Retry in a moment.",
        };
        throw new Error(
          ERROR_LABELS[responsePayload.error] ||
            responsePayload.reason ||
            responsePayload.error ||
            "Execution failed."
        );
      }
      setResult(responsePayload);
      setProgress(92);
      appendLog(
        `EAR selected ${responsePayload.selected_model} with ${responsePayload.total_tokens} total tokens`,
        "success",
      );
      appendEarPhaseLogs(responsePayload);
      await loadStats();
      setProgress(100);
      appendLog("Response rendered to UI.", "success");
    } catch (submitError) {
      setError(submitError.message);
      appendLog(`Execution failed: ${submitError.message}`, "error");
    } finally {
      window.setTimeout(() => {
        setLoading(false);
      }, 250);
    }
  }

  return (
    <div className={loading ? "page-shell is-loading" : "page-shell"}>
      <header className="hero">
        <p className="eyebrow">Live Data Only</p>
        <h1>EAR Routing Console</h1>
        <p>
          Ask any question. EAR selects the best model, can override your preference when policy
          or scoring requires it, and returns full transparency for every decision.
        </p>
        <div className="hero-status-row">
          <div className="progress-shell" aria-live="polite">
            <div className="progress-track">
              <div className="progress-bar" style={{ width: `${progress}%` }} />
            </div>
            <p className="progress-copy">
              {loading ? `Processing request... ${progress}%` : "Ready for the next request."}
            </p>
          </div>
        </div>
      </header>

      <main className="layout-grid">
        <section className="panel prompt-panel">
          <h2>Ask a Question</h2>
          <form onSubmit={onSubmit}>
            <label>
              Template Questions (optional)
              <select
                value=""
                onChange={(event) => {
                  if (event.target.value) {
                    onChange("prompt", event.target.value);
                  }
                }}
              >
                <option value="">-- Select a template or type your own --</option>
                {TEMPLATE_QUESTIONS.map((template, idx) => (
                  <option value={template.prompt} key={idx}>
                    [{template.category}] {template.prompt.substring(0, 60)}
                    {template.prompt.length > 60 ? "..." : ""}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Prompt
              <textarea
                value={form.prompt}
                onChange={(event) => onChange("prompt", event.target.value)}
                placeholder="Example: Compare blue-green and canary deployment for a fintech API rollout."
                required
              />
            </label>

            <div className="input-row">
              <label>
                Task Type
                <select
                  value={form.taskType}
                  onChange={(event) => onChange("taskType", event.target.value)}
                >
                  <option value="auto">Auto</option>
                  <option value="simple">Simple</option>
                  <option value="planning">Planning</option>
                  <option value="coding">Coding</option>
                  <option value="research">Research</option>
                </select>
              </label>

              <label>
                Budget
                <select
                  value={form.budgetPriority}
                  onChange={(event) => onChange("budgetPriority", event.target.value)}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </label>
            </div>

            <label>
              Preferred Model (EAR may override)
              <select
                value={form.preferredModel}
                onChange={(event) => onChange("preferredModel", event.target.value)}
              >
                <option value="">No preference</option>
                {models.map((model) => (
                  <option value={model.id} key={model.id}>
                    {model.id}
                  </option>
                ))}
              </select>
            </label>

            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={form.execute}
                onChange={(event) => onChange("execute", event.target.checked)}
              />
              Execute model call (off = route preview only)
            </label>

            <button type="submit" disabled={loading}>
              {loading ? "Routing..." : "Route With EAR"}
            </button>
          </form>
          {error && <p className="error-banner">{error}</p>}
        </section>

        <section className="panel result-panel">
          <h2>Routing Transparency</h2>
          {!result && <p className="muted">Submit a prompt to see live routing data.</p>}

          {result && (
            <>
              <div className="kpi-grid">
                <article>
                  <h3>Selected Model</h3>
                  <p>{result.selected_model}</p>
                </article>
                <article>
                  <h3>Provider</h3>
                  <p>{result.provider}</p>
                </article>
                <article>
                  <h3>Task Type</h3>
                  <p>{result.task_type}</p>
                </article>
                <article>
                  <h3>Budget</h3>
                  <p>{result.budget_priority}</p>
                </article>
              </div>

              <div className={hasOverride ? "override-card active" : "override-card"}>
                <h3>Preference Resolution</h3>
                <p>
                  Requested: <strong>{result.requested_model || "No preference"}</strong>
                </p>
                <p>
                  Applied: <strong>{String(result.requested_model_applied)}</strong>
                </p>
                <p>{result.transparency_note}</p>
              </div>

              <div className="kpi-grid">
                <article>
                  <h3>Prompt Tokens</h3>
                  <p>{result.prompt_tokens}</p>
                </article>
                <article>
                  <h3>Completion Tokens</h3>
                  <p>{result.completion_tokens}</p>
                </article>
                <article>
                  <h3>Total Tokens</h3>
                  <p>{result.total_tokens}</p>
                </article>
                <article>
                  <h3>Estimated Cost</h3>
                  <p>{formatCurrency(result.estimated_cost_usd)}</p>
                </article>
                <article>
                  <h3>Latency</h3>
                  <p>{formatMs(result.end_to_end_latency_ms)}</p>
                </article>
              </div>

              <article className="detail-card">
                <h3>Decision Reason</h3>
                <p>{result.reason}</p>
                <h4>Fallback Chain</h4>
                <p>{(result.fallback_chain || []).join(" -> ") || "None"}</p>
                <h4>Fallback Trace</h4>
                <p>{(result.fallback_trace || []).join(" -> ") || "None"}</p>
              </article>

              <article className="detail-card">
                <h3>Guardrails</h3>
                <p>Passed: {String(result.guardrails?.passed)}</p>
                <p>Injection Detected: {String(result.guardrails?.injection_detected)}</p>
                <p>PII Detected: {String(result.guardrails?.pii_detected)}</p>
                <p>Risk Score: {result.guardrails?.risk_score}</p>
                <p>Reason: {result.guardrails?.reason || "None"}</p>
              </article>

              <article className="detail-card response-card">
                <h3>Model Response</h3>
                <pre>{responseMessage}</pre>
              </article>
            </>
          )}
        </section>
      </main>

      <footer className="footer-strip">
        <article>
          <h3>Live Session Stats</h3>
          {!stats && <p className="muted">No stats yet.</p>}
          {stats && (
            <div className="stats-row">
              <p>Total Calls: {stats.total_calls}</p>
              <p>Total Cost: {formatCurrency(stats.total_cost_usd)}</p>
              <p>Total Latency: {formatMs(stats.total_latency_ms)}</p>
            </div>
          )}
        </article>
        <article className="activity-card">
          <h3>Activity Log</h3>
          <div className="activity-log" aria-live="polite">
            {activityLog.map((entry) => (
              <div className={`activity-entry ${entry.kind}`} key={entry.id}>
                <span className="activity-time">{entry.time}</span>
                <span className="activity-message">{entry.message}</span>
              </div>
            ))}
          </div>
        </article>
      </footer>
    </div>
  );
}
