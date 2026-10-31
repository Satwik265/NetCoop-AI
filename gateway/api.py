"""FastAPI microservice for telemetry ingestion, organizer format auto-detection, and canonical normalization."""

from typing import Any, Dict, Optional, Union
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
        return canonical_data
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
