import math

from features import extract_features, parse_age_years, parse_eligibility, therapeutic_area

ELIG = """Inclusion Criteria:
- Age 18+
- Confirmed diagnosis
* Signed consent

Exclusion Criteria:
1. Pregnancy
2. Prior therapy
"""


def study():
    return {"protocolSection": {
        "identificationModule": {"nctId": "NCT00000001", "briefTitle": "t"},
        "statusModule": {"overallStatus": "TERMINATED", "whyStopped": "Slow accrual",
                         "startDateStruct": {"date": "2014-03"}},
        "designModule": {"phases": ["PHASE2", "PHASE3"], "enrollmentInfo": {"count": 5},
                         "designInfo": {"allocation": "RANDOMIZED", "interventionModel": "PARALLEL",
                                        "maskingInfo": {"masking": "DOUBLE"}}},
        "armsInterventionsModule": {"armGroups": [{}, {}], "interventions": [{"type": "DRUG"}, {"type": "DEVICE"}]},
        "outcomesModule": {"primaryOutcomes": [{}], "secondaryOutcomes": [{}, {}, {}]},
        "eligibilityModule": {"eligibilityCriteria": ELIG, "sex": "ALL", "minimumAge": "18 Years",
                              "healthyVolunteers": False},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "X", "class": "INDUSTRY"}},
        "oversightModule": {"oversightHasDmc": True},
        "conditionsModule": {"conditions": ["Breast Cancer"]},
    }}


def test_age_parsing():
    assert parse_age_years("18 Years") == 18
    assert abs(parse_age_years("6 Months") - 0.5) < 1e-9
    assert math.isnan(parse_age_years(None))


def test_eligibility_counts():
    chars, n, inc, exc = parse_eligibility(ELIG)
    assert (n, inc, exc) == (5, 3, 2) and chars == len(ELIG)
    assert parse_eligibility("") == (0, 0, 0, 0)


def test_area():
    assert therapeutic_area(["Breast Cancer"]) == "oncology"
    assert therapeutic_area(["Type 2 Diabetes"]) == "endocrine_metabolic"
    assert therapeutic_area(["Zzz"]) == "other"
    assert therapeutic_area(["hospitals"]) == "other"  # ALS must not match inside words


def test_extract_features():
    f = extract_features(study())
    assert f["phase"] == "2/3" and f["n_arms"] == 2 and f["n_interventions"] == 2
    assert f["n_primary_outcomes"] == 1 and f["n_secondary_outcomes"] == 3
    assert f["start_year"] == 2014 and f["has_dmc"] == 1 and f["max_age_missing"] == 1
    assert f["int_drug"] == 1 and f["int_device"] == 1 and f["int_biological"] == 0
    assert f["therapeutic_area"] == "oncology" and f["sponsor_class"] == "INDUSTRY"


def test_features_do_not_use_outcome_fields():
    # Same design, wildly different post-hoc fields -> identical features.
    a, b = study(), study()
    b["protocolSection"]["statusModule"].update(overallStatus="COMPLETED", whyStopped="x")
    b["protocolSection"]["designModule"]["enrollmentInfo"] = {"count": 99999}
    assert extract_features(a) == extract_features(b)
