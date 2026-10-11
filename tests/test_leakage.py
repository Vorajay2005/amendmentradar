import pytest

import ctgov
from features import FEATURES, FORBIDDEN, GROUPS, assert_no_leakage
from modeling import feature_frame, load


def test_feature_list_is_clean():
    assert_no_leakage(FEATURES)
    assert not set(FEATURES) & set(FORBIDDEN)


def test_guard_rejects_forbidden_columns():
    for bad in ["enrollment_count", "n_locations", "why_stopped", "overall_status", "terminated",
                "completion_date", "last_update", "results_posted", "stop_reason", "n_countries"]:
        with pytest.raises(ValueError):
            assert_no_leakage(FEATURES + [bad])


def test_every_feature_in_exactly_one_group():
    flat = [c for g in GROUPS.values() for c in g]
    assert sorted(flat) == sorted(FEATURES)


def test_feature_matrix_has_no_forbidden_columns():
    df = load()
    X = feature_frame(df)
    assert_no_leakage(list(X.columns))
    assert list(X.columns) == FEATURES


def test_download_never_requests_post_registration_fields():
    requested = ctgov.FIELDS.lower()
    for tok in ["enrollment", "locations", "completiondate", "result", "reference", "lastupdate"]:
        assert tok not in requested
