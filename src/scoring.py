"""Scoring, plain-language drivers and descriptive design checks for one trial.

All statements are descriptive. Nothing here says that changing a value will
change a trial's outcome.
"""
import json
import math
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

import ctgov
from features import CAT_FEATURES, FEATURES, NUM_FEATURES, extract_features, extract_text
from modeling import TRAIN_YEARS

ROOT = Path(__file__).resolve().parent.parent
LABEL_MAIN, LABEL_LOW = "terminated", "terminated_low_accrual"
NCT_RE = re.compile(r"^NCT\d{8}$")
BAND_NAMES = ["Lower third", "Middle third", "Upper third"]

NICE = {
    "phase": "Phase", "masking": "Masking (blinding)", "allocation": "Allocation", "intervention_model": "Intervention model",
    "sex": "Sex eligibility", "therapeutic_area": "Therapeutic area", "sponsor_class": "Lead sponsor class",
    "n_arms": "Number of arms", "n_interventions": "Number of interventions",
    "n_primary_outcomes": "Primary outcomes", "n_secondary_outcomes": "Secondary outcomes",
    "elig_chars": "Eligibility text length (characters)", "elig_criteria": "Eligibility criteria (count)",
    "elig_inclusion": "Inclusion criteria (count)", "elig_exclusion": "Exclusion criteria (count)",
    "min_age_years": "Minimum age (years)", "max_age_years": "Maximum age (years)",
    "max_age_missing": "No maximum age stated", "healthy_volunteers": "Accepts healthy volunteers",
    "n_conditions": "Conditions listed", "start_year": "Start year", "has_dmc": "Has data monitoring committee",
    "fda_regulated_drug": "FDA-regulated drug flag", "int_drug": "Includes a drug", "int_biological": "Includes a biological",
    "int_device": "Includes a device", "int_procedure": "Includes a procedure", "int_behavioral": "Includes a behavioral intervention",
    "int_other": "Includes another intervention type",
}
CHECKS = ["elig_chars", "elig_criteria", "elig_exclusion", "n_primary_outcomes", "n_secondary_outcomes",
          "n_arms", "n_interventions", "n_conditions"]


# ------------------------------------------------------------ data access
def fetch_study(nct_id):
    """Current record via API v2 (any status, incl. not yet recruiting). Raises ValueError / LookupError."""
    nct_id = nct_id.strip().upper()
    if not NCT_RE.match(nct_id):
        raise ValueError("An NCT ID looks like NCT01234567 (NCT followed by 8 digits).")
    import requests
    try:
        d = ctgov.get_json(f"{ctgov.BASE}/{nct_id}", {"fields": ctgov.FIELDS, "format": "json"},
                           tries=3, use_cache=False)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            raise LookupError(f"{nct_id} was not found on ClinicalTrials.gov.") from e
        raise
    if "protocolSection" not in d:
        raise LookupError(f"{nct_id} returned no protocol data.")
    return d


def study_from_inputs(i):
    """Build an API-v2-shaped study dict from the manual form so the SAME extractors are used."""
    conds = [c.strip() for c in re.split(r"[;,\n]", i.get("conditions", "")) if c.strip()]
    ints = [{"name": n.strip(), "type": t} for n, t in
            zip([x for x in re.split(r"[;,\n]", i.get("intervention_names", "")) if x.strip()] or ["intervention"],
                [i.get("intervention_type", "DRUG")] * 99)]
    types = i.get("intervention_types") or [i.get("intervention_type", "DRUG")]
    ints = [{"name": x["name"], "type": types[k % len(types)]} for k, x in enumerate(ints)]
    start = i.get("start_year")
    el = {"eligibilityCriteria": i.get("eligibility", ""), "sex": i.get("sex", "ALL"),
          "healthyVolunteers": bool(i.get("healthy_volunteers", False))}
    if i.get("min_age") is not None:
        el["minimumAge"] = f"{i['min_age']} Years"
    if i.get("max_age"):
        el["maximumAge"] = f"{i['max_age']} Years"
    phase = i.get("phase", "PHASE2")
    return {"protocolSection": {
        "identificationModule": {"nctId": "MANUAL", "briefTitle": "Manual design"},
        "statusModule": {"startDateStruct": {"date": f"{start}-01"} if start else {}},
        "designModule": {"phases": phase.split("/") if "/" in phase else [phase],
                         "designInfo": {"allocation": i.get("allocation", "RANDOMIZED"),
                                        "interventionModel": i.get("intervention_model", "PARALLEL"),
                                        "maskingInfo": {"masking": i.get("masking", "NONE")}}},
        "armsInterventionsModule": {"armGroups": [{}] * int(i.get("n_arms", 2)),
                                    "interventions": ints[:max(int(i.get("n_interventions", len(ints))), 1)]},
        "outcomesModule": {"primaryOutcomes": [{}] * int(i.get("n_primary", 1)),
                           "secondaryOutcomes": [{}] * int(i.get("n_secondary", 0))},
        "eligibilityModule": el,
        "sponsorCollaboratorsModule": {"leadSponsor": {"class": i.get("sponsor_class", "INDUSTRY")}},
        "oversightModule": {"oversightHasDmc": bool(i.get("has_dmc", False)),
                            "isFdaRegulatedDrug": bool(i.get("fda_drug", False))},
        "conditionsModule": {"conditions": conds},
    }}


def prepare(study, as_of_year=TRAIN_YEARS[1] + 3):
    """study -> (feature dict for the model, retrieval-text dict, display info)."""
    f = extract_features(study)
    t = extract_text(study)
    p = study["protocolSection"]
    info = {"nct_id": f["nct_id"], "title": t["title"],
            "status": p["statusModule"].get("overallStatus", "UNKNOWN"),
            "raw_start_year": f["start_year"]}
    # Models saw 2008-2019 starts; clamp so a 2025 start is scored like a 2019 start (documented in the UI).
    if isinstance(f["start_year"], float) and math.isnan(f["start_year"]):
        pass  # imputed by the pipeline
    else:
        f["start_year"] = min(max(int(f["start_year"]), 2008), as_of_year)
    return f, t, info


# ------------------------------------------------------------ models
_M = {}


def models():
    if not _M:
        for lab in (LABEL_MAIN, LABEL_LOW):
            _M[lab] = joblib.load(ROOT / "models" / f"{lab}_gb.joblib")
        _M["meta"] = json.loads((ROOT / "models" / "meta.json").read_text())
    return _M


def typical_values(trials):
    tr = trials[trials.start_year.between(*TRAIN_YEARS)]
    out = {c: float(tr[c].median()) for c in NUM_FEATURES}
    out.update({c: tr[c].mode().iloc[0] for c in CAT_FEATURES})
    return out


def band_of(p, cuts):
    return BAND_NAMES[int(p > cuts[0]) + int(p > cuts[1])]


def score(feats, trials=None):
    """Returns probabilities and bands. Only the low-accrual probability is meant to be shown as a number."""
    m = models()
    X = pd.DataFrame([feats])[FEATURES]
    out = {}
    for lab in (LABEL_MAIN, LABEL_LOW):
        p = float(m[lab].predict_proba(X)[:, 1][0])
        out[lab] = {"p": p, "band": band_of(p, m["meta"]["risk_band_cutoffs"][lab])}
    return out


def _fmt(v):
    if isinstance(v, (float, np.floating, int, np.integer)) and not isinstance(v, bool):
        v = float(v)
        return "n/a" if math.isnan(v) else (f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.1f}".rstrip("0").rstrip("."))
    return str(v)


def _flag_feature(f):
    return f.startswith("int_") or f in ("healthy_volunteers", "has_dmc", "fda_regulated_drug", "max_age_missing")


def _driver_rows(feats, label, typical, n_up=3, n_down=2, min_delta=None):
    m = models()[label]
    X = pd.DataFrame([feats])[FEATURES]
    base = float(m.predict_proba(X)[:, 1][0])
    min_delta = min_delta if min_delta is not None else base * 0.03
    rows = []
    for f in FEATURES:
        if f == "start_year":  # clamped/time artifact, not a design property
            continue
        v, tv = X.at[0, f], typical[f]
        same = (isinstance(v, str) and v == tv) or (not isinstance(v, str) and not pd.isna(v) and abs(float(v) - float(tv)) < 1e-9)
        if same:
            continue
        X2 = X.copy()
        X2[f] = tv
        d = base - float(m.predict_proba(X2)[:, 1][0])
        if abs(d) >= min_delta:
            rows.append((d, f, v, tv))
    rows.sort(key=lambda r: -r[0])
    up = [r for r in rows if r[0] > 0][:n_up]
    down = [r for r in sorted(rows, key=lambda r: r[0]) if r[0] < 0][:n_down]
    return up, down


def driver_dict(row):
    """Structured, display-ready version of one driver row (direction is relative to a typical trial)."""
    d, f, v, tv = row
    if _flag_feature(f) and f not in CAT_FEATURES:
        shown, typ = ("yes" if v else "no"), ("yes" if tv >= 0.5 else "no")
    else:
        shown, typ = _fmt(v), _fmt(tv)
    return {"feature": f, "name": NICE[f], "value": shown, "typical": typ, "direction": "up" if d > 0 else "down"}


def drivers(feats, label, typical, n_up=3, n_down=2, min_delta=None):
    """Features that move the estimate away from what a typical (2008-2016) trial would get.

    For each feature, swap its value for the typical value and see how the estimate changes.
    Descriptive attribution only. Returns markdown lines (up, down).
    """
    up, down = _driver_rows(feats, label, typical, n_up, n_down, min_delta)

    def line(r, word):
        x = driver_dict(r)
        return f"**{x['name']}**: {x['value']} (typical: {x['typical']}) {word}"
    return ([line(r, "raises the estimate vs. a typical trial") for r in up],
            [line(r, "lowers the estimate vs. a typical trial") for r in down])


def driver_dicts(feats, label, typical, **kw):
    up, down = _driver_rows(feats, label, typical, **kw)
    return [driver_dict(r) for r in up], [driver_dict(r) for r in down]


def percentile_checks(feats, near):
    """Where this trial's values sit among its nearest neighbours (descriptive; mid-rank percentile)."""
    out = []
    for f in CHECKS:
        v = feats.get(f)
        if v is None or (isinstance(v, float) and math.isnan(v)) or near.empty:
            continue
        a = near[f].astype(float).values
        pct = 100 * ((a < v).sum() + 0.5 * (a == v).sum()) / len(a)
        note = "unusually high" if pct >= 90 else "unusually low" if pct <= 10 else ""
        out.append({"measure": NICE[f], "this trial": _fmt(float(v)), "median of similar": _fmt(float(np.median(a))),
                    "percentile among 25 similar": round(pct), "note": note})
    return out
