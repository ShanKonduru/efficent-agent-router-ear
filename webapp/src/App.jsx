import React, { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_EAR_API_BASE || "";

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

export default function App() {
  const [models, setModels] = useState([]);
  const [stats, setStats] = useState(null);
  const [form, setForm] = useState(initialForm);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const hasOverride = useMemo(() => {
    if (!result || !result.requested_model) {
      return false;
    }
    return result.requested_model !== result.selected_model;
  }, [result]);

  async function loadModels() {
    try {
      const response = await fetch(`${API_BASE}/live/models`);
      const payload = await response.json();
      if (!response.ok || payload.error) {
        throw new Error(payload.reason || payload.error || "Unable to load models.");
      }
      setModels(payload.models || []);
    } catch (loadError) {
      setError(loadError.message);
    }
  }

  async function loadStats() {
    try {
      const response = await fetch(`${API_BASE}/live/stats`);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error("Failed to load stats.");
      }
      setStats(payload);
    } catch {
      setStats(null);
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
    setError("");
    setResult(null);

    const payload = {
      prompt: form.prompt,
      budget_priority: form.budgetPriority,
      task_type: form.taskType === "auto" ? null : form.taskType,
      preferred_model: form.preferredModel || null,
      execute: form.execute,
    };

    try {
      const response = await fetch(`${API_BASE}/live/route-execute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      const responsePayload = await response.json();
      if (!response.ok || responsePayload.error) {
        throw new Error(responsePayload.reason || responsePayload.error || "Execution failed.");
      }
      setResult(responsePayload);
      await loadStats();
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-shell">
      <header className="hero">
        <p className="eyebrow">Live Data Only</p>
        <h1>EAR Routing Console</h1>
        <p>
          Ask any question. EAR selects the best model, can override your preference when policy
          or scoring requires it, and returns full transparency for every decision.
        </p>
      </header>

      <main className="layout-grid">
        <section className="panel prompt-panel">
          <h2>Ask a Question</h2>
          <form onSubmit={onSubmit}>
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
                <pre>{result.response_text || "Route-only mode: no model execution was requested."}</pre>
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
      </footer>
    </div>
  );
}
