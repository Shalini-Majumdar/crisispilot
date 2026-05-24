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

function AgentAnalysisPanel({ incident }) {
  const scenario = incident?.active_scenario;

  let message = "Trigger a scenario to let CrisisPilot observe a failure.";

  if (scenario === "latency_crisis") {
    message =
      "Recommendation latency increased sharply. Future Gemini agent will identify slow endpoint and suggest cached fallback.";
  }

  if (scenario === "token_spike") {
    message =
      "Estimated token usage spiked. Future Gemini agent will recommend context compression and prompt trimming.";
  }

  if (scenario === "tool_failure") {
    message =
      "Search tool failed. Future Gemini agent will recommend retry limits and graceful fallback.";
  }

  return (
    <section className="panel agent-panel">
      <p className="eyebrow">Agent Preview</p>
      <h2>What CrisisPilot sees</h2>
      <p>{message}</p>

      <div className="approval-box">
        <span>Human approval required</span>
        <button disabled>Approve Recovery</button>
      </div>
    </section>
  );
}

export default function App() {
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

        <div className="main-column">
          <TelemetryCards incident={incident} />
          <IncidentTimeline timeline={timeline} />
        </div>

        <AgentAnalysisPanel incident={incident} />
      </section>
    </main>
  );
}