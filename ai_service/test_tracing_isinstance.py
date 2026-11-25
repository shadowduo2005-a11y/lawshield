from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

print(type(trace.get_tracer_provider()))
trace.set_tracer_provider(TracerProvider())
print(type(trace.get_tracer_provider()))
