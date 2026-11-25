from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer("test")

with tracer.start_as_current_span("test-span") as span:
    try:
        raise ValueError("Oops")
    except Exception as exc:
        span.set_status(trace.StatusCode.ERROR, str(exc))
