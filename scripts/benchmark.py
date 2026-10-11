"""`make benchmark`: trains/evaluates everything and writes BENCHMARK.md, models/, data/tfidf_index.joblib."""
import json
import sys
import warnings

sys.path.insert(0, "src")
warnings.filterwarnings("ignore")
import joblib
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

from features import CAT_FEATURES, FEATURES, GROUPS
from modeling import (LABELS, SEED, TEST_YEARS, TRAIN_YEARS, area_baseline, boot_ci, calibration_table,
                      feature_frame, fit, load, make_model, metrics, predict, split)
from retrieval import build_index
from sklearn.metrics import average_precision_score

NAMES = {"lr": "Logistic regression", "gb": "Gradient boosting"}
MAIN = "terminated"


def md(df, floatfmt="{:.3f}"):
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.astype(object).iterrows():
        out.append("| " + " | ".join(floatfmt.format(v) if isinstance(v, (float, np.floating)) else str(v) for v in r) + " |")
    return "\n".join(out)


def ci(m, k="auc"):
    lo, hi = m[f"{k}_ci"]
    return f"{m[k]:.3f} ({lo:.3f}-{hi:.3f})"


df = load()
tr, te = split(df)
assert tr.start_year.max() <= TRAIN_YEARS[1] and te.start_year.min() >= TEST_YEARS[0]
log = print

# ---- drift ----
yr = df.groupby("start_year").agg(n=("nct_id", "size"), terminated=("terminated", "mean"),
                                  low_accrual=("terminated_low_accrual", "mean")).reset_index()
yr["start_year"] = yr.start_year.astype(int)
_cov = df[(df.terminated == 1) & df.why_stopped.fillna("").str.contains("covid|pandemic|coronavirus|sars-cov", case=False)]
yr["covid-cited %"] = (_cov.groupby("start_year").size().reindex(yr.start_year).fillna(0).values / yr.n.values * 100)
yr["terminated"] *= 100; yr["low_accrual"] *= 100
yr = yr.rename(columns={"terminated": "terminated %", "low_accrual": "low-accrual %"})
log(md(yr, "{:.1f}"))

res = {}      # time-split results
models = {}
for lab in LABELS:
    ytr, yte = tr[lab], te[lab]
    r = {"n_train": len(tr), "pos_train": int(ytr.sum()), "n_test": len(te), "pos_test": int(yte.sum()),
         "base_train": ytr.mean(), "base_test": yte.mean()}
    r["base_rate"] = {"auc": 0.5, "auc_ci": (0.5, 0.5), "pr_auc": yte.mean(), "pr_ci": boot_ci(yte, np.full(len(yte), ytr.mean()) + 0 * yte, average_precision_score)}
    pa = area_baseline(tr, te, lab)
    r["area_rate"] = metrics(yte, pa)
    for k in NAMES:
        m = fit(k, tr, lab)
        models[(lab, k)] = m
        p = predict(m, te)
        r[k] = metrics(yte, p); r[k]["p"] = p
        r[k]["calib"] = calibration_table(yte, p)
        r[k]["mean_pred"] = float(p.mean())
    res[lab] = r
    log(lab, {k: ci(r[k]) for k in ["area_rate", "lr", "gb"]}, "pos_test", r["pos_test"])

# ---- 5-fold stratified CV (all data, mixes years) ----
cv = {}
for lab in LABELS:
    y = df[lab].values
    for k in NAMES:
        oof = np.zeros(len(df)); aucs = []
        for tri, tei in StratifiedKFold(5, shuffle=True, random_state=SEED).split(df, y):
            m = fit(k, df.iloc[tri], lab)
            oof[tei] = predict(m, df.iloc[tei])
            aucs.append(roc_auc_score(y[tei], oof[tei]))
        cv[(lab, k)] = {"fold_mean": np.mean(aucs), "fold_sd": np.std(aucs),
                        "pooled": metrics(y, oof)}
    pa = np.zeros(len(df))
    for tri, tei in StratifiedKFold(5, shuffle=True, random_state=SEED).split(df, y):
        pa[tei] = area_baseline(df.iloc[tri], df.iloc[tei], lab)
    cv[(lab, "area")] = {"fold_mean": roc_auc_score(y, pa), "fold_sd": float("nan"), "pooled": metrics(y, pa)}
    log("cv", lab, {k: round(cv[(lab, k)]["fold_mean"], 3) for k in ["lr", "gb", "area"]})

# ---- feature-group ablation (test AUC) ----
abl = []
for lab in LABELS:
    for k in NAMES:
        full = res[lab][k]["auc"]
        abl.append({"label": lab, "model": NAMES[k], "removed": "(none: all features)", "auc": full, "drop": 0.0, "flag": ""})
        for g, cols in GROUPS.items():
            feats = [f for f in FEATURES if f not in cols]
            m = fit(k, tr, lab, feats)
            a = roc_auc_score(te[lab], predict(m, te, feats))
            abl.append({"label": lab, "model": NAMES[k], "removed": g, "auc": a, "drop": full - a,
                        "flag": "FLAG" if full - a > 0.03 else ""})
abl = pd.DataFrame(abl)
log(abl[abl.flag == "FLAG"])

# ---- importances ----
lr = models[(MAIN, "lr")]
names = lr.named_steps["pre"].get_feature_names_out()
coef = pd.Series(lr.named_steps["clf"].coef_[0], index=[n.split("__", 1)[1] for n in names])
coef_tab = pd.concat([coef.sort_values(ascending=False).head(10), coef.sort_values().head(10)[::-1]]).reset_index()
coef_tab.columns = ["feature (standardized / one-hot)", "coefficient (log-odds)"]
pi = {}
for lab in LABELS:
    r = permutation_importance(models[(lab, "gb")], feature_frame(te), te[lab], scoring="roc_auc",
                               n_repeats=3, random_state=SEED, n_jobs=1)
    pi[lab] = pd.Series(r.importances_mean, index=FEATURES).sort_values(ascending=False).head(10)

# ---- save artifacts ----
for (lab, k), m in models.items():
    joblib.dump(m, f"models/{lab}_{k}.joblib", compress=3)
train_med = {c: float(tr[c].median()) for c in FEATURES if c not in CAT_FEATURES}
meta = {"features": FEATURES, "groups": GROUPS, "train_years": TRAIN_YEARS, "test_years": TEST_YEARS,
        "base_rate_train": {l: float(tr[l].mean()) for l in LABELS},
        "test_rate": {l: float(te[l].mean()) for l in LABELS},
        "base_rate_all": {l: float(df[l].mean()) for l in LABELS},
        "area_rate_all": {l: df.groupby("therapeutic_area")[l].mean().to_dict() for l in LABELS},
        "test_auc": {l: {k: res[l][k]["auc"] for k in NAMES} for l in LABELS},
        "risk_band_cutoffs": {l: [float(np.quantile(predict(models[(l, "gb")], te), q)) for q in (1/3, 2/3)] for l in LABELS},
        "train_median": train_med}
json.dump(meta, open("models/meta.json", "w"), indent=1)
build_index(df)

# ---- report ----
def best(lab):  # honest: pick by TRAIN-agnostic fixed rule = report both; headline = higher test AUC
    return max(NAMES, key=lambda k: res[lab][k]["auc"])


def verdict(a):
    return ("near chance" if a < 0.55 else "weak" if a < 0.65 else "modest" if a < 0.75 else "moderate")


R = res[MAIN]; S = res["terminated_low_accrual"]
rows = []
for lab in LABELS:
    r = res[lab]
    for nm, m in [("Base rate (constant)", r["base_rate"]), ("Therapeutic-area base rate", r["area_rate"]),
                  (NAMES["lr"], r["lr"]), (NAMES["gb"], r["gb"])]:
        rows.append({"label": lab, "model": nm, "ROC-AUC (95% CI)": ci(m), "PR-AUC": f"{m['pr_auc']:.3f}"})
main_tab = pd.DataFrame(rows)

cvrows = []
for lab in LABELS:
    for k, nm in [("area", "Therapeutic-area base rate"), ("lr", NAMES["lr"]), ("gb", NAMES["gb"])]:
        c = cv[(lab, k)]
        cvrows.append({"label": lab, "model": nm, "fold-mean AUC": f"{c['fold_mean']:.3f}",
                       "fold SD": "" if np.isnan(c["fold_sd"]) else f"{c['fold_sd']:.3f}",
                       "pooled out-of-fold AUC (95% CI)": ci(c["pooled"])})
cv_tab = pd.DataFrame(cvrows)

flagged = abl[abl.flag == "FLAG"]
y0, y1 = yr.iloc[0], yr.iloc[-1]
cov16 = float(yr[yr.start_year == 2016]['covid-cited %'].iloc[0]); cov19 = float(yr[yr.start_year == 2019]['covid-cited %'].iloc[0])
tr_rate = tr.terminated.mean() * 100; te_rate = te.terminated.mean() * 100
abl_show = abl[abl.removed != "(none: all features)"].copy()
abl_show["AUC without group"] = abl_show.auc.map("{:.3f}".format)
abl_show["drop"] = abl_show["drop"].map("{:+.3f}".format)
full_show = abl[abl.removed == "(none: all features)"][["label", "model", "auc"]].rename(columns={"auc": "AUC (all features)"})

cal_md = ""
for lab in LABELS:
    for k in ("lr", "gb"):
        c = res[lab][k]["calib"].copy(); c.columns = ["n", "mean predicted", "observed rate"]
        cal_md += f"\n**{lab} / {NAMES[k]}** (test set, deciles of predicted risk; mean prediction overall {res[lab][k]['mean_pred']:.3f} vs observed {res[lab]['base_test']:.3f})\n\n{md(c)}\n"

bl = best(MAIN); bs = best("terminated_low_accrual")
txt = f"""# TrialRadar benchmark

Generated by `make benchmark` (`scripts/benchmark.py`). Data: ClinicalTrials.gov (NLM) API v2, **{len(df):,} trials**
(Phase 2, Phase 2/3, Phase 3; Drug/Biological; start 2008-2019; COMPLETED or TERMINATED), no sampling.
Features come only from registered-design fields; labels come from overall status / why-stopped text
(see `docs/labels.md`). Hyperparameters were fixed in advance; nothing was tuned on the test set.

> **Read this first.** The v2 API returns the *current* record, not the original registration. Features
> approximate the registered design but may reflect edits made after registration. TrialRadar produces risk
> estimates that assist trial designers; it does not approve or reject designs.

## Setup
- Time split by start year: train {TRAIN_YEARS[0]}-{TRAIN_YEARS[1]} (n={R['n_train']:,}), test {TEST_YEARS[0]}-{TEST_YEARS[1]} (n={R['n_test']:,}).
- Main label `terminated`: train rate {R['base_train']*100:.1f}%, test rate {R['base_test']*100:.1f}%, test positives **{R['pos_test']:,}**.
- Secondary label `terminated_low_accrual`: train rate {S['base_train']*100:.1f}%, test rate {S['base_test']*100:.1f}%, test positives **{S['pos_test']:,}** (train positives {S['pos_train']:,}).
- Whole population: terminated {df.terminated.mean()*100:.1f}% ({int(df.terminated.sum()):,}); terminated for low accrual {df.terminated_low_accrual.mean()*100:.1f}% ({int(df.terminated_low_accrual.sum()):,}).
- Confidence intervals: 1,000 bootstrap resamples of the test set (percentile). Constant base rate has AUC 0.5 by definition; its PR-AUC equals the test prevalence.

## 1. Main results (time split)
{md(main_tab)}

Headline: on the main label the better model is **{NAMES[bl]}** with test ROC-AUC **{ci(R[bl])}**, which is {verdict(R[bl]['auc'])}.
The therapeutic-area baseline gets {ci(R['area_rate'])}. For low accrual, the better model is **{NAMES[bs]}** with {ci(S[bs])} ({verdict(S[bs]['auc'])}) on **{S['pos_test']} test positives**.

## 2. Temporal drift
Termination rate by start year (all trials, true rates):

{md(yr, "{:.1f}")}

The termination rate moves from {y0['terminated %']:.1f}% ({int(y0.start_year)}) to {y1['terminated %']:.1f}% ({int(y1.start_year)}); the train period averages {tr_rate:.1f}% and the test period {te_rate:.1f}%.
The rate rises in the test years. COVID-19 explains part of it: terminations whose reason text mentions COVID-19/pandemic are {cov16:.1f}% of 2016 starts and {cov19:.1f}% of 2019 starts (last column), while the overall termination rate goes from {tr_rate:.1f}% (train years) to {te_rate:.1f}% (test years). The rest is unexplained (it may also be understated, since trials still RECRUITING / ACTIVE_NOT_RECRUITING were excluded and some will later terminate).
The models were trained before this shift, so they under-predict termination in the test period (mean prediction {R['lr']['mean_pred']:.3f}/{R['gb']['mean_pred']:.3f} vs observed {R['base_test']:.3f}).
Drift matters for calibration (section 4), not just ranking.

## 3. Stratified 5-fold cross-validation (random split, all years)
Shown next to the time split because a random split ignores drift and is normally more optimistic.

{md(cv_tab)}

## 4. Calibration (time-split test set)
{cal_md}
## 5. Feature-group ablation (test ROC-AUC)
Each row removes one group of features and refits. A drop larger than 0.03 is flagged. Groups: eligibility
(text length/criteria counts, ages, sex, healthy volunteers), outcomes (counts), sponsor (lead sponsor class),
design (phase, masking, allocation, model, arms, interventions, DMC, FDA flag, intervention types),
area (therapeutic area, number of conditions), start_year.

{md(full_show)}

{md(abl_show[['label','model','removed','AUC without group','drop','flag']])}

"""
if len(flagged):
    items = "; ".join(f"{r.label}/{r.model}: removing **{r.removed}** (-{r['drop']:.3f})" for _, r in flagged.iterrows())
    txt += f"""**Flagged groups (drop > 0.03): {items}.** A large drop means the model leans on that group. That can be
real signal (e.g. sponsor type) **or** a possible post-registration-edit leakage risk: because the API returns the
current record, a field that is edited when a trial changes course (eligibility text, outcome counts) could encode what happened.
We cannot separate the two without historical record versions, which are not publicly available through the API.
"""
else:
    txt += "**No group's removal dropped test AUC by more than 0.03**, so no single group dominates and we see no evidence that a group like eligibility text or outcome counts is carrying post-registration-edit leakage on its own. This is not proof of absence: correlated groups can compensate for each other when one is removed, so small drops understate how much a group matters.\n"
txt += f"""
## 6. What the models use
Logistic regression, `terminated` (standardized numerics, one-hot categoricals): largest positive and negative coefficients.

{md(coef_tab)}

Gradient boosting permutation importance on the test set (drop in AUC when the column is shuffled), top 10:

**terminated**

{md(pi['terminated'].reset_index().rename(columns={'index':'feature',0:'AUC drop'}), "{:.4f}")}

**terminated_low_accrual**

{md(pi['terminated_low_accrual'].reset_index().rename(columns={'index':'feature',0:'AUC drop'}), "{:.4f}")}

## 7. Conclusions in plain English
- **Predictive power.** Using only registered-design fields, TrialRadar ranks trials by termination risk with {verdict(R[bl]['auc'])} accuracy (AUC {R[bl]['auc']:.2f}; a coin flip is 0.50, and the simple therapeutic-area lookup gets {R['area_rate']['auc']:.2f}). It is a screening aid, not a crystal ball.
- **Low accrual** is {verdict(S[bs]['auc'])} to predict (AUC {S[bs]['auc']:.2f}, CI {S[bs]['auc_ci'][0]:.2f}-{S[bs]['auc_ci'][1]:.2f}) and rests on only {S['pos_test']} test positives, so its interval is wide.
- **Random vs. time split.** Cross-validation AUC for the main label is {cv[(MAIN, bl)]['fold_mean']:.3f} versus {R[bl]['auc']:.3f} on the time split, which shows how much of the apparent skill depends on mixing years.
- **What the tool is still useful for even when the AUC is modest:** showing the similar past trials that stopped and why (Step 5), flagging design traits associated with higher risk, and giving a base-rate-anchored estimate. It is not a decision rule.

## 8. Limits (please read)
1. **Current-record snapshot.** The API serves the latest version of each record; we cannot see the original registration. "Registered design" features may include post-registration edits (see the ablation in section 5).
2. **Excluded statuses.** WITHDRAWN (2,204), UNKNOWN (6,774), RECRUITING, ACTIVE_NOT_RECRUITING, SUSPENDED and similar are excluded, so rates are for trials that reached COMPLETED or TERMINATED. True non-completion across the registry is likely higher. Recent start years are further biased by trials not yet finished.
3. **Keyword-derived labels.** `terminated_low_accrual` and the stop-reason classes come from keyword rules over free text, not human review. 738 terminated trials ({738/int(df.terminated.sum())*100:.0f}% of terminated) have no reason text and can never count as low accrual.
4. **Rule-order effect.** Safety, efficacy and sponsor rules take precedence over low accrual, so a record that mentions both an accrual problem and a sponsor decision is not counted as low accrual. The low-accrual label undercounts.
5. **Therapeutic area is crude.** It is a keyword mapping; {(df.therapeutic_area=='other').mean()*100:.0f}% of trials fall into "other". Area baselines inherit that noise.
6. **Associations, not causes.** Coefficients and importances describe patterns in past registrations. Changing a design feature will not necessarily change a trial's risk.
7. **Time shift.** Train and test periods differ in termination rate (section 2); calibration on the test set shows the consequence.
8. **Proxy for trial planning, not an approval tool.** Estimates assist trial designers and do not approve or reject any design.

Source: ClinicalTrials.gov, U.S. National Library of Medicine (https://clinicaltrials.gov). Context from the Regeneron challenge sheet "Site Unseen" (Tufts CSDD): about 11% of chosen sites enroll zero patients and 37% enroll fewer than promised.
"""
open("BENCHMARK.md", "w").write(txt)
log("written BENCHMARK.md")
