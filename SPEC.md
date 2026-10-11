# TrialRadar: build spec (MIT)

Open-source tool that estimates how likely a clinical trial design is to be
terminated early (especially for low accrual), learning from REAL public
ClinicalTrials.gov records, and shows similar past trials with their stated
reasons for stopping. Target: Regeneron challenge at HackRU. Judges score:
real bottleneck, readiness (clean clone works), design and packaging
(README, demo video, slides, intuitive UX), and explains itself.
Solo build, 4 hours total including video and slides. Keep scope tight. Ask
before adding scope.

## Hard rules
- No LLM calls and no API keys. Data from ClinicalTrials.gov API v2 only
  (https://clinicaltrials.gov/api/v2/studies, free, no key). Do NOT touch
  /api/int endpoints, do not spoof browsers, do not evade any access control.
- Cache downloads in data/raw/ (gitignored). Polite rate limit (>=0.5s),
  retries with backoff, descriptive User-Agent.
- NO TARGET LEAKAGE. The v2 API returns the CURRENT record, so exclude any field
  that reflects what happened during or after the trial. Forbidden as features:
  enrollment count/type, location/country counts, overall status and any status
  or completion dates, why-stopped text, results data, last-update dates,
  publications. Add a pytest leakage guard that fails if a forbidden column
  reaches the feature matrix.
- State the limit prominently: features approximate the registered design, but
  the record may have been edited after registration.
- State prominently: predictions are risk estimates that assist trial designers.
  They do not approve or reject designs.
- Report results honestly including weak ones. Never tune on the test set.
- Don't cite outside statistics unless sourced. Compute base rates from our own
  data. For general context you may cite Tufts CSDD figures from the Regeneron
  starter sheet "Site Unseen" (about 11% of chosen sites enroll zero patients and
  37% enroll fewer than promised).
- Python 3.12, .venv, requirements.txt: pandas, scikit-learn, requests,
  streamlit, pytest. Keep the existing LICENSE (MIT).
- Commit and push to origin after each step.

## STEP 0: gate (max 15 min)
Using API v2 with pagination (pageSize up to 1000, pageToken), fetch a first page
of interventional trials (Phase 2, Phase 2/3, Phase 3; drug or biological;
start date 2008-2019; status COMPLETED or TERMINATED). Print: how many fetched,
fields available (design, eligibility, outcomes, sponsor, whyStopped), the
share terminated, and 5 sample whyStopped strings. Stop and report.

## Step 1: dataset
Fetch up to ~8,000 matching trials (cap for speed). Exclude WITHDRAWN, UNKNOWN,
and ongoing statuses (document the selection effect in the README). Save a small
processed table to data/processed/ (committed) with the allowed features, labels,
NCT IDs, and why-stopped text for terminated trials.

## Step 2: labels (docs/labels.md)
- terminated: status TERMINATED (1) vs COMPLETED (0).
- terminated_low_accrual: terminated AND the whyStopped text matches documented
  keywords (accrual, enrol(l)ment, recruit, participants, patients, slow, low,
  insufficient, lack of eligible).
- Also classify whyStopped into: low accrual, sponsor/business/funding,
  safety, efficacy/futility, other/unspecified. Document the keyword rules.
- Print 30 random classified examples and label counts to eyeball accuracy.
Print positive rates for each label.

## Step 3: features (registered-design proxies only)
phase, masking, allocation, intervention model, number of arms, number of
interventions, intervention types, number of primary and secondary outcomes,
eligibility text length and criteria count, inclusion vs exclusion counts,
min/max age, sex, healthy-volunteers flag, number of conditions, condition
category (about 12 therapeutic areas), lead sponsor class, start year,
has data monitoring committee, FDA-regulated drug flag if present in the record.

## Step 4: modeling and benchmark (BENCHMARK.md, `make benchmark`)
- Time split by start year: train 2008-2016, test 2017-2019.
- Models: standardized logistic regression and gradient boosting.
- Baselines: base rate; therapeutic-area base rate.
- Report ROC-AUC with bootstrap 95% CI, PR-AUC, calibration table, per-label
  results, coefficients / importances, and base rates.
- Write plain-English conclusions including limits. If AUC is near chance, say so.
AFTER STEP 4: print the benchmark summary and STOP for review.

## Step 5: similar-trial retrieval
TF-IDF over condition + intervention + design text with cosine similarity. For
any trial return the 5 nearest TERMINATED trials with their stated why-stopped
reason and links, plus the share of the nearest 25 that terminated.

## Step 6: Streamlit app (app/Home.py)
- Input: NCT ID (fetch via API v2; works for not-yet-recruiting trials too) or a
  manual design form.
- Output: risk band, risk for terminated and for low accrual, plain-language top
  drivers (e.g. "eligibility much longer than similar trials"), similar
  terminated trials with reasons, and short design checks.
- Dashboard page: termination rates by therapeutic area and by reason.
- Visible disclaimers (limits above). Clean layout, phone-width safe, tooltips
  for jargon.

## Step 7: packaging
README (problem, what it does, quickstart: clone then `make setup && make run`
works offline from data/processed, data and label definitions, benchmark
results, limitations, sources, license), pytest tests (labels, features,
leakage guard), Makefile targets (setup, data, benchmark, run, test),
docs/labels.md, docs/demo_script.md (timed 3-minute script). Verify a fresh
clone runs from the README alone.
