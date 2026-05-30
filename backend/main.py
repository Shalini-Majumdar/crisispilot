import os
import time
import uuid
import logging
from statistics import mean
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import json
from google import genai
from google.genai import types

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


load_dotenv()

SERVICE_NAME = "crisispilot-backend"

DT_OTLP_ENDPOINT = os.getenv("DT_OTLP_ENDPOINT")
DT_API_TOKEN = os.getenv("DT_API_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

resource = Resource.create({
    "service.name": SERVICE_NAME,
    "service.version": "0.3.0",
    "deployment.environment": "local"
})

trace.set_tracer_provider(TracerProvider(resource=resource))

if DT_OTLP_ENDPOINT and DT_API_TOKEN:
    otlp_exporter = OTLPSpanExporter(
        endpoint=f"{DT_OTLP_ENDPOINT}/v1/traces",
        headers={
            "Authorization": f"Api-Token {DT_API_TOKEN}"
        }
    )
    span_processor = BatchSpanProcessor(otlp_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)

tracer = trace.get_tracer(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crisispilot")

app = FastAPI(title="CrisisPilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FastAPIInstrumentor.instrument_app(app)


system_state = {
    "mode": "healthy",
    "active_scenario": None,
    "current_incident_id": None
}

incident_events = []
incident_analyses = {}
incident_decisions = {}

def build_incident_prompt(telemetry: dict):
    return f"""
You are CrisisPilot, an AI incident commander.

You must diagnose the incident using only the provided telemetry evidence.
Do not invent missing evidence.
Return JSON only.
Recommend safe recovery actions that require human approval.

Telemetry evidence:
{json.dumps(telemetry, indent=2)}

Return JSON with exactly these fields:
- incident_id
- severity
- incident_type
- root_cause
- evidence
- user_impact
- business_impact
- recommended_actions
- human_approval_required
- confidence
"""

INCIDENT_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "incident_id": {"type": "string"},
        "severity": {"type": "string"},
        "incident_type": {"type": "string"},
        "root_cause": {"type": "string"},
        "evidence": {
            "type": "array",
            "items": {"type": "string"}
        },
        "user_impact": {"type": "string"},
        "business_impact": {"type": "string"},
        "recommended_actions": {
            "type": "array",
            "items": {"type": "string"}
        },
        "human_approval_required": {"type": "boolean"},
        "confidence": {"type": "string"}
    },
    "required": [
        "incident_id",
        "severity",
        "incident_type",
        "root_cause",
        "evidence",
        "user_impact",
        "business_impact",
        "recommended_actions",
        "human_approval_required",
        "confidence"
    ]
}


def create_incident(scenario_name: str):
    incident_id = str(uuid.uuid4())[:8]

    system_state["mode"] = "failure"
    system_state["active_scenario"] = scenario_name
    system_state["current_incident_id"] = incident_id

    incident_events.append({
        "incident_id": incident_id,
        "scenario": scenario_name,
        "event_type": "incident_created",
        "timestamp": time.time(),
        "latency_ms": 0,
        "status": "created",
        "error_type": None,
        "tokens_estimated": 0,
        "tool_failure": False,
        "endpoint": None
    })

    logger.info(
        "Incident created",
        extra={
            "incident_id": incident_id,
            "scenario": scenario_name
        }
    )

    return incident_id


def record_event(
    endpoint: str,
    latency_ms: float,
    status: str = "success",
    error_type: str | None = None,
    tokens_estimated: int = 0,
    tool_failure: bool = False
):
    incident_id = system_state["current_incident_id"]

    event = {
        "incident_id": incident_id,
        "scenario": system_state["active_scenario"],
        "event_type": "telemetry_captured",
        "timestamp": time.time(),
        "endpoint": endpoint,
        "latency_ms": latency_ms,
        "status": status,
        "error_type": error_type,
        "tokens_estimated": tokens_estimated,
        "tool_failure": tool_failure
    }

    incident_events.append(event)

    logger.info(f"Telemetry event recorded: {event}")

    return event


def get_affected_endpoint(scenario: str | None):
    if scenario == "latency_crisis":
        return "/api/recommendations"
    if scenario == "token_spike":
        return "/api/gemini-response"
    if scenario == "tool_failure":
        return "/api/search-tool"
    return None


@app.get("/")
def root():
    return {
        "message": "CrisisPilot backend is running",
        "docs": "/docs"
    }


@app.get("/api/health")
def health():
    with tracer.start_as_current_span("crisispilot.health_check") as span:
        span.set_attribute("http.endpoint", "/api/health")
        span.set_attribute("scenario.name", system_state["active_scenario"] or "none")
        span.set_attribute("incident.id", system_state["current_incident_id"] or "none")

        return {
            "status": "healthy",
            "service": SERVICE_NAME,
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"],
            "incident_id": system_state["current_incident_id"]
        }


@app.post("/api/scenarios/reset")
def reset_scenarios():
    with tracer.start_as_current_span("crisispilot.reset_scenarios") as span:
        span.set_attribute("scenario.name", "reset")
        span.set_attribute("http.endpoint", "/api/scenarios/reset")

        system_state["mode"] = "healthy"
        system_state["active_scenario"] = None
        system_state["current_incident_id"] = None

        logger.info("System reset to healthy mode")

        return {
            "message": "System reset to healthy mode",
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"],
            "incident_id": system_state["current_incident_id"]
        }


@app.post("/api/scenarios/latency")
def activate_latency_crisis():
    incident_id = create_incident("latency_crisis")

    with tracer.start_as_current_span("crisispilot.latency_crisis") as span:
        span.set_attribute("scenario.name", "latency_crisis")
        span.set_attribute("http.endpoint", "/api/scenarios/latency")
        span.set_attribute("incident.id", incident_id)

        return {
            "message": "Latency crisis activated",
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"],
            "incident_id": incident_id
        }


@app.post("/api/scenarios/token-spike")
def activate_token_spike():
    incident_id = create_incident("token_spike")

    with tracer.start_as_current_span("crisispilot.token_spike") as span:
        span.set_attribute("scenario.name", "token_spike")
        span.set_attribute("http.endpoint", "/api/scenarios/token-spike")
        span.set_attribute("incident.id", incident_id)

        return {
            "message": "Gemini token spike scenario activated",
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"],
            "incident_id": incident_id
        }


@app.post("/api/scenarios/tool-failure")
def activate_tool_failure():
    incident_id = create_incident("tool_failure")

    with tracer.start_as_current_span("crisispilot.tool_failure") as span:
        span.set_attribute("scenario.name", "tool_failure")
        span.set_attribute("http.endpoint", "/api/scenarios/tool-failure")
        span.set_attribute("incident.id", incident_id)

        return {
            "message": "Tool failure scenario activated",
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"],
            "incident_id": incident_id
        }


@app.post("/api/recommendations")
def recommendations():
    start = time.time()

    with tracer.start_as_current_span("crisispilot.recommendations") as span:
        span.set_attribute("http.endpoint", "/api/recommendations")
        span.set_attribute("tool.name", "recommendation-engine")
        span.set_attribute("scenario.name", system_state["active_scenario"] or "none")
        span.set_attribute("incident.id", system_state["current_incident_id"] or "none")

        if system_state["active_scenario"] == "latency_crisis":
            time.sleep(5)
            result = {
                "recommendations": ["Fallback item A", "Fallback item B", "Fallback item C"],
                "note": "Recommendations returned after artificial latency"
            }
        else:
            time.sleep(0.2)
            result = {
                "recommendations": ["Item A", "Item B", "Item C"],
                "note": "Recommendations returned normally"
            }

        latency_ms = round((time.time() - start) * 1000, 2)

        span.set_attribute("latency_ms", latency_ms)

        record_event(
            endpoint="/api/recommendations",
            latency_ms=latency_ms
        )

        return {
            "endpoint": "/api/recommendations",
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"],
            "incident_id": system_state["current_incident_id"],
            "latency_ms": latency_ms,
            "data": result
        }


@app.post("/api/gemini-response")
def gemini_response():
    start = time.time()

    with tracer.start_as_current_span("crisispilot.gemini_response") as span:
        span.set_attribute("http.endpoint", "/api/gemini-response")
        span.set_attribute("tool.name", "gemini-model")
        span.set_attribute("scenario.name", system_state["active_scenario"] or "none")
        span.set_attribute("incident.id", system_state["current_incident_id"] or "none")

        if system_state["active_scenario"] == "token_spike":
            fake_context = "large_context " * 5000
            tokens_estimated = len(fake_context.split())
            time.sleep(2)

            response = {
                "message": "Generated response using excessive context",
                "risk": "High token usage detected"
            }
        else:
            fake_context = "short_context " * 50
            tokens_estimated = len(fake_context.split())
            time.sleep(0.3)

            response = {
                "message": "Generated normal Gemini-style response",
                "risk": "Normal token usage"
            }

        latency_ms = round((time.time() - start) * 1000, 2)

        span.set_attribute("gemini.tokens_estimated", tokens_estimated)
        span.set_attribute("latency_ms", latency_ms)

        record_event(
            endpoint="/api/gemini-response",
            latency_ms=latency_ms,
            tokens_estimated=tokens_estimated
        )

        return {
            "endpoint": "/api/gemini-response",
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"],
            "incident_id": system_state["current_incident_id"],
            "gemini_tokens_estimated": tokens_estimated,
            "latency_ms": latency_ms,
            "data": response
        }


@app.post("/api/search-tool")
def search_tool():
    start = time.time()

    with tracer.start_as_current_span("crisispilot.search_tool") as span:
        span.set_attribute("http.endpoint", "/api/search-tool")
        span.set_attribute("tool.name", "mock-search-tool")
        span.set_attribute("scenario.name", system_state["active_scenario"] or "none")
        span.set_attribute("incident.id", system_state["current_incident_id"] or "none")

        if system_state["active_scenario"] == "tool_failure":
            time.sleep(0.5)
            latency_ms = round((time.time() - start) * 1000, 2)

            span.set_attribute("error.type", "mock_search_tool_500")
            span.set_attribute("latency_ms", latency_ms)
            span.set_attribute("tool.failure", True)

            record_event(
                endpoint="/api/search-tool",
                latency_ms=latency_ms,
                status="failed",
                error_type="mock_search_tool_500",
                tool_failure=True
            )

            return {
                "endpoint": "/api/search-tool",
                "mode": system_state["mode"],
                "active_scenario": system_state["active_scenario"],
                "incident_id": system_state["current_incident_id"],
                "status": "failed",
                "error_type": "mock_search_tool_500",
                "latency_ms": latency_ms,
                "message": "Search tool failed with simulated 500 error"
            }

        time.sleep(0.2)
        latency_ms = round((time.time() - start) * 1000, 2)

        span.set_attribute("latency_ms", latency_ms)
        span.set_attribute("tool.failure", False)

        record_event(
            endpoint="/api/search-tool",
            latency_ms=latency_ms
        )

        return {
            "endpoint": "/api/search-tool",
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"],
            "incident_id": system_state["current_incident_id"],
            "status": "success",
            "latency_ms": latency_ms,
            "results": ["Result 1", "Result 2", "Result 3"]
        }


@app.get("/api/incidents")
def list_incidents():
    incident_ids = sorted(
        list(set(event["incident_id"] for event in incident_events if event["incident_id"]))
    )

    return {
        "count": len(incident_ids),
        "incident_ids": incident_ids,
        "events": incident_events
    }


@app.get("/api/incidents/{incident_id}/telemetry-summary")
def telemetry_summary(incident_id: str):
    events = [
        event for event in incident_events
        if event["incident_id"] == incident_id
    ]

    if not events:
        return {
            "error": "Incident not found",
            "incident_id": incident_id
        }

    scenario = events[0]["scenario"]
    affected_endpoint = get_affected_endpoint(scenario)

    telemetry_events = [
        event for event in events
        if event["event_type"] == "telemetry_captured"
    ]

    latencies = [
        event["latency_ms"]
        for event in telemetry_events
        if event["latency_ms"] is not None
    ]

    failed_events = [
        event for event in telemetry_events
        if event["status"] == "failed"
    ]

    tool_failures = [
        event for event in telemetry_events
        if event["tool_failure"]
    ]

    estimated_tokens = sum(
        event["tokens_estimated"]
        for event in telemetry_events
    )

    avg_latency_ms = round(mean(latencies), 2) if latencies else 0
    p95_latency_ms = round(max(latencies), 2) if latencies else 0
    error_rate = round(len(failed_events) / len(telemetry_events), 2) if telemetry_events else 0

    return {
        "incident_id": incident_id,
        "scenario": scenario,
        "affected_endpoint": affected_endpoint,
        "avg_latency_ms": avg_latency_ms,
        "p95_latency_ms": p95_latency_ms,
        "error_rate": error_rate,
        "tool_failures": len(tool_failures),
        "estimated_tokens": estimated_tokens,
        "events_count": len(telemetry_events),
        "evidence_source": "OpenTelemetry traces captured by CrisisPilot and exported to Dynatrace"
    }


@app.get("/api/current-telemetry-summary")
def current_telemetry_summary():
    incident_id = system_state["current_incident_id"]

    if not incident_id:
        return {
            "message": "No active incident",
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"]
        }

    return telemetry_summary(incident_id)

@app.post("/api/incidents/{incident_id}/analyze")
def analyze_incident(incident_id: str):
    with tracer.start_as_current_span("crisispilot.gemini_incident_analysis") as span:
        span.set_attribute("http.endpoint", f"/api/incidents/{incident_id}/analyze")
        span.set_attribute("incident.id", incident_id)
        span.set_attribute("tool.name", "gemini-analysis-agent")

        telemetry = telemetry_summary(incident_id)

        if "error" in telemetry:
            span.set_attribute("error.type", "incident_not_found")
            return telemetry

        if not gemini_client:
            span.set_attribute("error.type", "gemini_api_key_missing")
            return {
                "error": "Gemini API key missing. Add GEMINI_API_KEY to backend/.env"
            }

        prompt = build_incident_prompt(telemetry)

        try:
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=INCIDENT_ANALYSIS_SCHEMA,
                    temperature=0.2
                )
            )

            analysis = json.loads(response.text)

            incident_analyses[incident_id] = {
                "incident_id": incident_id,
                "telemetry_summary": telemetry,
                "analysis": analysis,
                "status": "analysis_complete",
                "source": "Gemini structured JSON output"
            }

            span.set_attribute("scenario.name", telemetry["scenario"])
            span.set_attribute("analysis.status", "success")

            return incident_analyses[incident_id]

        except Exception as e:
            span.set_attribute("error.type", "gemini_analysis_failed")
            return {
                "error": "Gemini analysis failed",
                "details": str(e)
            }

@app.post("/api/incidents/{incident_id}/approve")
def approve_recovery_plan(incident_id: str):
    if incident_id in incident_decisions:
        return {
            "locked": True,
            "message": "A human decision has already been recorded for this incident.",
            "existing_decision": incident_decisions[incident_id]
        }

    if incident_id not in incident_analyses:
        return {
            "error": "Analyze incident before approving recovery plan",
            "incident_id": incident_id
        }

    incident_decisions[incident_id] = {
        "incident_id": incident_id,
        "decision": "approved",
        "message": "Recovery plan accepted by human reviewer.",
        "approved_actions": incident_analyses[incident_id]["analysis"]["recommended_actions"],
        "status": "approved_pending_execution",
        "locked": True
    }

    system_state["mode"] = "healthy"
    system_state["active_scenario"] = None
    system_state["current_incident_id"] = None

    return incident_decisions[incident_id]

@app.post("/api/incidents/{incident_id}/reject")
def reject_recovery_plan(incident_id: str):
    if incident_id in incident_decisions:
        return {
            "locked": True,
            "message": "A human decision has already been recorded for this incident.",
            "existing_decision": incident_decisions[incident_id]
        }

    if incident_id not in incident_analyses:
        return {
            "error": "Analyze incident before rejecting recovery plan",
            "incident_id": incident_id
        }

    incident_decisions[incident_id] = {
        "incident_id": incident_id,
        "decision": "rejected",
        "message": "Recovery plan rejected by human reviewer.",
        "status": "rejected_needs_revision",
        "locked": True
    }

    return incident_decisions[incident_id]

@app.post("/api/incidents/{incident_id}/safer-plan")
def generate_safer_plan(incident_id: str):
    if incident_id in incident_decisions:
        return {
            "locked": True,
            "message": "A human decision has already been recorded for this incident.",
            "existing_decision": incident_decisions[incident_id]
        }

    if incident_id not in incident_analyses:
        return {
            "error": "Analyze incident before generating safer plan",
            "incident_id": incident_id
        }

    telemetry = incident_analyses[incident_id]["telemetry_summary"]

    safer_plan = {
        "incident_id": incident_id,
        "decision": "safer_plan_requested",
        "message": "Human reviewer requested a safer recovery plan.",
        "safer_actions": [
            "Do not auto-deploy code changes.",
            "Keep the affected feature in fallback mode.",
            "Ask a human engineer to review Dynatrace traces.",
            "Apply temporary mitigation before permanent fix.",
            "Validate recovery in staging before production rollout."
        ],
        "status": "safer_plan_generated_awaiting_execution_review",
        "based_on": telemetry,
        "locked": True
    }

    incident_decisions[incident_id] = safer_plan
    return safer_plan