# core/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
import os
from dotenv import load_dotenv

load_dotenv()

def setup_tracing(service_name: str):
    # Eğer zaten bir provider varsa tekrar kurma (Worker ve API çakışmasın)
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        return trace.get_tracer(__name__)

    resource = Resource(attributes={"service.name": service_name})
    provider = TracerProvider(resource=resource)
    
    # OTLP Exporter (Docker'daki Jaeger'a bağlanır)
    jaeger_endpoint = os.environ["OTLP_ENDPOINT"]
    exporter = OTLPSpanExporter(endpoint=jaeger_endpoint, insecure=True)
    
    # Asenkron ve batch (toplu) gönderim (Sistemi yavaşlatmaz)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    
    trace.set_tracer_provider(provider)
    return trace.get_tracer(__name__)