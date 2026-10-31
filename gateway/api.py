"""FastAPI microservice for telemetry ingestion and canonical normalization."""

from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from gateway.adapters.organizer_adapter import OrganizerAdapter

app = FastAPI(
    title="NetCoop AI Ingestion Gateway",
    version="1.0.0",
    description="Transforms, canonicalizes, and validates external telemetry into NetCoop schemas.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestionResponse(BaseModel):
    """Canonicalized ingestion response payload."""

    incident_id: str
    network_id: str
    schema_version: str
    clock_skew_detected: bool
    record_count: int
    data: Dict[str, Any]


@app.get("/health")
def health() -> Dict[str, str]:
    """Gateway service health check."""
    return {"status": "ok", "service": "gateway", "version": "1.0.0"}


@app.post("/ingest")
async def ingest_endpoint(request: Request) -> Dict[str, Any]:
    """Ingest raw, unnormalized, or organizer-format network data and return canonical schema."""
    try:
        raw_body = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Malformed JSON payload: {str(e)}",
        )

    try:
        canonical_data = OrganizerAdapter.adapt_dataset(raw_body)
        return canonical_data
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Gateway normalization failure: {str(e)}",
        )


def create_gateway_app() -> FastAPI:
    """Factory creating the gateway FastAPI application."""
    return app

