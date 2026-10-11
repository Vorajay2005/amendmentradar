import numpy as np
import pytest

from modeling import load
from retrieval import aligned_trials, ctgov_link, load_index, query, doc_text


@pytest.fixture(scope="module")
def setup():
    idx = load_index()
    return idx, aligned_trials(load(), idx)


def test_index_aligned(setup):
    idx, tr = setup
    assert tr.nct_id.tolist() == idx["nct_ids"] and idx["matrix"].shape[0] == len(tr)


def test_self_query_and_exclusion(setup):
    idx, tr = setup
    row = tr.iloc[100]
    text = doc_text(row.fillna(""))
    q = query(text, tr, idx)
    assert q["near"].iloc[0]["similarity"] > 0.99 and len(q["near"]) == 25
    q2 = query(text, tr, idx, exclude=row.nct_id)
    assert row.nct_id not in q2["near"].nct_id.values


def test_nearest_terminated_are_terminated_and_sorted(setup):
    idx, tr = setup
    q = query("breast cancer ; paclitaxel ; RANDOMIZED PARALLEL", tr, idx)
    nt = q["nearest_terminated"]
    assert len(nt) == 5 and (nt.terminated == 1).all()
    assert list(nt.similarity) == sorted(nt.similarity, reverse=True)
    assert 0 <= q["share_terminated"] <= 1 and q["n_terminated"] == int(q["near"].terminated.sum())


def test_no_overlap_text(setup):
    idx, tr = setup
    q = query("zzzzqqqq xxxxyyyy", tr, idx)
    assert q["found"] is False and q["nearest_terminated"].empty


def test_link():
    assert ctgov_link("NCT01234567") == "https://clinicaltrials.gov/study/NCT01234567"
