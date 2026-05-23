import os
from fastapi import FastAPI
from dotenv import load_dotenv

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
    "service.version": "0.1.0",
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

FastAPIInstrumentor.instrument_app(app)


@app.get("/api/health")
def health():
    with tracer.start_as_current_span("crisispilot.health_check"):
        return {
            "status": "healthy",
            "service": SERVICE_NAME
        }