# NetCoop AI Automation Makefile
# Target platforms: Linux, macOS, and Windows (via PowerShell / bash)

.PHONY: help setup demo test eval assets run clean

help:
	@echo "NetCoop AI Automation Commands:"
	@echo "  make setup   - Install Python dependencies and dashboard packages"
	@echo "  make demo    - Run CLI diagnosis demonstration on key scenarios"
	@echo "  make test    - Run complete unit and property-based test suite"
	@echo "  make eval    - Execute 19-scenario ground-truth diagnostic benchmark"
	@echo "  make assets  - Compile and bundle React dashboard frontend assets"
	@echo "  make run     - Start local FastAPI backend server on port 8000"
	@echo "  make clean   - Remove build artifacts, pycache, and temporary caches"

setup:
	python -m pip install --upgrade pip
	pip install -r requirements.txt
	pip install -e .
	cd dashboard && npm install

demo:
	netcoop gen --scenario link_congestion --seed 42
	netcoop diagnose --file data/scenarios/link_congestion.json
	netcoop diagnose --file data/scenarios/weak_wifi_signal.json
	netcoop diagnose --file data/scenarios/insufficient_data.json

test:
	pytest tests/ -v

eval:
	python scripts/eval_benchmark.py

assets:
	cd dashboard && npm run build

run:
	uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".hypothesis" -exec rm -rf {} + 2>/dev/null || true

