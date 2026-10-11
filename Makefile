PY = .venv/bin/python

setup:
	python3.12 -m venv .venv 2>/dev/null || python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt

data:          ## re-download from ClinicalTrials.gov API v2 (cached in data/raw/) and rebuild data/processed/
	$(PY) scripts/build_dataset.py

benchmark:     ## train, evaluate, write BENCHMARK.md + models/ + data/tfidf_index.joblib
	$(PY) scripts/benchmark.py

run:
	.venv/bin/streamlit run app/Home.py

test:
	$(PY) -m pytest -q

.PHONY: setup data benchmark run test
