import pytest
from fastapi.testclient import TestClient

from api.main import app
import scoring

c = TestClient(app)
DESIGN = dict(phase="PHASE3", conditions="Type 2 diabetes", intervention_names="metformin, placebo",
              eligibility="Inclusion Criteria:\n- a\n- b\n\nExclusion Criteria:\n- c", start_year=2026)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Tests never touch the network: the live fetch always fails unless a test patches it."""
    def boom(nct):
        if not scoring.NCT_RE.match(nct.strip().upper()):
            raise ValueError("An NCT ID looks like NCT01234567 (NCT followed by 8 digits).")
        raise ConnectionError("offline")
    monkeypatch.setattr(scoring, "fetch_study", boom)


def test_manual_analyze_shape():
    r = c.post("/api/analyze", json={"design": DESIGN}); assert r.status_code == 200
    d = r.json()
    assert d["source"] == "manual" and d["trial"]["nct_id"] is None
    assert 0 < d["low_accrual"]["probability"] < 1 and d["low_accrual"]["band"] in ("Lower third", "Middle third", "Upper third")
    assert "probability" not in d["overall"]  # overall termination is a relative band only
    assert d["similar"]["size"] == 25 and 0 <= d["similar"]["n_terminated"] <= 25
    assert len(d["similar"]["nearest_terminated"]) == 5
    n = d["similar"]["nearest_terminated"][0]
    assert n["link"].startswith("https://clinicaltrials.gov/study/NCT") and "stop_reason_label" in n and "why_stopped" in n
    assert all(0 <= x["percentile"] <= 100 for x in d["design_checks"])
    assert any(n_["kind"] == "clamped_year" for n_ in d["notes"])


def test_stored_snapshot_fallbacks():
    r = c.post("/api/analyze", json={"nct_id": "NCT03827850"}).json()
    assert r["source"] == "stored_snapshot" and "could not be reached" in r["source_note"]
    assert r["trial"]["link"].endswith("NCT03827850") and any(n["kind"] == "in_test" for n in r["notes"])
    assert "NCT03827850" not in [x["nct_id"] for x in r["similar"]["nearest_terminated"]]
    r = c.post("/api/analyze", json={"nct_id": "nct06964230"}).json()  # not in dataset: bundled example record
    assert r["source"] == "stored_snapshot" and r["trial"]["status"] == "NOT_YET_RECRUITING"


def test_errors_are_structured():
    r = c.post("/api/analyze", json={"nct_id": "banana"}); assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_nct"
    r = c.post("/api/analyze", json={"nct_id": "NCT00000001"}); assert r.status_code == 503 and r.json()["error"]["code"] == "unreachable"
    assert c.post("/api/analyze", json={}).status_code == 422
    assert c.post("/api/analyze", json={"nct_id": "NCT03827850", "design": DESIGN}).status_code == 422
    bad = dict(DESIGN, n_arms=99); assert c.post("/api/analyze", json={"design": bad}).status_code == 422
    assert c.post("/api/analyze", json={"design": dict(DESIGN, conditions="")}).status_code == 422


def test_not_found_from_live(monkeypatch):
    def nf(nct): raise LookupError(f"{nct} was not found on ClinicalTrials.gov.")
    monkeypatch.setattr(scoring, "fetch_study", nf)
    r = c.post("/api/analyze", json={"nct_id": "NCT00000002"}); assert r.status_code == 404


def test_dashboard_shows_other_buckets():
    d = c.get("/api/dashboard").json()
    assert d["totals"]["trials"] == 41380 and any(a["key"] == "other" for a in d["by_area"])
    assert [y["label"] for y in d["by_year"]] == [str(y) for y in range(2008, 2020)]
    assert abs(sum(r["pct_of_terminated"] for r in d["reasons"]) - 100) < 0.2
    assert d["other_reason"]["pct_of_terminated"] > 30 and d["other_area"]["pct"] > 10


def test_reliability_matches_benchmark_md():
    d = c.get("/api/reliability").json()
    gb = {r["label"]: r for r in d["main_results"] if r["model"] == "Gradient boosting"}
    assert gb["terminated_low_accrual"]["auc"] == pytest.approx(0.701, abs=1e-3) and gb["terminated"]["auc"] == pytest.approx(0.646, abs=1e-3)
    assert gb["terminated"]["ci_low"] < gb["terminated"]["auc"] < gb["terminated"]["ci_high"]
    assert d["test_positives"]["terminated_low_accrual"] == 441 and len(d["limits"]) >= 7 and len(d["drift"]) == 12
    assert d["band_rates"]["terminated_low_accrual"]["Upper third"] > d["band_rates"]["terminated_low_accrual"]["Lower third"]


def test_examples_and_spa_fallback():
    ex = c.get("/api/examples").json(); assert [e["kind"] for e in ex] == ["hit", "miss", "new"]
    assert c.get("/api/nope").status_code == 404
    assert c.get("/analyze").status_code in (200, 503)
