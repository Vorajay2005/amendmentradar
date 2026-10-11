# Model search (Phase A: validation only)

Branch `model-v2`. Goal: try to improve on the v1 models honestly, under a fixed protocol. **This page logs every attempt,
including the ones that did not help.** Nothing here touches the 2017-2019 test set (it was dropped while the data were being
read, and no test-period record is evaluated or used to fit anything).

## Protocol
- **Split:** train = start years 2008-2014 (24,686 trials), validation = 2015-2016 (6,908 trials).
  Positives: `terminated` 3,978 train / 1,114 validation (16.1%); `terminated_low_accrual` 1,042 train / **280 validation** (4.1%).
- **v1 baseline:** the current v1 features and models, refit on 2008-2014 (not the shipped models, which saw 2015-2016).
  The reference for the rule is the *better* of v1 LR / v1 GB on validation, i.e. the stricter bar:
  `terminated`: v1 GB 0.6667 (0.6501-0.6824);
  `terminated_low_accrual`: v1 GB 0.7482 (0.7176-0.7755).
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

## All attempts (32)
Validation ROC-AUC with 95% bootstrap CI. "Delta" is versus the stricter v1 reference above. Brier and ECE (10-bin expected calibration error)
are shown where they were computed.

| # | Feature set | Model | Label | Validation ROC-AUC (95% CI) | Delta vs v1 | Paired delta 95% CI | Brier | ECE | Meets rule? |
|---|---|---|---|---|---|---|---|---|---|
| 1 | v1 (current features, default params) | LR | terminated (main) | 0.6460 (0.6285-0.6631) | baseline |  |  |  | no |
| 2 | v1 (current features, default params) | GB | terminated (main) | 0.6667 (0.6501-0.6824) | baseline |  |  |  | no |
| 3 | v1 (current features, default params) | LR | terminated_low_accrual | 0.7359 (0.7053-0.7640) | baseline |  |  |  | no |
| 4 | v1 (current features, default params) | GB | terminated_low_accrual | 0.7482 (0.7176-0.7755) | baseline |  |  |  | no |
| 5 | v1 + sponsor identity (OOF target enc.) | LR | terminated (main) | 0.6520 (0.6348-0.6695) | -0.0147 | (-0.028, -0.001) | 0.1310 | 0.024 | no |
| 6 | v1 + sponsor identity (OOF target enc.) | GB | terminated (main) | 0.6631 (0.6468-0.6796) | -0.0036 | (-0.015, +0.008) | 0.1293 | 0.016 | no |
| 7 | v1 + sponsor identity (OOF target enc.) | LR | terminated_low_accrual | 0.7417 (0.7104-0.7721) | -0.0065 | (-0.022, +0.011) | 0.0376 | 0.007 | no |
| 8 | v1 + sponsor identity (OOF target enc.) | GB | terminated_low_accrual | 0.7603 (0.7316-0.7859) | +0.0121 | (-0.001, +0.025) | 0.0374 | 0.005 | no |
| 9 | v1 + TF-IDF/SVD(50) elig+cond+interv | LR | terminated (main) | 0.6612 (0.6448-0.6794) | -0.0055 | (-0.018, +0.008) | 0.1298 | 0.016 | no |
| 10 | v1 + TF-IDF/SVD(50) elig+cond+interv | GB | terminated (main) | 0.6702 (0.6536-0.6863) | +0.0035 | (-0.007, +0.016) | 0.1293 | 0.010 | no |
| 11 | v1 + TF-IDF/SVD(50) elig+cond+interv | LR | terminated_low_accrual | 0.7393 (0.7095-0.7668) | -0.0088 | (-0.026, +0.009) | 0.0377 | 0.007 | no |
| 12 | v1 + TF-IDF/SVD(50) elig+cond+interv | GB | terminated_low_accrual | 0.7556 (0.7269-0.7825) | +0.0074 | (-0.009, +0.022) | 0.0373 | 0.004 | no |
| 13 | v1 + eligibility flags | LR | terminated (main) | 0.6460 (0.6284-0.6631) | -0.0207 | (-0.031, -0.009) | 0.1306 | 0.012 | no |
| 14 | v1 + eligibility flags | GB | terminated (main) | 0.6690 (0.6525-0.6853) | +0.0023 | (-0.002, +0.007) | 0.1290 | 0.012 | no |
| 15 | v1 + eligibility flags | LR | terminated_low_accrual | 0.7389 (0.7080-0.7670) | -0.0092 | (-0.023, +0.004) | 0.0375 | 0.005 | no |
| 16 | v1 + eligibility flags | GB | terminated_low_accrual | 0.7526 (0.7224-0.7793) | +0.0045 | (-0.002, +0.011) | 0.0374 | 0.004 | no |
| 17 | v1 + sponsor + SVD + flags | LR | terminated (main) | 0.6651 (0.6477-0.6829) | -0.0016 | (-0.016, +0.013) | 0.1300 | 0.024 | no |
| 18 | v1 + sponsor + SVD + flags | GB | terminated (main) | 0.6691 (0.6521-0.6857) | +0.0024 | (-0.012, +0.017) | 0.1291 | 0.015 | no |
| 19 | v1 + sponsor + SVD + flags | LR | terminated_low_accrual | 0.7421 (0.7126-0.7702) | -0.0061 | (-0.025, +0.014) | 0.0377 | 0.007 | no |
| 20 | v1 + sponsor + SVD + flags | GB | terminated_low_accrual | 0.7611 (0.7315-0.7875) | +0.0129 | (-0.007, +0.033) | 0.0374 | 0.004 | no |
| 21 | v1 features + tuned GB (train-CV search) | GB | terminated (main) | 0.6634 (0.6463-0.6797) | -0.0033 | (-0.009, +0.003) | 0.1291 | 0.011 | no |
| 22 | v1 features + tuned LR (C by train-CV) | LR | terminated (main) | 0.6471 (0.6294-0.6640) | -0.0196 | (-0.030, -0.009) | 0.1306 | 0.014 | no |
| 23 | v1 features + tuned GB (train-CV search) | GB | terminated_low_accrual | 0.7504 (0.7212-0.7770) | +0.0023 | (-0.002, +0.006) | 0.0374 | 0.006 | no |
| 24 | v1 features + tuned LR (C by train-CV) | LR | terminated_low_accrual | 0.7399 (0.7092-0.7673) | -0.0083 | (-0.022, +0.005) | 0.0376 | 0.006 | no |
| 25 | v1 + sponsor + SVD + flags + tuned GB | GB | terminated (main) | 0.6700 (0.6541-0.6858) | +0.0033 | (-0.011, +0.018) | 0.1294 | 0.021 | no |
| 26 | + isotonic calibration (map fit on train OOF) | GB | terminated (main) | 0.6688 (0.6525-0.6847) | +0.0021 | (-0.012, +0.017) | 0.1292 | 0.015 | no |
| 27 | v1 + sponsor + SVD + flags + tuned GB | GB | terminated_low_accrual | 0.7599 (0.7315-0.7876) | +0.0117 | (-0.007, +0.029) | 0.0374 | 0.005 | no |
| 28 | + isotonic calibration (map fit on train OOF) | GB | terminated_low_accrual | 0.7591 (0.7301-0.7863) | +0.0109 | (-0.008, +0.029) | 0.0374 | 0.003 | no |
| 29 | v1 + isotonic calibration (map fit on train OOF) | GB | terminated (main) | 0.6669 (0.6504-0.6833) | +0.0002 | (-0.001, +0.001) | 0.1291 | 0.014 | no |
| 30 | v1 GB uncalibrated (calibration reference) | GB | terminated (main) | 0.6667 (0.6501-0.6824) | +0.0000 | (+0.000, +0.000) | 0.1291 | 0.015 | no |
| 31 | v1 + isotonic calibration (map fit on train OOF) | GB | terminated_low_accrual | 0.7470 (0.7159-0.7744) | -0.0012 | (-0.003, +0.001) | 0.0376 | 0.007 | no |
| 32 | v1 GB uncalibrated (calibration reference) | GB | terminated_low_accrual | 0.7482 (0.7176-0.7755) | +0.0000 | (+0.000, +0.000) | 0.0375 | 0.005 | no |

## Outcome
**No attempt met the rule.** Largest gains over the v1 reference:
- `terminated`: v1 + TF-IDF/SVD(50) elig+cond+interv (GB), +0.0035 (paired CI (-0.007, +0.016)); needs >= +0.020.
- `terminated_low_accrual`: v1 + sponsor + SVD + flags (GB), +0.0129 (paired CI (-0.007, +0.033)); needs >= +0.020.

**Decision: keep v1.** The candidate features, tuning and calibration move validation AUC by at most about a hundredth, which is
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
- **Multiple looks.** 32 attempts were scored on the same validation slice. Even the largest gain above would shrink under a correction for
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
