# 📡 TrialRadar

**Early-stopping risk for clinical trial designs, learned from 41,380 real ClinicalTrials.gov records.**
Open source (MIT) · no LLMs · no API keys · runs offline from a clone.

**Live demo:** https://trialradar-i080.onrender.com  *(free instance: after being idle it sleeps, and the first load can take up to a minute to wake)*

> **Please read.** TrialRadar produces risk *estimates* that **assist trial designers**. It is **not an approval tool**
> and does not say a design is good or bad. Its data are a **current-record snapshot** (records may have been edited
> after registration) and its reasons-for-stopping are **keyword-derived labels**, not human review.
> Its ranking skill is modest (see [Results](#results)); use it as one screening input.

## The problem
Trials that stop early waste time, money and participants' contributions. Context from the Regeneron challenge
starter sheet "Site Unseen" (Tufts CSDD): about 11% of chosen sites enroll zero patients and 37% enroll fewer than
promised. Designers have little way to ask: *"what happened to trials that looked like mine?"*

## What it does
Enter a ClinicalTrials.gov **NCT ID** (works for trials that have not started) or describe a design in a form.
TrialRadar shows:
1. **Low-accrual risk** (leads): an estimated chance the trial is terminated for too few participants, and a band relative to trials that started 2017-2019.
2. **Overall early-termination risk** as a **relative band only** (never a raw percentage, because the model under-predicts for 2017-2019 starts).
3. **"X of the 25 most similar trials were terminated"** plus the **5 nearest terminated trials** with their classified reason, the raw stated reason, and a link to ClinicalTrials.gov.
4. **What moves the estimate** (descriptive attributions vs a typical trial) and **design checks** (percentile versus the 25 nearest trials; descriptive only, no advice).
5. A **"How reliable is this?"** panel (tables read from `BENCHMARK.md`) and a **Dashboard** of termination rates by therapeutic area, phase, sponsor class, start year, and reason.

## Quickstart
```bash
git clone https://github.com/Vorajay2005/amendmentradar.git
cd amendmentradar
make setup     # creates .venv and installs Python requirements (internet needed once, for pip)
make run       # serves the web app + API at http://localhost:8000 (open it in your browser)
```
`make run` works **offline** and needs **no Node**: the built React app (`web/dist`) is committed, and the API only reads committed files (`data/`, `models/`, `BENCHMARK.md`).
Tested on Python 3.12 (3.14 also installs).

| Target | What it does |
|---|---|
| `make run` | FastAPI + built React app on http://localhost:8000 |
| `make dev` | hot reload: API with `--reload` plus the Vite dev server on http://localhost:5173 (needs Node >= 20, see `web/.nvmrc`) |
| `make web` | rebuild `web/dist` after editing `web/src` (needs Node >= 20); commit the result |
| `make test` | pytest: labels, features, leakage guard, retrieval, API, Streamlit pages |
| `make benchmark` | retrain, evaluate, rewrite `BENCHMARK.md`, `models/`, `data/tfidf_index.joblib` (~3 min) |
| `make data` | re-download the population from ClinicalTrials.gov API v2 into `data/raw/` (gitignored, ~180 MB, cached, resumable) and rebuild `data/processed/` |
| `make run-streamlit` | the original Streamlit UI |

Only the NCT-ID lookup uses the internet (current record from API v2). If it fails, the API falls back to the stored snapshot (trials in the data, plus a bundled copy of the not-yet-recruiting demo trial in `data/examples/`) and the UI says so.

**Why `web/dist` is committed:** a judge or reviewer can run the project from a fresh clone with no network and no Node toolchain, which matters more here than a small build artifact (about 1 MB). `make web` regenerates it.

## Deploy
One web service runs everything: FastAPI serves the API under `/api` and the committed React build (`web/dist`) at `/`, with a fallback to `index.html` so deep links such as `/dashboard` survive a refresh. No secrets or API keys are needed.

- **One command, no Node:** `make serve` (or `python -m api.main`). It binds `0.0.0.0` and reads the port from `$PORT` (default 8000).
- **Render (free tier):** `render.yaml` is included (build `pip install -r requirements.txt`, start `python -m api.main`, health check `/health`, Python pinned to 3.12.9 via `PYTHON_VERSION`). Create a *Blueprint* or a *Web Service* from the `deploy` branch.
- **Dependencies:** `requirements.txt` is runtime-only and fully pinned (the saved models are scikit-learn pickles, so the version must match). `requirements-dev.txt` adds pytest, httpx and Streamlit for `make setup` / `make test`.
- **Free-tier behaviour:** models, the TF-IDF index and the cached tables load once at startup (about 240 MB resident after startup, 316 MB peak while loading, measured on macOS; the free tier allows 512 MB). The service sleeps after ~15 min idle. If ClinicalTrials.gov is unreachable, NCT lookups fall back to the stored snapshots and the UI says so.

## Architecture
```
web/ (React + Vite + TypeScript + Tailwind, Framer Motion, Recharts)  --HTTP-->  api/main.py (FastAPI)
                                                                                    |
                                                                       src/service.py (thin orchestration)
                                                          retrieval.py · scoring.py · modeling.py · BENCHMARK.md parser
```
Endpoints: `POST /api/analyze` (NCT ID or manual design), `GET /api/dashboard`, `GET /api/reliability` (parsed from `BENCHMARK.md`, so the UI always shows the benchmark's own numbers), `GET /api/examples`. The API reuses the existing query, model and benchmark code; nothing is re-implemented.

## Data
- **Source:** [ClinicalTrials.gov](https://clinicaltrials.gov), U.S. National Library of Medicine, public API v2 (no key; only `/api/v2/studies` is used; polite 0.6 s spacing, retries, descriptive User-Agent).
- **Population (entire, no sampling):** interventional, Phase 2, Phase 2/3 and Phase 3 (the API's Phase 2 filter also admits **Phase 1/2** trials: 4,848, or 11.7%), Drug or Biological, start date 2008-2019, status COMPLETED (34,295) or TERMINATED (7,085): **41,380 trials**.
- **Excluded** (same filters): UNKNOWN 6,774; WITHDRAWN 2,204; ACTIVE_NOT_RECRUITING 1,669; RECRUITING 567; SUSPENDED 139; ENROLLING_BY_INVITATION 25; NOT_YET_RECRUITING 11. This is a **selection effect**: true non-completion across the registry is probably higher than the 17.1% observed.
- **Committed:** `data/processed/trials.csv.gz` (features, labels, why-stopped text for terminated trials, text for retrieval).

## Labels (details and known misfires: [docs/labels.md](docs/labels.md))
- `terminated`: status TERMINATED (1) vs COMPLETED (0). Main label. 17.1% positive.
- `terminated_low_accrual`: terminated **and** the why-stopped text matches an ordered rule set whose first match wins: safety → efficacy/futility → sponsor/business → **low accrual** (recruitment word + difficulty word) → other/unspecified. 4.3% positive.

## Features (registered-design proxies only)
Phase, masking, allocation, intervention model, arms, interventions, intervention types, primary/secondary outcome counts, eligibility length and criteria counts (inclusion/exclusion), ages, sex, healthy volunteers, number of conditions, therapeutic area (14 keyword-mapped areas + other), sponsor class, start year, data monitoring committee, FDA-regulated flag.
**No leakage:** enrollment, locations, status, dates other than start year, why-stopped text, results and publications are never downloaded as features, and a pytest guard fails if a forbidden column reaches the feature matrix.

## Results
Time split by start year (train 2008-2016, test 2017-2019: 9,786 trials; 1,993 terminated; **441 low-accrual positives**). 95% bootstrap CIs. Hyperparameters fixed in advance; the test set was never used for tuning. Full report: [BENCHMARK.md](BENCHMARK.md).

| Label | Model | Test ROC-AUC (95% CI) | PR-AUC (base rate) |
|---|---|---|---|
| terminated | Therapeutic-area base rate | 0.601 (0.587-0.615) | 0.261 (0.204) |
| terminated | Logistic regression | 0.631 (0.618-0.644) | 0.295 |
| terminated | **Gradient boosting** | **0.646 (0.633-0.659)** | 0.302 |
| terminated_low_accrual | Therapeutic-area base rate | 0.633 (0.608-0.657) | 0.067 (0.045) |
| terminated_low_accrual | Logistic regression | 0.689 (0.661-0.713) | 0.089 |
| terminated_low_accrual | **Gradient boosting** | **0.701 (0.676-0.724)** | 0.093 |

Stratified 5-fold CV (ignores drift): 0.673 (terminated) and 0.742 (low accrual) for gradient boosting.

What the numbers mean:
- **Overall termination ranking is weak** (AUC 0.65). That is why it is shown as a relative band.
- **Low accrual is modest** (AUC 0.70) and **well calibrated** on the test period (mean prediction 0.043 vs 0.045 observed).
- In 2017-2019, trials in the model's upper third had a low-accrual termination rate of **8.4%** versus **1.7%** in the lower third; the upper third held 62% of all low-accrual terminations. It separates groups of trials; it does not identify individual ones.
- **Drift:** the termination rate was 15-17% for 2008-2016 starts and 18.5-21.7% for 2017-2019, partly COVID-19-related, so the models under-predict termination in the test period.
- A feature-group ablation found no group whose removal cost more than 0.03 AUC (no leakage flag), which is not proof of no leakage.
- **Model search (v2 attempt, rejected).** We searched for improvements on a 2015-2016 validation slice (32 attempts, including sponsor identity, text features, eligibility flags, tuning and calibration); none met the pre-set adoption rule, so v1 models are unchanged. See [docs/model_search.md](docs/model_search.md). The 2017-2019 test set was evaluated once, for v1 only. (The v1 benchmark also scored diagnostic feature-group ablations on it; none of those was used to choose or tune anything.)

## Limitations
1. **Current-record snapshot.** The API returns the latest version; "registered design" features may include post-registration edits, and public version histories could not be obtained.
2. **Selection:** withdrawn, unknown-status and still-running trials are excluded.
3. **Keyword-derived labels.** 37.9% of terminated trials land in "other / unspecified" (738 gave no reason). Known misfires are listed in [docs/labels.md](docs/labels.md).
4. **Rule-order effect:** safety, efficacy and sponsor rules outrank low accrual, so low accrual is undercounted.
5. **Therapeutic area is a crude keyword mapping;** 12% of trials fall in "other".
6. **Associations, not causes;** design checks and drivers do not imply that changing a value will change an outcome.
7. **Temporal drift** (above); models trained on 2008-2016 starts.
8. Not an approval or go/no-go tool.
9. **Near-duplicate neighbours.** About 10% of trials have a near-duplicate neighbour (similarity >= 0.95), such as a sister or extension study, which can influence the 'X of 25' share for those trials.
10. **Scope.** The data set includes 4,848 Phase 1/2 trials (11.7%): the API's Phase 2 filter admits them.

## Repository layout
`src/` (client, labels, features, modeling, retrieval, scoring, service) · `api/` (FastAPI) · `web/` (React UI; `web/dist` is the committed build) · `scripts/` (dataset build, benchmark, optional browser smoke test) · `app/` (original Streamlit UI) · `data/processed/` · `models/` · `docs/` (labels, demo script) · `tests/`.

## Sources and license
- ClinicalTrials.gov, U.S. National Library of Medicine. https://clinicaltrials.gov
- Tufts CSDD figures as quoted on the Regeneron challenge sheet "Site Unseen".
- MIT License ([LICENSE](LICENSE)). Built for the Regeneron challenge at HackRU 2026.
