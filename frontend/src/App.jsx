import { useState } from "react";
import axios from "axios";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";

const scenarios = [
  {
    id: "latency",
    title: "Latency Crisis",
    description: "Recommendation endpoint slows down to 5 seconds.",
    endpoint: "/api/scenarios/latency",
    testEndpoint: "/api/recommendations",
    metric: "latency_ms",
  },
  {
    id: "token-spike",
    title: "Token Spike",
    description: "Gemini-style response uses excessive context.",
    endpoint: "/api/scenarios/token-spike",
    testEndpoint: "/api/gemini-response",
    metric: "gemini_tokens_estimated",
  },
  {
    id: "tool-failure",
    title: "Tool Failure",
    description: "Mock search tool returns a simulated failure.",
    endpoint: "/api/scenarios/tool-failure",
    testEndpoint: "/api/search-tool",
    metric: "error_type",
  },
];

function ScenarioCard({ scenario, onTrigger, loading }) {
  return (
    <button
      className="scenario-card"
      onClick={() => onTrigger(scenario)}
      disabled={loading}
    >
      <span className="scenario-label">SIMULATE</span>
      <h3>{scenario.title}</h3>
      <p>{scenario.description}</p>
    </button>
  );
}

function TelemetryCards({ incident }) {
  return (
    <section className="telemetry-grid">
      <div className="telemetry-card">
        <span>Mode</span>
        <strong>{incident?.mode || "healthy"}</strong>
      </div>

      <div className="telemetry-card">
        <span>Scenario</span>
        <strong>{incident?.active_scenario || "none"}</strong>
      </div>

      <div className="telemetry-card">
        <span>Latency</span>
        <strong>
          {incident?.latency_ms ? `${incident.latency_ms} ms` : "—"}
        </strong>
      </div>

      <div className="telemetry-card">
        <span>Tokens</span>
        <strong>{incident?.gemini_tokens_estimated || "—"}</strong>
      </div>
    </section>
  );
}

function IncidentTimeline({ timeline }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <p className="eyebrow">Incident Timeline</p>
        <h2>Failure flight path</h2>
      </div>

      <div className="timeline">
        {timeline.map((item, index) => (
          <div className="timeline-item" key={index}>
            <div className="timeline-dot" />
            <div>
              <strong>{item.title}</strong>
              <p>{item.description}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function AgentAnalysisPanel({
  incident,
  analysis,
  decision,
  decisionLocked,
  pendingDecision,
  onAnalyze,
  onApprove,
  onReject,
  onSaferPlan,
  onConfirmDecision,
  onCancelDecision,
  analyzing,
}) {
  const geminiAnalysis = analysis?.analysis;
  const error = analysis?.error;

  return (
    <section className="panel agent-panel">
      <p className="eyebrow">Agent Analysis</p>
      <h2>What CrisisPilot sees</h2>

      {!incident && (
        <p>Trigger a scenario to let CrisisPilot observe a failure.</p>
      )}

      {incident && !geminiAnalysis && !error && (
        <p>
          Telemetry has been captured for{" "}
          <strong>{incident.active_scenario}</strong>. Run agent analysis to
          diagnose the incident.
        </p>
      )}

      {error && (
        <div className="analysis-box">
          <strong>Analysis failed</strong>
          <p>{error}</p>
          <small>{analysis?.details}</small>
        </div>
      )}

      {geminiAnalysis && (
        <div className="analysis-box">
          <strong>{geminiAnalysis.severity} Severity</strong>
          <p>{geminiAnalysis.root_cause}</p>

          <h4>Evidence</h4>
          <ul>
            {geminiAnalysis.evidence?.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>

          <h4>Recovery Plan</h4>
          <ul>
            {geminiAnalysis.recommended_actions?.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>

          <div className="decision-actions">
            <button onClick={onApprove} disabled={decisionLocked}>
              Approve Recovery Plan
            </button>

            <button onClick={onReject} disabled={decisionLocked}>
              Reject Plan
            </button>

            <button onClick={onSaferPlan} disabled={decisionLocked}>
              Generate Safer Plan
            </button>
          </div>

          {pendingDecision && (
            <div className="confirm-box">
              <strong>{pendingDecision.title}</strong>
              <p>{pendingDecision.message}</p>

              <div className="confirm-actions">
                <button onClick={onConfirmDecision}>Confirm</button>
                <button onClick={onCancelDecision}>Cancel</button>
              </div>
            </div>
          )}

          {decision && (
            <div className="decision-box">
              <strong>
                {decision.message || "Decision recorded by human reviewer."}
              </strong>

              <p>
                Status: {decision.status || decision.decision || "pending"}
              </p>

              {decision.approved_actions && (
                <>
                  <h4>Approved Actions</h4>
                  <ul>
                    {decision.approved_actions.map((action, index) => (
                      <li key={index}>{action}</li>
                    ))}
                  </ul>
                </>
              )}

              {decision.safer_actions && (
                <>
                  <h4>Safer Recovery Plan</h4>
                  <ul>
                    {decision.safer_actions.map((action, index) => (
                      <li key={index}>{action}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
        </div>
      )}

      <div className="approval-box">
        <span>Human approval required</span>

        <button
          onClick={onAnalyze}
          disabled={!incident?.incident_id || analyzing || decisionLocked}
        >
          {analyzing ? "Analyzing..." : "Analyze Incident"}
        </button>
      </div>
    </section>
  );
}

export default function App() 
{ const [analysis, setAnalysis] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [decision, setDecision] = useState(null);
  const [decisionLocked, setDecisionLocked] = useState(false);
  const [pendingDecision, setPendingDecision] = useState(null);

 const approvePlan = () => {
  if (!incident?.incident_id || decisionLocked) return;

  setPendingDecision({
    type: "approve",
    title: "Approve recovery plan?",
    message:
      "This will accept Gemini's recovery plan and lock all other decision options.",
  });
};

const rejectPlan = () => {
  if (!incident?.incident_id || decisionLocked) return;

  setPendingDecision({
    type: "reject",
    title: "Reject recovery plan?",
    message:
      "This will reject Gemini's proposed recovery plan and lock all other decision options.",
  });
};

const generateSaferPlan = () => {
  if (!incident?.incident_id || decisionLocked) return;

  setPendingDecision({
    type: "safer",
    title: "Generate safer plan?",
    message:
      "This will request a lower-risk recovery plan and lock all other decision options.",
  });
};

const confirmDecision = async () => {
  if (!pendingDecision || !incident?.incident_id) return;

  let endpoint = "";

  if (pendingDecision.type === "approve") {
    endpoint = "approve";
  }

  if (pendingDecision.type === "reject") {
    endpoint = "reject";
  }

  if (pendingDecision.type === "safer") {
    endpoint = "safer-plan";
  }

  try {
    const response = await axios.post(
      `${API_BASE}/api/incidents/${incident.incident_id}/${endpoint}`
    );

    const finalDecision = response.data.existing_decision || response.data;

    setDecision(finalDecision);
    setDecisionLocked(true);
    setPendingDecision(null);

    if (pendingDecision.type === "approve") {
      addTimeline(
        "Recovery approved",
        "Human reviewer accepted the recovery plan. Other decision options are now locked."
      );

      setIncident({
        ...incident,
        mode: "healthy",
        active_scenario: null,
      });
    }

    if (pendingDecision.type === "reject") {
      addTimeline(
        "Recovery rejected",
        "Human reviewer rejected the proposed plan. Other decision options are now locked."
      );
    }

    if (pendingDecision.type === "safer") {
      addTimeline(
        "Safer plan generated",
        "Human reviewer requested a lower-risk recovery plan. Other decision options are now locked."
      );
    }
  } catch (error) {
    addTimeline("Decision failed", "Could not record the human decision.");
    setPendingDecision(null);
  }
};

  const analyzeIncident = async () => {
  if (!incident?.incident_id) {
    addTimeline("Analysis blocked", "No incident ID found. Trigger a scenario first.");
    return;
  }

  try {
    setAnalyzing(true);

    addTimeline(
      "Gemini investigation started",
      "CrisisPilot is sending telemetry evidence to the incident analysis agent."
    );

    const response = await axios.post(
      `${API_BASE}/api/incidents/${incident.incident_id}/analyze`
    );

    setAnalysis(response.data);

    addTimeline(
      "Analysis complete",
      "Gemini returned a structured diagnosis and recovery plan."
    );
  } catch (error) {
    addTimeline("Analysis failed", "Could not analyze the incident.");
  } finally {
    setAnalyzing(false);
  }
};

  const [incident, setIncident] = useState(null);
  const [timeline, setTimeline] = useState([
    {
      title: "System ready",
      description: "CrisisPilot backend is waiting for a failure simulation.",
    },
  ]);
  const [loading, setLoading] = useState(false);

  const addTimeline = (title, description) => {
    setTimeline((prev) => [...prev, { title, description }]);
  };

  const triggerScenario = async (scenario) => {
  try {
    setLoading(true);
    setTimeline([]);
    setAnalysis(null);
    setDecision(null);
    setDecisionLocked(false);
    setPendingDecision(null);

    addTimeline("Scenario armed", `${scenario.title} has been triggered.`);

    await axios.post(`${API_BASE}${scenario.endpoint}`);

    addTimeline(
      "Failure injected",
      "The demo AI app is now running in broken mode."
    );

    const response = await axios.post(`${API_BASE}${scenario.testEndpoint}`);

    setIncident(response.data);

    addTimeline(
      "Telemetry captured",
      `${scenario.testEndpoint} returned measurable failure evidence.`
    );

    addTimeline(
      "Ready for analysis",
      "Dynatrace can now display this trace for agent investigation."
    );
  } catch (error) {
    addTimeline("Frontend error", "Could not reach the backend API.");
  } finally {
    setLoading(false);
  }
};

  const resetSystem = async () => {
  try {
    setLoading(true);

    const response = await axios.post(`${API_BASE}/api/scenarios/reset`);
    setIncident(response.data);
    setAnalysis(null);
    setDecision(null);
    setDecisionLocked(false);

    setTimeline([
      {
        title: "System reset",
        description: "All failure scenarios cleared. Healthy mode restored.",
      },
    ]);
  } catch (error) {
    addTimeline("Reset failed", "Could not reset backend state.");
  } finally {
    setLoading(false);
  }
};

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">AI Failure Simulator</p>
          <h1>CrisisPilot Mission Control</h1>
          <p>
            Inject controlled failures, capture telemetry through Dynatrace,
            and prepare the incident for Gemini-powered investigation.
          </p>
        </div>

        <div className="status-pill">
          <span className={incident?.mode === "failure" ? "pulse danger" : "pulse"} />
          {incident?.mode === "failure" ? "Failure active" : "Healthy"}
        </div>
      </section>

<section className="dashboard-layout">
  <div className="top-grid">
    <aside className="panel scenario-panel">
      <p className="eyebrow">Failure Lab</p>
      <h2>Choose a crisis</h2>

      <div className="scenario-list">
        {scenarios.map((scenario) => (
          <ScenarioCard
            key={scenario.id}
            scenario={scenario}
            onTrigger={triggerScenario}
            loading={loading}
          />
        ))}
      </div>

      <button className="reset-button" onClick={resetSystem} disabled={loading}>
        Reset System
      </button>
    </aside>

    <div className="operations-panel">
      <TelemetryCards incident={incident} />
      <IncidentTimeline timeline={timeline} />
    </div>
  </div>

  <AgentAnalysisPanel
    incident={incident}
    analysis={analysis}
    decision={decision}
    decisionLocked={decisionLocked}
    pendingDecision={pendingDecision}
    onAnalyze={analyzeIncident}
    onApprove={approvePlan}
    onReject={rejectPlan}
    onSaferPlan={generateSaferPlan}
    onConfirmDecision={confirmDecision}
    onCancelDecision={() => setPendingDecision(null)}
    analyzing={analyzing}
  />
</section>
    </main>
  );
}