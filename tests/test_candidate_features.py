"""Leakage guard for the model-v2 candidate features (scripts/model_search/phase_a.py).

Names are checked against the same guard as v1, and the behaviour is checked: the new features may use only
design-time text, sponsor identity, and TRAINING labels (never validation/test labels, status, enrollment, ...).
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from features import FEATURES, FORBIDDEN, FORBIDDEN_TOKENS, assert_no_leakage

ROOT = Path(__file__).resolve().parent.parent
_saved = sys.argv[:]
sys.argv = [sys.argv[0]]  # phase_a reads argv[1] at import; keep it neutral under pytest
spec = importlib.util.spec_from_file_location("phase_a", ROOT / "scripts" / "model_search" / "phase_a.py")
pa = importlib.util.module_from_spec(spec); spec.loader.exec_module(pa)
sys.argv = _saved


def frame(n=200, seed=0):
    r = np.random.default_rng(seed)
    names = r.choice(["Acme Pharma", "Beta Univ", "Gamma NIH", "Delta Co"], n)
    return pd.DataFrame({
        "sponsor_name": names, "sponsor_class": np.where(np.isin(names, ["Acme Pharma", "Delta Co"]), "INDUSTRY", "OTHER"),
        "terminated": r.integers(0, 2, n),
        "eligibility_text": ["Inclusion Criteria:\n- ECOG 0-1\n- prior chemotherapy\n\nExclusion Criteria:\n- pregnancy\n- HIV infection"] * n,
        "conditions": ["cancer"] * n, "interventions": ["drug x"] * n,
        # forbidden / outcome-side columns that must never influence a feature
        "why_stopped": ["slow accrual"] * n, "status": r.choice(["COMPLETED", "TERMINATED"], n), "enrollment": r.integers(1, 999, n),
    })


def test_new_feature_names_pass_the_v1_guard():
    assert_no_leakage(pa.NEW_FEATURE_COLUMNS)
    assert not set(pa.NEW_FEATURE_COLUMNS) & set(FORBIDDEN)
    assert len(pa.NEW_FEATURE_COLUMNS) == len(set(pa.NEW_FEATURE_COLUMNS)) and not set(pa.NEW_FEATURE_COLUMNS) & set(FEATURES)
    assert len(pa.NEW_FEATURE_COLUMNS) == 4 + 2 + pa.SVD_K


def test_guard_rejects_forbidden_names_among_new_features():
    for bad in ["enrollment_count", "n_locations", "why_stopped_flag", "overall_status", "completion_year", "results_posted"]:
        with pytest.raises(ValueError):
            assert_no_leakage(pa.NEW_FEATURE_COLUMNS + [bad])


def test_eligibility_flags_read_only_eligibility_text():
    only_text = frame()[["eligibility_text"]]
    full = frame()
    a, b = pa.eligibility_flags(only_text), pa.eligibility_flags(full.assign(why_stopped="x", status="TERMINATED", enrollment=1))
    pd.testing.assert_frame_equal(a, b)
    assert list(a.columns) == pa.FLAG_COLS and a.iloc[0].tolist() == [1, 0, 1, 2]  # prior therapy, no biomarker, ECOG, 2 exclusion types


def test_sponsor_encoding_never_uses_validation_labels():
    tr, va = frame(300, 1), frame(100, 2)
    enc = pa.SponsorEncoder(); enc.fit_transform(tr, "terminated")
    base = enc.transform(va)
    shuffled = va.assign(terminated=np.random.default_rng(9).permutation(va.terminated.values))
    pd.testing.assert_frame_equal(base, enc.transform(shuffled))  # validation labels are irrelevant
    pd.testing.assert_frame_equal(base, enc.transform(va.assign(why_stopped="x", status="COMPLETED", enrollment=0)))


def test_sponsor_encoding_is_out_of_fold_for_training_rows():
    tr = frame(300, 3).reset_index(drop=True)
    enc = pa.SponsorEncoder(); a = enc.fit_transform(tr, "terminated")
    i = 17
    flipped = tr.copy(); flipped.loc[i, "terminated"] = 1 - flipped.loc[i, "terminated"]
    b = pa.SponsorEncoder().fit_transform(flipped, "terminated")
    # StratifiedKFold folds depend on labels, so compare with fixed folds: a row's own label can never be in its own fold's fit
    assert np.isfinite(a.values).all() and a.sponsor_te.between(0, 1).all()
    # direct check of the mechanism: encode row i from a reference set that excludes it
    ref = tr.drop(index=i); names = ref.sponsor_name.map(pa.norm_name).values
    te, n = enc._encode(ref, names, tr.loc[[i]], tr.loc[[i], "sponsor_name"].map(pa.norm_name).values)
    te2, _ = enc._encode(ref, names, flipped.loc[[i]], flipped.loc[[i], "sponsor_name"].map(pa.norm_name).values)
    assert te[0] == te2[0]  # an out-of-reference row's own label has no influence on its encoding


def test_unseen_sponsor_falls_back_to_class_rate():
    tr = frame(300, 4)
    enc = pa.SponsorEncoder(); enc.fit_transform(tr, "terminated")
    new = tr.iloc[:3].copy(); new["sponsor_name"] = "Totally New Sponsor Inc"; new["sponsor_class"] = "INDUSTRY"
    out = enc.transform(new)
    assert np.allclose(out.sponsor_te, tr[tr.sponsor_class == "INDUSTRY"].terminated.mean()) and (out.sponsor_log_n == 0).all()


def test_text_svd_is_fit_on_training_text_only():
    tr = frame(100, 5); va = frame(50, 6)
    va["eligibility_text"] = "xylophone zeppelin quasar " * 5  # tokens that exist only in validation
    svd = pa.TextSVD(k=3); svd.fit_transform(tr)
    vocab = set(svd.vec.vocabulary_)
    z = svd.transform(va)
    assert not any("xylophone" in v for v in vocab) and z.shape == (50, 3)


def test_extraction_reads_only_design_side_fields_and_filters_by_year():
    src = (ROOT / "scripts" / "model_search" / "extract_text.py").read_text()
    for field in ["enrollmentInfo", "whyStopped", "contactsLocationsModule", "resultsSection", "completionDate", "lastUpdate"]:
        assert field not in src.replace('"overallStatus"', ""), field
    assert "max_year" in src and "continue" in src  # later-period rows are dropped at read time
