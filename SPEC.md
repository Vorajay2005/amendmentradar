# AmendmentRadar — build spec (MIT license)

Open-source tool that estimates how likely a clinical trial design is to be
changed after registration, learning from REAL public ClinicalTrials.gov record
version histories. Target: Regeneron HackRU challenge. Judges score: real
bottleneck, readiness (runs from a clean clone), design/packaging (README, demo
video, slides), explains itself. I'm solo. TOTAL BUDGET 4 HOURS including video
and slides. Keep scope tight. Ask me before adding scope.

## Hard rules
- No LLM calls and no API keys anywhere. Pure data + classical ML.
- Cache every download on disk (data/raw, gitignored). Be polite: >=0.5s delay,
  retries with backoff, descriptive User-Agent.
- No target leakage: features come ONLY from the first-posted version.
- Never present registry edits as protocol amendments. They are a PROXY.
  The UI and README must say so, and must say the tool assists authors and
  does not approve protocols.
- Report results honestly, including weak ones. Never tune on the test set.
- Cite sources (ClinicalTrials.gov / NLM) in the README.
- Python 3.11; pandas, scikit-learn, requests, streamlit, pytest.
  Prefer pure Python for history download; use R/cthist only if Python fails.

## STEP 0 — feasibility gate (do first, max 20 minutes)
Get first-posted AND latest versions for 20 completed interventional trials.
Try in this order and report which one works:
 (a) the current-record API v2: https://clinicaltrials.gov/api/v2/studies/{NCT}
     (free, no key) for the latest version; and
 (b) whatever the ClinicalTrials.gov site uses to serve "record history"
     (inspect the site's history view / network calls; the R package cthist
     documents one working approach); and
 (c) classic.clinicaltrials.gov/ct2/history/{NCT}?V_1=View style pages if still
     available.
If no way to get version histories works, STOP and tell me so I can switch to
the fallback project. Do not fake or simulate histories.

## Step 1 — dataset
- Sample ~400 completed interventional trials, start dates 2010-2020, mixed
  conditions, drug/biological interventions, >=2 arms or single-arm allowed.
- Exclude trials first-posted AFTER their start date (retrospective
  registration) to avoid label noise. Document exclusions and counts.
- Save data/processed/trials.parquet|csv (small, committed) and
  data/processed/versions.* with the first and last pre-completion versions.

## Step 2 — labels (document exact definitions in docs/labels.md)
Compare the FIRST version with the LAST version submitted BEFORE the trial's
completion/results posting (so "estimated -> actual enrollment" at completion
does not count as a change). Three binary labels plus an "any" label:
- eligibility_changed: normalized criteria text differs (strip whitespace,
  case, bullet formatting) AND edit is non-trivial (>5% character change).
- primary_outcome_changed: primary outcome measure titles/timeframes