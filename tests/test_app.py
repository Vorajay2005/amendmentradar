from pathlib import Path

import pytest

import scoring
from features import FEATURES, assert_no_leakage
from retrieval import aligned_trials, load_index, query, trial_text
from modeling import load

FORM = dict(phase="PHASE3", sponsor_class="INDUSTRY", conditions="Type 2 diabetes", intervention_names="metformin, placebo",
            intervention_types=["DRUG"], allocation="RANDOMIZED", intervention_model="PARALLEL", masking="DOUBLE",
            n_arms=2, n_interventions=2, n_primary=1, n_secondary=4, min_age=18, sex="ALL", start_year=2026,
            eligibility="Inclusion Criteria:\n- a\n- b\n\nExclusion Criteria:\n- c")


def test_form_goes_through_same_extractor():
    f, t, info = scoring.prepare(scoring.study_from_inputs(FORM))
    assert_no_leakage(FEATURES)
    assert f["phase"] == "3" and f["n_arms"] == 2 and f["elig_exclusion"] == 1 and f["elig_inclusion"] == 2
    assert f["start_year"] == 2019 and info["raw_start_year"] == 2026  # clamped for scoring only
    assert f["therapeutic_area"] == "endocrine_metabolic"


def test_score_bands_and_drivers():
    f, t, _ = scoring.prepare(scoring.study_from_inputs(FORM))
    s = scoring.score(f)
    assert 0 < s["terminated_low_accrual"]["p"] < 1 and s["terminated"]["band"] in scoring.BAND_NAMES
    tr = load()
    up, down = scoring.drivers(f, "terminated_low_accrual", scoring.typical_values(tr))
    assert all("start year" not in x.lower() for x in up + down)
    idx = load_index()
    near = query(trial_text(t), aligned_trials(tr, idx), idx)["near"]
    chk = scoring.percentile_checks(f, near)
    assert chk and all(0 <= c["percentile among 25 similar"] <= 100 for c in chk)


def test_nct_validation():
    with pytest.raises(ValueError):
        scoring.fetch_study("not-an-id")
    with pytest.raises(ValueError):
        scoring.fetch_study("NCT123")


def test_app_pages_run_without_exception():
    from streamlit.testing.v1 import AppTest
    for page in ["app/Home.py", "app/pages/1_Dashboard.py", "app/pages/2_About_and_Limits.py"]:
        at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / page), default_timeout=60).run()
        assert not at.exception, (page, at.exception)


HOME = str(Path(__file__).resolve().parent.parent / "app" / "Home.py")


def _all_text(at):
    return " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)


def test_home_nct_flow_renders_all_sections(monkeypatch):
    from streamlit.testing.v1 import AppTest

    def fake(nct):
        s = scoring.study_from_inputs(FORM)
        s["protocolSection"]["identificationModule"].update(nctId="NCT09999999", briefTitle="Fake not-yet-recruiting trial")
        s["protocolSection"]["statusModule"]["overallStatus"] = "NOT_YET_RECRUITING"
        return s

    monkeypatch.setattr(scoring, "fetch_study", fake)
    at = AppTest.from_file(HOME, default_timeout=90).run()
    at.text_input[0].set_value("NCT09999999")
    at.button[0].click().run()
    assert not at.exception
    txt = _all_text(at)
    assert "of the 25 most similar trials were terminated" in txt
    assert "Risk of stopping early for low accrual" in txt and "relative to trials starting 2017-2019" in txt
    assert "Design checks (descriptive)" in txt and "Not Yet Recruiting" in txt


def test_home_nct_errors_are_graceful(monkeypatch):
    from streamlit.testing.v1 import AppTest

    def missing(nct):
        raise LookupError("NCT00000000 was not found on ClinicalTrials.gov.")

    monkeypatch.setattr(scoring, "fetch_study", missing)
    at = AppTest.from_file(HOME, default_timeout=90).run()
    at.text_input[0].set_value("NCT00000000")
    at.button[0].click().run()
    assert not at.exception and len(at.error) == 1


def test_home_manual_form_flow():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(HOME, default_timeout=90).run()
    at.radio[0].set_value("Manual design form").run()
    at.button[0].click().run()
    assert not at.exception
    assert "Your design" in " ".join(s.value for s in at.subheader)
