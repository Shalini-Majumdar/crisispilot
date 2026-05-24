import os
import time
import random
from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
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

resource = Resource.create({
    "service.name": SERVICE_NAME,
    "service.version": "0.2.0",
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

app = FastAPI(title="CrisisPilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FastAPIInstrumentor.instrument_app(app)


# Simple in-memory system state.
# Later we can move this to a database.
system_state = {
    "mode": "healthy",
    "active_scenario": None
}


@app.get("/api/health")
def health():
    with tracer.start_as_current_span("crisispilot.health_check") as span:
        span.set_attribute("http.endpoint", "/api/health")
        span.set_attribute("scenario.name", system_state["active_scenario"] or "none")

        return {
            "status": "healthy",
            "service": SERVICE_NAME,
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"]
        }


@app.post("/api/scenarios/reset")
def reset_scenarios():
    with tracer.start_as_current_span("crisispilot.reset_scenarios") as span:
        system_state["mode"] = "healthy"
        system_state["active_scenario"] = None

        span.set_attribute("scenario.name", "reset")
        span.set_attribute("http.endpoint", "/api/scenarios/reset")

        return {
            "message": "System reset to healthy mode",
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"]
        }


@app.post("/api/scenarios/latency")
def activate_latency_crisis():
    with tracer.start_as_current_span("crisispilot.activate_latency_crisis") as span:
        system_state["mode"] = "failure"
        system_state["active_scenario"] = "latency_crisis"

        span.set_attribute("scenario.name", "latency_crisis")
        span.set_attribute("http.endpoint", "/api/scenarios/latency")

        return {
            "message": "Latency crisis activated",
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"]
        }


@app.post("/api/scenarios/token-spike")
def activate_token_spike():
    with tracer.start_as_current_span("crisispilot.activate_token_spike") as span:
        system_state["mode"] = "failure"
        system_state["active_scenario"] = "token_spike"

        span.set_attribute("scenario.name", "token_spike")
        span.set_attribute("http.endpoint", "/api/scenarios/token-spike")

        return {
            "message": "Gemini token spike scenario activated",
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"]
        }


@app.post("/api/scenarios/tool-failure")
def activate_tool_failure():
    with tracer.start_as_current_span("crisispilot.activate_tool_failure") as span:
        system_state["mode"] = "failure"
        system_state["active_scenario"] = "tool_failure"

        span.set_attribute("scenario.name", "tool_failure")
        span.set_attribute("http.endpoint", "/api/scenarios/tool-failure")

        return {
            "message": "Tool failure scenario activated",
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"]
        }


@app.post("/api/recommendations")
def recommendations():
    start = time.time()

    with tracer.start_as_current_span("crisispilot.recommendations") as span:
        span.set_attribute("http.endpoint", "/api/recommendations")
        span.set_attribute("tool.name", "recommendation-engine")
        span.set_attribute("scenario.name", system_state["active_scenario"] or "none")

        if system_state["active_scenario"] == "latency_crisis":
            time.sleep(5)
            result = {
                "recommendations": [
                    "Fallback item A",
                    "Fallback item B",
                    "Fallback item C"
                ],
                "note": "Recommendations returned after artificial latency"
            }
        else:
            time.sleep(0.2)
            result = {
                "recommendations": [
                    "Item A",
                    "Item B",
                    "Item C"
                ],
                "note": "Recommendations returned normally"
            }

        latency_ms = round((time.time() - start) * 1000, 2)

        span.set_attribute("latency_ms", latency_ms)

        return {
            "endpoint": "/api/recommendations",
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"],
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

        return {
            "endpoint": "/api/gemini-response",
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"],
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

        if system_state["active_scenario"] == "tool_failure":
            time.sleep(0.5)

            span.set_attribute("error.type", "mock_search_tool_500")
            span.set_attribute("latency_ms", round((time.time() - start) * 1000, 2))

            return {
                "endpoint": "/api/search-tool",
                "mode": system_state["mode"],
                "active_scenario": system_state["active_scenario"],
                "status": "failed",
                "error_type": "mock_search_tool_500",
                "message": "Search tool failed with simulated 500 error"
            }

        time.sleep(0.2)
        latency_ms = round((time.time() - start) * 1000, 2)

        span.set_attribute("latency_ms", latency_ms)

        return {
            "endpoint": "/api/search-tool",
            "mode": system_state["mode"],
            "active_scenario": system_state["active_scenario"],
            "status": "success",
            "latency_ms": latency_ms,
            "results": [
                "Result 1",
                "Result 2",
                "Result 3"
            ]
        }