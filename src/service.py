"""JSON-ready orchestration used by the FastAPI layer (reuses retrieval / scoring / modeling)."""
import json
import math
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

import modeling
import retrieval
import scoring

ROOT = Path(__file__).resolve().parent.parent
REASON_LABELS = {"low_accrual": "Low accrual", "safety": "Safety", "efficacy_futility": "Efficacy / futility",
                 "sponsor_business": "Sponsor / business", "other_unspecified": "Other / unspecified"}
AREA_LABELS = {"oncology": "Oncology", "infectious_disease": "Infectious disease", "cardiovascular": "Cardiovascular",
               "neurology": "Neurology", "psychiatry": "Psychiatry", "endocrine_metabolic": "Endocrine & metabolic",
               "respiratory": "Respiratory", "immunology_rheumatology": "Immunology & rheumatology",
               "gastro_hepatology": "Gastro & hepatology", "renal_urology": "Renal & urology", "hematology": "Hematology",
               "dermatology_ophthalmology": "Dermatology & ophthalmology", "womens_health_reproductive": "Women's health",
               "pain_musculoskeletal_anesthesia": "Pain, musculoskeletal & anesthesia", "other": "Other (not mapped)"}
BAND_PHRASE = {"Lower third": "lower", "Middle third": "middle", "Upper third": "upper"}


class AnalyzeError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@lru_cache(maxsize=1)
def _data():
    trials = modeling.load(ROOT / "data" / "processed" / "trials.csv.gz")
    idx = retrieval.load_index(str(ROOT / "data" / "tfidf_index.joblib"))
    return trials, idx, retrieval.aligned_trials(trials, idx), scoring.typical_values(trials)


def _clean(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if math.isnan(v) else float(v)
    if v is pd.NA or v is None:
        return None
    return v


def _row_to_study_inputs(row):
    """Stored-snapshot fallback: features straight from the processed table (no raw record needed)."""
    feats = {k: _clean(row[k]) if not isinstance(row[k], str) else row[k] for k in scoring.FEATURES}
    feats = {k: (math.nan if v is None else v) for k, v in feats.items()}
    text = {k: ("" if pd.isna(row[k]) else str(row[k])) for k in ["conditions", "interventions", "design_text", "title"]}
    return feats, text, {"nct_id": row.nct_id, "title": text["title"], "status": row.status, "raw_start_year": row.start_year}


def _stored_example(nct):
    p = ROOT / "data" / "examples" / f"{nct}.json"
    if p.exists():
        d = json.loads(p.read_text())
        return d, d.get("_stored", {})
    return None, None


def _resolve(nct_id, design):
    """-> (feats, text, info, source, source_note)."""
    trials = _data()[0]
    if design is not None:
        feats, text, info = scoring.prepare(scoring.study_from_inputs(design))
        return feats, text, info, "manual", None
    nct = (nct_id or "").strip().upper()
    try:
        study = scoring.fetch_study(nct)
        feats, text, info = scoring.prepare(study)
        return feats, text, info, "live", None
    except ValueError as e:
        raise AnalyzeError("invalid_nct", str(e), 422)
    except LookupError as e:
        raise AnalyzeError("not_found", str(e), 404)
    except Exception:
        pass  # network / rate-limit: try stored copies
    d, meta = _stored_example(nct)
    if d is not None:
        feats, text, info = scoring.prepare(d)
        return feats, text, info, "stored_snapshot", (
            f"ClinicalTrials.gov could not be reached, so this is a stored copy of the record fetched on "
            f"{meta.get('fetched_at', 'an earlier date')}. Its status may have changed since.")
    hit = trials[trials.nct_id == nct]
    if len(hit):
        feats, text, info = _row_to_study_inputs(hit.iloc[0])
        return feats, text, info, "stored_snapshot", (
            "ClinicalTrials.gov could not be reached, so this uses the stored snapshot of the record "
            "from when the data set was built. Its status may have changed since.")
    raise AnalyzeError("unreachable", "Could not reach ClinicalTrials.gov (offline or rate-limited). "
                       "Try again, or use the manual design form.", 503)


def analyze(nct_id=None, design=None):
    trials, idx, aligned, typical = _data()
    meta = scoring.models()["meta"]
    feats, text, info, source, source_note = _resolve(nct_id, design)
    is_manual = design is not None
    nct = info["nct_id"]
    notes = []
    in_data = (not is_manual) and nct in set(trials.nct_id)
    row_year = int(trials.loc[trials.nct_id == nct, "start_year"].iloc[0]) if in_data else None
    ry = info["raw_start_year"]
    if in_data and row_year <= 2016:
        notes.append({"kind": "in_training", "text": "This trial was part of the data the models were trained on (start 2008-2016), so its scores are optimistic. It is excluded from its own list of similar trials."})
    elif in_data:
        notes.append({"kind": "in_test", "text": "This trial started in 2017-2019: it belongs to the benchmark test period, so the models did not train on it. It is excluded from its own list of similar trials, and its real outcome is already in the data."})
    if ry is None or (isinstance(ry, float) and math.isnan(ry)):
        notes.append({"kind": "no_start", "text": "No start date on record; the model fills in a typical value."})
    elif ry > 2019:
        notes.append({"kind": "clamped_year", "text": f"Start year {int(ry)} is outside the 2008-2019 training range; it is scored as 2019."})

    s = scoring.score(feats)
    q = retrieval.query(retrieval.trial_text(text), aligned, idx, exclude=None if is_manual else nct)
    low, main = s["terminated_low_accrual"], s["terminated"]

    similar = {"found": bool(q["found"]), "size": 25, "n_terminated": q["n_terminated"],
               "share_terminated": None if not q["found"] else q["share_terminated"],
               "base_rate_all": meta["base_rate_all"]["terminated"], "nearest_terminated": []}
    for _, r in q["nearest_terminated"].iterrows():
        raw = r.why_stopped if isinstance(r.why_stopped, str) and r.why_stopped.strip() else ""
        similar["nearest_terminated"].append({
            "nct_id": r.nct_id, "title": r.title, "start_year": int(r.start_year), "similarity": float(r.similarity),
            "stop_reason": r.stop_reason, "stop_reason_label": REASON_LABELS.get(r.stop_reason, r.stop_reason),
            "why_stopped": raw, "link": retrieval.ctgov_link(r.nct_id)})

    drv = {}
    for key, lab in (("low_accrual", scoring.LABEL_LOW), ("overall", scoring.LABEL_MAIN)):
        up, down = scoring.driver_dicts(feats, lab, typical)
        drv[key] = {"up": up, "down": down}
    checks = scoring.percentile_checks(feats, q["near"]) if q["found"] else []

    rel = reliability()
    return {
        "source": source, "source_note": source_note, "notes": notes,
        "trial": {"nct_id": None if is_manual else nct, "title": "Your manual design" if is_manual else info["title"],
                  "status": None if is_manual else info["status"], "link": None if is_manual else retrieval.ctgov_link(nct),
                  "start_year_on_record": None if (ry is None or (isinstance(ry, float) and math.isnan(ry))) else int(ry),
                  "therapeutic_area": AREA_LABELS.get(feats["therapeutic_area"], feats["therapeutic_area"]),
                  "phase": feats["phase"], "sponsor_class": feats["sponsor_class"]},
        "low_accrual": {"probability": low["p"], "band": low["band"], "band_phrase": BAND_PHRASE[low["band"]],
                        "average_2017_2019": meta["test_rate"]["terminated_low_accrual"],
                        "band_observed_rate": rel["band_rates"].get("terminated_low_accrual", {}).get(low["band"]),
                        "test_auc": meta["test_auc"]["terminated_low_accrual"]["gb"]},
        "overall": {"band": main["band"], "band_phrase": BAND_PHRASE[main["band"]],
                    "band_observed_rate": rel["band_rates"].get("terminated", {}).get(main["band"]),
                    "test_auc": meta["test_auc"]["terminated"]["gb"]},
        "similar": similar, "drivers": drv,
        "design_checks": [{"measure": c["measure"], "value": c["this trial"], "similar_median": c["median of similar"],
                           "percentile": c["percentile among 25 similar"], "note": c["note"]} for c in checks],
    }


# ------------------------------------------------------------------ dashboard
@lru_cache(maxsize=1)
def dashboard():
    df = _data()[0]
    t = df[df.terminated == 1]

    def table(col, labeler=lambda x: str(x), order=None):
        g = df.groupby(col).agg(trials=("nct_id", "size"), term=("terminated", "mean"), low=("terminated_low_accrual", "mean"))
        g = g.loc[order] if order else g.sort_values("term", ascending=False)
        return [{"key": str(k), "label": labeler(k), "trials": int(r.trials), "terminated_pct": round(r.term * 100, 2),
                 "low_accrual_pct": round(r.low * 100, 2)} for k, r in g.iterrows()]

    vc = t.stop_reason.value_counts()
    empty = int((t.why_stopped.fillna("") == "").sum())
    other = int((t.stop_reason == "other_unspecified").sum())
    return {
        "totals": {"trials": int(len(df)), "terminated": int(df.terminated.sum()),
                   "terminated_pct": round(df.terminated.mean() * 100, 2),
                   "low_accrual": int(df.terminated_low_accrual.sum()),
                   "low_accrual_pct": round(df.terminated_low_accrual.mean() * 100, 2)},
        "by_area": table("therapeutic_area", lambda a: AREA_LABELS.get(a, a)),
        "by_phase": table("phase", lambda p: f"Phase {p}"),
        "by_sponsor": table("sponsor_class"),
        "by_year": table("start_year", lambda y: str(int(y)), order=sorted(df.start_year.unique())),
        "reasons": [{"key": k, "label": REASON_LABELS[k], "trials": int(vc.get(k, 0)),
                     "pct_of_terminated": round(vc.get(k, 0) / len(t) * 100, 1)} for k in REASON_LABELS],
        "other_area": {"trials": int((df.therapeutic_area == "other").sum()),
                       "pct": round((df.therapeutic_area == "other").mean() * 100, 1)},
        "other_reason": {"trials": other, "pct_of_terminated": round(other / len(t) * 100, 1),
                         "no_reason_given": empty, "no_reason_pct_of_terminated": round(empty / len(t) * 100, 1)},
    }


# ------------------------------------------------------------------ reliability (parsed from BENCHMARK.md)
def _tables(section):
    """Markdown tables in a section -> list of list-of-dicts."""
    out, cur = [], []
    for line in section.splitlines() + [""]:
        if line.startswith("|"):
            cur.append([c.strip() for c in line.strip().strip("|").split("|")])
        elif cur:
            hdr, body = cur[0], [r for r in cur[2:]]
            out.append([dict(zip(hdr, r)) for r in body])
            cur = []
    return out


def _auc(s):
    m = re.match(r"([\d.]+) \(([\d.]+)-([\d.]+)\)", s)
    return (float(m[1]), float(m[2]), float(m[3])) if m else (float(s), None, None)


@lru_cache(maxsize=1)
def reliability():
    text = (ROOT / "BENCHMARK.md").read_text()
    parts = re.split(r"\n(?=## )", text)
    sec = {int(re.match(r"## (\d+)\.", p)[1]): p for p in parts[1:] if re.match(r"## (\d+)\.", p)}
    setup = re.search(r"## Setup(.*?)\n## ", text, re.S)[1]
    t1 = _tables(sec[1])
    main = []
    for r in t1[0]:
        a, lo, hi = _auc(r["ROC-AUC (95% CI)"])
        main.append({"label": r["label"], "model": r["model"], "auc": a, "ci_low": lo, "ci_high": hi, "pr_auc": float(r["PR-AUC"])})
    bands = {}
    for r in t1[1]:
        bands.setdefault(r["label"], {})[r["band (gradient boosting)"]] = float(r["observed rate %"]) / 100
    band_rows = [{"label": r["label"], "band": r["band (gradient boosting)"], "trials": int(r["trials"]),
                  "observed_rate": float(r["observed rate %"]) / 100, "share_of_positives": float(r["share of all positives %"]) / 100}
                 for r in t1[1]]
    cv = []
    for r in _tables(sec[3])[0]:
        a, lo, hi = _auc(r["pooled out-of-fold AUC (95% CI)"])
        cv.append({"label": r["label"], "model": r["model"], "auc": a, "ci_low": lo, "ci_high": hi})
    drift = [{"year": int(r["start_year"]), "trials": int(r["n"]), "terminated_pct": float(r["terminated %"]),
              "low_accrual_pct": float(r["low-accrual %"]), "covid_cited_pct": float(r["covid-cited %"])} for r in _tables(sec[2])[0]]
    drift_note = " ".join(l.strip() for l in sec[2].split("\n\n")[-1].splitlines() if l and not l.startswith("|"))
    calib = [{"label": m[1], "model": m[2], "mean_predicted": float(m[3]), "observed": float(m[4])}
             for m in re.finditer(r"\*\*(\w+) / ([\w ]+)\*\* \(test set.*?mean prediction overall ([\d.]+) vs observed ([\d.]+)\)", sec[4])]
    limits = [re.sub(r"\*\*", "", m[1]).strip() for m in re.finditer(r"^\d+\. (.+)$", sec[8], re.M)]
    pos = {m[1]: int(m[2].replace(",", "")) for m in re.finditer(r"`(\w+)`: train rate [\d.]+%, test rate [\d.]+%, test positives \*\*([\d,]+)\*\*", setup)}
    n = re.search(r"test (\d{4})-(\d{4}) \(n=([\d,]+)\)", setup)
    return {"main_results": main, "band_rates": bands, "band_table": band_rows, "cv": cv, "drift": drift,
            "drift_note": drift_note, "calibration": calib, "limits": limits, "test_positives": pos,
            "test_n": int(n[3].replace(",", "")) if n else None, "n_trials": int(re.search(r"\*\*([\d,]+) trials\*\*", text)[1].replace(",", ""))}
