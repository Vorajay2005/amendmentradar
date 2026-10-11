"""Render docs/model_search.md from docs/model_search_attempts.csv (Phase A). Applies the adoption rule mechanically."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
df = pd.read_csv(ROOT / "docs" / "model_search_attempts.csv")
LAB = {"terminated": "terminated (main)", "terminated_low_accrual": "terminated_low_accrual"}
base = df[df.feature_set.str.startswith("v1 (current features")]
ref = {}
for lab, g in base.groupby("label"):
    r = g.sort_values("val_auc", ascending=False).iloc[0]
    ref[lab] = r  # v1 reference = the better of v1 LR / v1 GB on validation (stricter)

rows, adopt = [], []
for i, r in df.reset_index(drop=True).iterrows():
    is_base = r.feature_set.startswith("v1 (current features")
    cal_ref = "calibration reference" in r.feature_set or r.feature_set.startswith("v1 + isotonic")
    meets = (not is_base and not cal_ref and r.delta_vs_v1_best >= 0.02 and r.ci_low > ref[r.label].ci_high)
    if meets:
        adopt.append(i + 1)
    d = "baseline" if is_base else f"{r.delta_vs_v1_best:+.4f}"
    pd_ci = "" if is_base else r.paired_delta_ci
    br = "" if pd.isna(r.get("brier")) else f"{r.brier:.4f}"
    ec = "" if pd.isna(r.get("ece")) else f"{r.ece:.3f}"
    rows.append(f"| {i+1} | {r.feature_set.strip()} | {r.model.upper()} | {LAB[r.label]} | {r.val_auc:.4f} ({r.ci_low:.4f}-{r.ci_high:.4f}) | {d} | {pd_ci} | {br} | {ec} | {'**YES**' if meets else 'no'} |")

best = df[~df.feature_set.str.startswith("v1 (current")].copy()
best = best[~best.feature_set.str.contains("calibration")]
top = {lab: g.sort_values("delta_vs_v1_best", ascending=False).iloc[0] for lab, g in best.groupby("label")}

txt = f"""# Model search (Phase A: validation only)

Branch `model-v2`. Goal: try to improve on the v1 models honestly, under a fixed protocol. **This page logs every attempt,
including the ones that did not help.** Nothing here touches the 2017-2019 test set (it was dropped while the data were being
read, and no test-period record is evaluated or used to fit anything).

## Protocol
- **Split:** train = start years 2008-2014 (24,686 trials), validation = 2015-2016 (6,908 trials).
  Positives: `terminated` 3,978 train / 1,114 validation (16.1%); `terminated_low_accrual` 1,042 train / **280 validation** (4.1%).
- **v1 baseline:** the current v1 features and models, refit on 2008-2014 (not the shipped models, which saw 2015-2016).
  The reference for the rule is the *better* of v1 LR / v1 GB on validation, i.e. the stricter bar:
  `terminated`: v1 {ref['terminated'].model.upper()} {ref['terminated'].val_auc:.4f} ({ref['terminated'].ci_low:.4f}-{ref['terminated'].ci_high:.4f});
  `terminated_low_accrual`: v1 {ref['terminated_low_accrual'].model.upper()} {ref['terminated_low_accrual'].val_auc:.4f} ({ref['terminated_low_accrual'].ci_low:.4f}-{ref['terminated_low_accrual'].ci_high:.4f}).
- **Anything fitted on data is fitted on training years only:** target encoding (out-of-fold within train), TF-IDF/SVD, the isotonic map
  (fit on out-of-fold training predictions), and hyperparameters (random search / grid by 3-fold CV *inside* 2008-2014; validation was only
  used to score the chosen configuration once).
- **Leakage guard:** every new feature is covered by `tests/test_candidate_features.py` (names pass the v1 guard; behaviour tests: flags read
  only eligibility text; sponsor encoding ignores validation labels, is out-of-fold, and falls back to sponsor class for unseen sponsors;
  SVD vocabulary is train-only; extraction reads no enrollment / locations / status / dates / why-stopped / results).
- **Adoption rule:** adopt only if validation ROC-AUC improves by **>= 0.02** for a label **and** the candidate's 95% bootstrap CI lower
  bound is above v1's CI upper bound. Otherwise keep v1. (1,000 bootstrap resamples of the validation set. The paired-difference column is
  extra information and is not part of the rule.)

## Candidates
1. **Sponsor identity:** out-of-fold smoothed target encoding of the lead sponsor (smoothing m=20, fixed in advance), prior = sponsor-class
   rate; unseen sponsors fall back to sponsor class; plus log(1 + number of training trials by that sponsor).
2. **Text:** TF-IDF (1-2 grams, 20k features) of eligibility text + conditions + intervention names, reduced to 50 SVD components.
3. **Eligibility flags:** prior-therapy mention, biomarker/mutation requirement, ECOG/Karnofsky performance-status requirement, and the number
   of distinct exclusion-criteria types (10 keyword families) in the exclusion section.
4. **Tuning and calibration:** GB random search (10 configurations) and LR `C` grid chosen by train-CV; isotonic calibration.

## All attempts ({len(df)})
Validation ROC-AUC with 95% bootstrap CI. "Delta" is versus the stricter v1 reference above. Brier and ECE (10-bin expected calibration error)
are shown where they were computed.

| # | Feature set | Model | Label | Validation ROC-AUC (95% CI) | Delta vs v1 | Paired delta 95% CI | Brier | ECE | Meets rule? |
|---|---|---|---|---|---|---|---|---|---|
""" + "\n".join(rows) + f"""

## Outcome
**{'No attempt met the rule' if not adopt else 'Attempts meeting the rule: ' + str(adopt)}.** Largest gains over the v1 reference:
- `terminated`: {top['terminated'].feature_set.strip()} ({top['terminated'].model.upper()}), {top['terminated'].delta_vs_v1_best:+.4f} (paired CI {top['terminated'].paired_delta_ci}); needs >= +0.020.
- `terminated_low_accrual`: {top['terminated_low_accrual'].feature_set.strip()} ({top['terminated_low_accrual'].model.upper()}), {top['terminated_low_accrual'].delta_vs_v1_best:+.4f} (paired CI {top['terminated_low_accrual'].paired_delta_ci}); needs >= +0.020.

**Decision: {'keep v1' if not adopt else 'rule met, see above'}.** The candidate features, tuning and calibration move validation AUC by at most about a hundredth, which is
inside the sampling noise of a 280-positive validation slice for low accrual and below the pre-registered bar for both labels.

## What we learned
- **Nothing helps the main label (`terminated`) beyond noise:** best +0.0035 (text SVD, GB). Sponsor identity slightly *hurt* it (-0.004 GB, -0.015 LR), so
  who the sponsor is adds little once sponsor class, phase and area are known, at least for early termination in general.
- **Low accrual shows the only consistent signal:** sponsor identity (+0.012), SVD text (+0.007) and the combination (+0.013) all lean positive for GB, but the
  paired 95% intervals include zero (best: -0.007 to +0.033), so we cannot call it real on a 280-positive validation slice.
- **Eligibility flags are close to useless** (+0.002 / +0.005 for GB; about zero versus v1 LR), consistent with v1 already carrying eligibility length and criteria counts.
- **Tuning does not beat the defaults:** the train-CV-selected GB configurations scored -0.003 (`terminated`) and +0.002 (low accrual) on validation, and tuned LR stayed
  below GB. v1's fixed settings were already near a plateau.
- **Calibration:** v1 GB is already well calibrated on validation (ECE 0.015 / 0.005). Isotonic recalibration leaves ECE essentially unchanged
  (0.014 and 0.007) and cannot move AUC, so it is not worth the extra moving part.

## Notes and caveats
- **Isotonic calibration** is rank-preserving apart from ties, so it cannot raise AUC (rows above show 0 to -0.001). It is judged by Brier and ECE
  instead; see the calibration rows against the "v1 GB uncalibrated" reference rows.
- **Multiple looks.** {len(df)} attempts were scored on the same validation slice. Even the largest gain above would shrink under a correction for
  that, which is one reason the rule demands both a minimum effect size and non-overlapping intervals.
- **A faulty first run is part of the record.** In the first run of this script, the sponsor-identity columns were computed but not passed to the
  model, so the "sponsor identity" and "sponsor + SVD + flags" rows were identical to v1 (GB `terminated` 0.6667, `terminated_low_accrual` 0.7482).
  This was caught because a candidate matched v1 to four decimals. The script now asserts that every candidate's input columns differ from v1's.
  All rows in the table are from the corrected, re-run script; the table was reproduced by a second full run with identical results.
- **A feature was renamed.** `elig_perf_status` tripped the leakage guard because it contains "status" (it means ECOG performance status, not trial
  status). The guard was not loosened; the feature is now `elig_performance_req`.
- **Same caveat as v1:** all features come from the *current* record, so they may include post-registration edits.
- Reproduce: `python scripts/model_search/extract_text.py 2016 <out.csv.gz>` then `python scripts/model_search/phase_a.py <out.csv.gz>` then
  `python scripts/model_search/write_doc.py` (needs the cached API pages in `data/raw/`; run `make data` first on a fresh clone).
"""
(ROOT / "docs" / "model_search.md").write_text(txt)
print("wrote docs/model_search.md; adopt:", adopt)
