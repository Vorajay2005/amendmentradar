PY = .venv/bin/python

setup:
	python3.12 -m venv .venv 2>/dev/null || python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt

data:          ## re-download from ClinicalTrials.gov API v2 (cached in data/raw/) and rebuild data/processed/
	$(PY) scripts/build_dataset.py

benchmark:     ## train, evaluate, write BENCHMARK.md + models/ + data/tfidf_index.joblib
	$(PY) scripts/benchmark.py

run:           ## serve the React app + API at http://localhost:8000 (uses the committed web/dist; no Node needed)
	@echo "TrialRadar -> http://localhost:8000  (Ctrl+C to stop)"
	.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000

dev:           ## hot reload: API on :8000 (auto-reload) + Vite on http://localhost:5173 (needs Node >= 20)
	@[ -d web/node_modules ] || (cd web && npm ci)
	@echo "Dev UI -> http://localhost:5173  (API on :8000)"
	@trap 'kill 0' INT TERM EXIT; .venv/bin/uvicorn api.main:app --reload --port 8000 & cd web && npm run dev

web:           ## rebuild web/dist after editing web/src (needs Node >= 20); commit the result
	cd web && npm ci && npm run build

run-streamlit: ## the original Streamlit UI
	.venv/bin/streamlit run app/Home.py --server.headless true --browser.gatherUsageStats false

test:
	$(PY) -m pytest -q

.PHONY: setup data benchmark run dev web run-streamlit test
