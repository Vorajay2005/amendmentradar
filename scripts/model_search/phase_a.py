"""Phase A model search. VALIDATION ONLY.

PROTOCOL
  * train = start year 2008-2014, validation = 2015-2016.
  * The 2017-2019 test period is dropped while the CSV is being read (chunked filter) and is never evaluated.
  * Every attempt is appended to the attempts log and written to docs/model_search.md (+ .csv), including
    attempts that did not help.
  * Anything fitted on data (target encoding, TF-IDF/SVD, hyperparameter search, isotonic map) is fitted on
    TRAINING years only; hyperparameters are chosen by cross-validation inside the training years.
  * Adoption rule: validation ROC-AUC up by >= 0.02 for a label AND the candidate's 95% bootstrap CI lower bound
    above v1's CI upper bound (v1 = the better of v1 LR / v1 GB on validation, which is the stricter reference).
"""
import itertools
import json
import re
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import TruncatedSVD
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from features import CAT_FEATURES, FEATURES, NUM_FEATURES, FORBIDDEN_TOKENS, assert_no_leakage
import modeling

SEED = 0
LABELS = ["terminated", "terminated_low_accrual"]
TRAIN = (2008, 2014)
VAL = (2015, 2016)
WORK = Path(sys.argv[1]) if len(sys.argv) > 1 else None  # text_le2016.csv.gz from extract_text.py

# Names of every candidate feature (imported by tests/test_candidate_features.py for the leakage guard)
FLAG_COLS = ["elig_prior_therapy", "elig_biomarker", "elig_performance_req", "elig_excl_types"]
SPON_COLS = ["sponsor_te", "sponsor_log_n"]
SVD_K = 50
SVD_COLS = [f"txt_svd_{i}" for i in range(SVD_K)]
NEW_FEATURE_COLUMNS = FLAG_COLS + SPON_COLS + SVD_COLS


# ------------------------------------------------------------------ data (test period never loaded)
def load_le2016():
    parts = []
    for ch in pd.read_csv(ROOT / "data/processed/trials.csv.gz", keep_default_na=False, na_values=[""], chunksize=4000):
        parts.append(ch[ch.start_year <= VAL[1]])
    df = pd.concat(parts, ignore_index=True)
    assert df.start_year.max() <= VAL[1]
    t = pd.read_csv(WORK, keep_default_na=False)
    assert len(t) and t.nct_id.isin(df.nct_id).all()
    return df.merge(t, on="nct_id", how="left")


# ------------------------------------------------------------------ new features
def norm_name(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


class SponsorEncoder:
    """Out-of-fold smoothed target encoding of lead-sponsor identity, fit on TRAIN only.

    Unseen sponsors fall back to the sponsor-class rate. Also emits log(1 + #training trials of the sponsor)."""
    M = 20  # smoothing strength, fixed a priori

    def fit_transform(self, tr, label):
        self.label = label
        self.class_rate = tr.groupby("sponsor_class")[label].mean()
        self.global_rate = tr[label].mean()
        out_te = np.zeros(len(tr)); out_n = np.zeros(len(tr))
        names = tr.sponsor_name.map(norm_name).values
        for a, b in StratifiedKFold(5, shuffle=True, random_state=SEED).split(tr, tr[label]):
            te, n = self._encode(tr.iloc[a], names[a], tr.iloc[b], names[b])
            out_te[b], out_n[b] = te, n
        self._names = names; self._tr = tr
        self.fit_stats = self._stats(tr, names)
        return pd.DataFrame({"sponsor_te": out_te, "sponsor_log_n": np.log1p(out_n)}, index=tr.index)

    def _stats(self, tr, names):
        g = pd.DataFrame({"n": names, "y": tr[self.label].values}).groupby("n").y.agg(["sum", "count"])
        return g

    def _encode(self, ref, ref_names, tgt, tgt_names):
        st = self._stats(ref, ref_names)
        prior = tgt.sponsor_class.map(ref.groupby("sponsor_class")[self.label].mean()).fillna(ref[self.label].mean()).values
        s = pd.Series(tgt_names).map(st["sum"]).fillna(0).values
        c = pd.Series(tgt_names).map(st["count"]).fillna(0).values
        return (s + self.M * prior) / (c + self.M), c

    def transform(self, tgt):
        te, n = self._encode(self._tr, self._names, tgt, tgt.sponsor_name.map(norm_name).values)
        return pd.DataFrame({"sponsor_te": te, "sponsor_log_n": np.log1p(n)}, index=tgt.index)


class TextSVD:
    """TF-IDF + truncated SVD of eligibility + conditions + intervention names; fit on TRAIN only."""
    def __init__(self, k=50):
        self.k = k

    @staticmethod
    def doc(d):
        return (d.eligibility_text.fillna("") + " . " + d.conditions.fillna("") + " . " + d.interventions.fillna("")).str.lower()

    def fit_transform(self, tr):
        self.vec = TfidfVectorizer(max_features=20000, min_df=5, ngram_range=(1, 2), sublinear_tf=True, stop_words="english", dtype="float32")
        self.svd = TruncatedSVD(self.k, random_state=SEED)
        z = self.svd.fit_transform(self.vec.fit_transform(self.doc(tr)))
        return pd.DataFrame(z, columns=[f"txt_svd_{i}" for i in range(self.k)], index=tr.index)

    def transform(self, d):
        return pd.DataFrame(self.svd.transform(self.vec.transform(self.doc(d))), columns=[f"txt_svd_{i}" for i in range(self.k)], index=d.index)


PRIOR = re.compile(r"prior (?:\w+ ){0,3}(?:therapy|therapies|treatment|chemotherapy|regimen|line)|previous(?:ly)? (?:\w+ ){0,3}(?:treated|therapy|treatment|chemotherapy)|refractory|relapsed|treatment[- ]na[iï]ve|failed", re.I)
BIOMARKER = re.compile(r"mutation|biomarker|positive for|expression|her2|egfr|pd-?l1|alk\b|braf|kras|brca|genotype|hla-|amplification|receptor[- ](?:positive|negative)|status of", re.I)
PERF = re.compile(r"ecog|karnofsky|performance status|who performance|lansky", re.I)
EXCL_TYPES = {
    "pregnancy": r"pregnan|breast-?feeding|lactat|childbearing|contracepti",
    "infection": r"infection|hiv|hepatitis|tubercul|sepsis|\bhbv\b|\bhcv\b",
    "cardiac": r"cardi|myocardial|heart failure|arrhythm|qtc?\b|angina|stroke|hypertension",
    "renal_hepatic": r"renal|kidney|creatinine|hepatic|liver|bilirubin|\balt\b|\bast\b",
    "other_malignancy": r"other (?:active |primary )?malignan|second (?:primary )?malignan|prior malignan|history of (?:cancer|malignan)",
    "psych_substance": r"psychiatr|alcohol|substance|drug abuse|dementia|depress",
    "allergy": r"allerg|hypersensitiv|anaphyla",
    "concomitant_meds": r"concomitant|concurrent|inhibitor|inducer|anticoagul|immunosuppress|steroid|corticosteroid",
    "lab_abnormal": r"platelet|neutrophil|hemoglobin|haemoglobin|anc\b|lab(?:oratory)? (?:values|abnormal)|white blood",
    "investigational": r"investigational|participat\w+ in (?:another|any) (?:clinical|study|trial)|another (?:clinical )?(?:trial|study)",
}
EXCL_RX = {k: re.compile(v, re.I) for k, v in EXCL_TYPES.items()}


def eligibility_flags(d):
    out = []
    for txt in d.eligibility_text.fillna(""):
        m = re.search(r"exclusion\s+criteria", txt, re.I)
        exc = txt[m.start():] if m else ""
        out.append((int(bool(PRIOR.search(txt))), int(bool(BIOMARKER.search(txt))), int(bool(PERF.search(txt))),
                    sum(bool(rx.search(exc)) for rx in EXCL_RX.values())))
    return pd.DataFrame(out, columns=FLAG_COLS, index=d.index)


# ------------------------------------------------------------------ models
GB_DEFAULT = dict(learning_rate=0.05, max_iter=300, max_depth=4, min_samples_leaf=50, l2_regularization=1.0)  # = v1


def make_pipe(kind, num, cat, params=None):
    steps = [("imp", SimpleImputer(strategy="median"))] + ([("sc", StandardScaler())] if kind == "lr" else [])
    pre = ColumnTransformer([("num", Pipeline(steps), num), ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20, sparse_output=False), cat)])
    if kind == "lr":
        clf = LogisticRegression(max_iter=3000, C=(params or {}).get("C", 1.0))
    else:
        p = dict(GB_DEFAULT); p.update(params or {})
        clf = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.15, n_iter_no_change=20, random_state=SEED, **p)
    return Pipeline([("pre", pre), ("clf", clf)])


def boot(y, p, ref=None, n=1000):
    """AUC, 95% CI; if ref given also the paired difference CI vs ref scores on the same resamples."""
    y, p = np.asarray(y), np.asarray(p); rng = np.random.default_rng(SEED)
    a, d = [], []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() == y[i].max():
            continue
        x = roc_auc_score(y[i], p[i]); a.append(x)
        if ref is not None:
            d.append(x - roc_auc_score(y[i], ref[i]))
    r = {"auc": roc_auc_score(y, p), "lo": float(np.percentile(a, 2.5)), "hi": float(np.percentile(a, 97.5))}
    if ref is not None:
        r["dlo"], r["dhi"] = float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))
    return r


def ece(y, p, bins=10):
    d = pd.DataFrame({"y": y, "p": p}); d["b"] = pd.qcut(d.p, bins, duplicates="drop")
    g = d.groupby("b", observed=True).agg(n=("y", "size"), p=("p", "mean"), y=("y", "mean"))
    return float((g.n * (g.p - g.y).abs()).sum() / g.n.sum())


ATTEMPTS = []


def record(featset, label, model, scores, y, v1ref, note="", extra=None):
    b = boot(y, scores, ref=v1ref)
    row = {"feature_set": featset, "model": model, "label": label, "val_auc": round(b["auc"], 4), "ci_low": round(b["lo"], 4), "ci_high": round(b["hi"], 4),
           "delta_vs_v1_best": None if v1ref is None else round(b["auc"] - roc_auc_score(y, v1ref), 4),
           "paired_delta_ci": None if v1ref is None else f"({b['dlo']:+.3f}, {b['dhi']:+.3f})", "note": note}
    row.update(extra or {})
    ATTEMPTS.append(row)
    print(f"{featset:42} {model:3} {label:24} {b['auc']:.4f} ({b['lo']:.4f}-{b['hi']:.4f})  d={row['delta_vs_v1_best']}", flush=True)
    return row


def main():
    t0 = time.time()
    df = load_le2016()
    tr = df[df.start_year.between(*TRAIN)].reset_index(drop=True)
    va = df[df.start_year.between(*VAL)].reset_index(drop=True)
    print("train", len(tr), "val", len(va), "| years", tr.start_year.min(), tr.start_year.max(), va.start_year.min(), va.start_year.max())
    for lab in LABELS:
        print(lab, "train pos", int(tr[lab].sum()), "val pos", int(va[lab].sum()), "val rate %.3f" % va[lab].mean())

    # row-wise features that need no fitting
    for d in (tr, va):
        d[FLAG_COLS] = eligibility_flags(d)
    svd = TextSVD(SVD_K); Ztr = svd.fit_transform(tr); Zva = svd.transform(va)
    tr = pd.concat([tr, Ztr], axis=1); va = pd.concat([va, Zva], axis=1)
    FLAGS, SVDC, SPON = FLAG_COLS, list(Ztr.columns), SPON_COLS
    assert SVDC == SVD_COLS

    # leakage guard on every new column name
    assert_no_leakage(FLAGS + SVDC + SPON)

    v1 = {}      # v1 val scores per (kind,label)
    base = {}
    for lab in LABELS:
        for kind in ("lr", "gb"):
            m = modeling.make_model(kind, FEATURES); m.fit(tr[FEATURES], tr[lab])
            v1[(kind, lab)] = m.predict_proba(va[FEATURES])[:, 1]
            m2 = make_pipe(kind, NUM_FEATURES, CAT_FEATURES); m2.fit(tr[FEATURES], tr[lab])
            assert abs(roc_auc_score(va[lab], m2.predict_proba(va[FEATURES])[:, 1]) - roc_auc_score(va[lab], v1[(kind, lab)])) < 1e-9, "builder != v1"
        best = max(("lr", "gb"), key=lambda k: roc_auc_score(va[lab], v1[(k, lab)]))
        base[lab] = best
        for kind in ("lr", "gb"):
            record("v1 (current features, default params)", lab, kind, v1[(kind, lab)], va[lab].values, None, note="baseline refit on 2008-2014")
        print("  v1 reference for", lab, "=", best)
    ref = {lab: v1[(base[lab], lab)] for lab in LABELS}

    def run(featset, num_extra, cat_extra=(), sponsor=False, params=None, calibrate=False, tag=""):
        res = {}
        for lab in LABELS:
            Xtr, Xva = tr.copy(), va.copy()
            if sponsor:
                enc = SponsorEncoder(); Xtr[SPON] = enc.fit_transform(tr, lab); Xva[SPON] = enc.transform(va)
            num = NUM_FEATURES + list(num_extra) + (SPON if sponsor else []); cat = CAT_FEATURES + list(cat_extra)
            for kind in ("lr", "gb"):
                p = (params or {}).get((lab, kind))
                assert set(num + cat) != set(FEATURES), 'candidate identical to v1 inputs'
                m = make_pipe(kind, num, cat, p); m.fit(Xtr[num + cat], Xtr[lab])
                s = m.predict_proba(Xva[num + cat])[:, 1]
                extra = {"brier": round(brier_score_loss(va[lab], s), 5), "ece": round(ece(va[lab].values, s), 4)}
                note = tag + (f" params={p}" if p else "")
                record(featset, lab, kind, s, va[lab].values, ref[lab], note=note, extra=extra)
                res[(lab, kind)] = (m, s, Xtr, Xva, num + cat)
        return res

    run("v1 + sponsor identity (OOF target enc.)", [], sponsor=True)
    run("v1 + TF-IDF/SVD(50) elig+cond+interv", SVDC)
    run("v1 + eligibility flags", FLAGS)
    allres = run("v1 + sponsor + SVD + flags", SVDC + FLAGS, sponsor=True)

    # ---- tuning: random search by 3-fold CV INSIDE the training years only
    rng = np.random.default_rng(SEED)
    grid = [dict(learning_rate=float(rng.choice([0.03, 0.05, 0.1])), max_depth=int(rng.choice([3, 4, 6])), min_samples_leaf=int(rng.choice([20, 50, 100, 200])),
                 l2_regularization=float(rng.choice([0.0, 1.0, 5.0])), max_iter=int(rng.choice([200, 300, 500]))) for _ in range(10)]
    def tune(featcols_num, featcols_cat, Xtr, lab):
        best, bs = None, -1
        for g in grid:
            s = cross_val_predict(make_pipe("gb", featcols_num, featcols_cat, g), Xtr[featcols_num + featcols_cat], Xtr[lab], cv=StratifiedKFold(3, shuffle=True, random_state=SEED), method="predict_proba")[:, 1]
            a = roc_auc_score(Xtr[lab], s)
            if a > bs: best, bs = g, a
        return best, bs
    tuned_params = {}
    for lab in LABELS:
        g, a = tune(NUM_FEATURES, CAT_FEATURES, tr, lab); tuned_params[("v1", lab)] = (g, a)
        print("tuned v1-features GB", lab, g, "trainCV AUC %.4f" % a, flush=True)
    m_by = {}
    for lab in LABELS:
        g = tuned_params[("v1", lab)][0]
        m = make_pipe("gb", NUM_FEATURES, CAT_FEATURES, g); m.fit(tr[FEATURES], tr[lab]); s = m.predict_proba(va[FEATURES])[:, 1]
        record("v1 features + tuned GB (train-CV search)", lab, "gb", s, va[lab].values, ref[lab], note=f"params={g}; train-CV AUC {tuned_params[('v1', lab)][1]:.4f}",
               extra={"brier": round(brier_score_loss(va[lab], s), 5), "ece": round(ece(va[lab].values, s), 4)})
        # LR tuning
        bestC, bsc = None, -1
        for C in (0.01, 0.1, 1.0, 10.0):
            sc = cross_val_predict(make_pipe("lr", NUM_FEATURES, CAT_FEATURES, {"C": C}), tr[FEATURES], tr[lab], cv=StratifiedKFold(3, shuffle=True, random_state=SEED), method="predict_proba")[:, 1]
            a = roc_auc_score(tr[lab], sc)
            if a > bsc: bestC, bsc = C, a
        ml = make_pipe("lr", NUM_FEATURES, CAT_FEATURES, {"C": bestC}); ml.fit(tr[FEATURES], tr[lab]); s = ml.predict_proba(va[FEATURES])[:, 1]
        record("v1 features + tuned LR (C by train-CV)", lab, "lr", s, va[lab].values, ref[lab], note=f"C={bestC}",
               extra={"brier": round(brier_score_loss(va[lab], s), 5), "ece": round(ece(va[lab].values, s), 4)})

    # tuned GB on the combined feature set
    for lab in LABELS:
        Xtr, Xva = tr.copy(), va.copy(); enc = SponsorEncoder(); Xtr[SPON] = enc.fit_transform(tr, lab); Xva[SPON] = enc.transform(va)
        num = NUM_FEATURES + SVDC + FLAGS + SPON
        g, a = tune(num, CAT_FEATURES, Xtr, lab)
        m = make_pipe("gb", num, CAT_FEATURES, g); m.fit(Xtr[num + CAT_FEATURES], Xtr[lab]); s = m.predict_proba(Xva[num + CAT_FEATURES])[:, 1]
        record("v1 + sponsor + SVD + flags + tuned GB", lab, "gb", s, va[lab].values, ref[lab], note=f"params={g}; train-CV AUC {a:.4f}",
               extra={"brier": round(brier_score_loss(va[lab], s), 5), "ece": round(ece(va[lab].values, s), 4)})
        # isotonic calibration of this tuned model: fit the map on out-of-fold TRAIN predictions only
        oof = cross_val_predict(make_pipe("gb", num, CAT_FEATURES, g), Xtr[num + CAT_FEATURES], Xtr[lab], cv=StratifiedKFold(5, shuffle=True, random_state=SEED), method="predict_proba")[:, 1]
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(oof, Xtr[lab]); sc = iso.predict(s)
        record("  + isotonic calibration (map fit on train OOF)", lab, "gb", sc, va[lab].values, ref[lab], note="AUC is rank-based; isotonic can only keep or lose ties",
               extra={"brier": round(brier_score_loss(va[lab], sc), 5), "ece": round(ece(va[lab].values, sc), 4)})
    # isotonic on plain v1 GB for reference
    for lab in LABELS:
        m = make_pipe("gb", NUM_FEATURES, CAT_FEATURES); oof = cross_val_predict(m, tr[FEATURES], tr[lab], cv=StratifiedKFold(5, shuffle=True, random_state=SEED), method="predict_proba")[:, 1]
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(oof, tr[lab]); sc = iso.predict(v1[("gb", lab)])
        record("v1 + isotonic calibration (map fit on train OOF)", lab, "gb", sc, va[lab].values, ref[lab], note="calibration only",
               extra={"brier": round(brier_score_loss(va[lab], sc), 5), "ece": round(ece(va[lab].values, sc), 4)})
        record("v1 GB uncalibrated (calibration reference)", lab, "gb", v1[("gb", lab)], va[lab].values, ref[lab], note="Brier/ECE reference",
               extra={"brier": round(brier_score_loss(va[lab], v1[("gb", lab)]), 5), "ece": round(ece(va[lab].values, v1[("gb", lab)]), 4)})

    out = pd.DataFrame(ATTEMPTS)
    out.to_csv(ROOT / "docs" / "model_search_attempts.csv", index=False)
    print("done in %.0fs; %d attempts" % (time.time() - t0, len(out)))
    return out, va


if __name__ == "__main__":
    main()
