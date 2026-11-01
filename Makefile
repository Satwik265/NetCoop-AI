# NetCoop AI Automation Makefile
# Target platforms: Linux, macOS, and Windows (via PowerShell / bash)

.PHONY: help setup up down demo demo-organizer test eval eval-quick train assets gen-assets readme run clean

help:
	@echo "NetCoop AI Automation Commands:"
	@echo "  make setup          - Install Python dependencies and dashboard packages"
	@echo "  make up             - Start all specialist agent microservices on assigned ports"
	@echo "  make down           - Terminate all running agent microservices cleanly"
	@echo "  make demo           - Run end-to-end multi-agent demonstration (normal, link, ethernet)"
	@echo "  make demo-organizer - Ingest organizer Colab JSONL samples and run diagnostic pipeline"
	@echo "  make test           - Run complete unit and property-based test suite"
	@echo "  make eval           - Execute diagnostic benchmark across all sets"
	@echo "  make eval-quick     - Execute quick diagnostic benchmark"
	@echo "  make train          - Train learned classifier, calibrate, and generate artifacts"
	@echo "  make assets         - Compile and bundle React dashboard frontend assets"
	@echo "  make gen-assets     - Regenerate all visual charts, diagrams, and screenshots"
	@echo "  make readme         - Dynamically compile README.md from benchmark results"
	@echo "  make run            - Start local FastAPI backend server on port 8000"
	@echo "  make clean          - Remove build artifacts, pycache, and temporary caches"

setup:
	python -m pip install --upgrade pip
	pip install -r requirements.txt
	pip install -e .
	cd dashboard && npm install

up:
	python scripts/run_agents.py --daemon

down:
	python scripts/run_agents.py --stop

demo:
	python scripts/demo.py

demo-organizer:
	python scripts/demo_organizer.py

test:
	pytest tests/ -v

eval:
	python scripts/eval_benchmark.py

eval-quick:
	python scripts/eval_benchmark.py --quick

train:
	python scripts/train_models.py

assets:
	cd dashboard && npm run build

gen-assets:
	python docs/assets/scripts/generate_all_assets.py

readme:
	@echo "Disabled: README.md is maintained by hand; docs/README.template.md is stale."

run:
	uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

clean:
	python scripts/run_agents.py --stop 2>/dev/null || true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".hypothesis" -exec rm -rf {} + 2>/dev/null || true
