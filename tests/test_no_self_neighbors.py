"""Guard: a queried trial must never appear in its own neighbours, share, or nearest-terminated cards."""
import random

import pytest

import retrieval
import scoring
import service
from api.main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def data():
    trials, idx, aligned, _ = service._data()
    return idx, aligned


def _ids(q):
    return set(q["near"].nct_id), set(q["nearest_terminated"].nct_id)


def test_sampled_indexed_trials_never_in_own_neighbours(data):
    idx, al = data
    rng = random.Random(7)
    rows = [al.iloc[i] for i in rng.sample(range(len(al)), 300)]
    rows += [al[al.terminated == 1].iloc[0], al[al.terminated == 0].iloc[0]]  # both statuses
    for r in rows:
        q = retrieval.query(retrieval.doc_text(r.fillna("")), al, idx, exclude=r.nct_id)
        near, nearest_t = _ids(q)
        assert r.nct_id not in near and r.nct_id not in nearest_t, r.nct_id
        # the share is computed from the same exclusion-aware list
        assert q["n_terminated"] == int(al[al.nct_id.isin(near)].terminated.sum())


def test_control_without_exclusion_does_find_itself(data):
    """Proves the guard above would fail if exclusion broke."""
    idx, al = data
    r = al.iloc[123]
    q = retrieval.query(retrieval.doc_text(r.fillna("")), al, idx)
    assert r.nct_id in set(q["near"].nct_id) and q["near"].iloc[0].similarity > 0.99


def test_api_excludes_queried_trial_for_indexed_examples(monkeypatch):
    def offline(nct):
        raise ConnectionError("offline")
    monkeypatch.setattr(scoring, "fetch_study", offline)
    c = TestClient(app)
    for nct in ("NCT03827850", "NCT03598036"):
        d = c.post("/api/analyze", json={"nct_id": nct}).json()
        assert nct not in [t["nct_id"] for t in d["similar"]["nearest_terminated"]]
        trials, idx, al, _ = service._data()
        s = retrieval.similarities(retrieval.doc_text(al[al.nct_id == nct].iloc[0].fillna("")), idx)
        s[idx["nct_ids"].index(nct)] = -1
        top = al.iloc[sorted(range(len(s)), key=lambda i: -s[i])[:25]]
        assert d["similar"]["n_terminated"] == int(top.terminated.sum())  # independent recomputation
    d = c.post("/api/analyze", json={"nct_id": "NCT06964230"}).json()  # not indexed: nothing to exclude
    assert "NCT06964230" not in service._data()[1]["nct_ids"]
    assert "NCT06964230" not in [t["nct_id"] for t in d["similar"]["nearest_terminated"]]
