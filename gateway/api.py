"""FastAPI microservice for telemetry ingestion, organizer format auto-detection, and canonical normalization."""

import secrets
from typing import Any, Dict, Optional, Union
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.config import settings
from gateway.adapters.organizer_adapter import OrganizerAdapter

app = FastAPI(
    title="NetCoop AI Ingestion Gateway",
    version="1.0.0",
    description="Transforms, canonicalizes, and validates external telemetry into NetCoop schemas.",
)

_gateway_cors_origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_gateway_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-NetCoop-Service-Token", "Accept"],
)


@app.middleware("http")
async def verify_gateway_service_auth(request: Request, call_next):
    # Health check is public for orchestrator/docker health probes
    if request.url.path == "/health":
        return await call_next(request)

    # In non-production mode, allow interactive docs
    if not settings.is_production and request.url.path in ("/docs", "/openapi.json"):
        return await call_next(request)

    configured_token = settings.internal_service_token

    # Production mode must fail closed if token is missing or weak
    if settings.is_production:
        valid, reason = settings.validate_service_token_strength(configured_token)
        if not valid:
            return JSONResponse(
                status_code=500,
                content={"detail": f"Production configuration error: {reason}. Gateway fail closed."},
            )

        client_token = request.headers.get(settings.service_auth_header)
        if not client_token or not secrets.compare_digest(client_token, configured_token or ""):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: missing or invalid service authentication token"},
            )
    else:
        # Development mode: if token is explicitly configured, verify it
        if configured_token:
            client_token = request.headers.get(settings.service_auth_header)
            if client_token and not secrets.compare_digest(client_token, configured_token or ""):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized: invalid service authentication token"},
                )

    return await call_next(request)


@app.get("/health")
def health() -> Dict[str, str]:
    """Gateway service health check."""
    return {"status": "ok", "service": "gateway", "version": "1.0.0"}


@app.post("/ingest")
async def ingest_endpoint(request: Request) -> Dict[str, Any]:
    """Ingest raw, unnormalized, or organizer-format network data and return canonical schema."""
    raw_body: Any = None
    try:
        raw_body = await request.json()
    except Exception:
        # Fall back to raw text body for lenient/malformed JSON handling
        try:
            body_bytes = await request.body()
            body_str = body_bytes.decode("utf-8", errors="replace")
            if body_str.strip():
                raw_body = body_str
            else:
                raw_body = ""
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Malformed JSON payload: {str(e)}",
            )

    try:
        canonical_data = OrganizerAdapter.adapt_dataset(raw_body)
        val_errors = canonical_data.get("data_quality", {}).get("validation_errors", [])
        if any(e.get("code") == "ERR_MALFORMED_JSON" and "Unrecoverable" in e.get("explanation", "") for e in val_errors):
            raise HTTPException(
                status_code=400,
                detail="Malformed JSON payload: unrecoverable syntax error",
            )
        return canonical_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Gateway normalization failure: {str(e)}",
        )


def create_gateway_app() -> FastAPI:
    """Factory creating the gateway FastAPI application."""
    return app


def main() -> None:
    """CLI runner to start the Ingestion Gateway microservice."""
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description="Run NetCoop Ingestion Gateway microservice.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface to bind to")
    parser.add_argument("--port", type=int, default=8006, help="Port to listen on")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
