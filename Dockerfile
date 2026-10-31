# Multi-stage Docker build for NetCoop AI

# Stage 1: Build React dashboard
FROM node:22-alpine AS dashboard-builder
WORKDIR /app/dashboard
COPY dashboard/package*.json ./
RUN npm ci
COPY dashboard/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and schemas
COPY agents/ ./agents/
COPY core/ ./core/
COPY gateway/ ./gateway/
COPY orchestrator/ ./orchestrator/
COPY mcp_server/ ./mcp_server/
COPY api/ ./api/
COPY cli/ ./cli/
COPY storage/ ./storage/
COPY remediation/ ./remediation/
COPY llm/ ./llm/
COPY netcoop/ ./netcoop/
COPY schemas/ ./schemas/
COPY data/ ./data/
COPY docs/ ./docs/
COPY README.md Makefile ./

# Install package in editable mode
RUN pip install --no-cache-dir -e .

# Copy built dashboard assets from stage 1
COPY --from=dashboard-builder /app/dashboard/dist ./dashboard/dist

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

