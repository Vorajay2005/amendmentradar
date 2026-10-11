"""TF-IDF index over condition + intervention + design text (used by Step 5 / the app)."""
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

INDEX_PATH = "data/tfidf_index.joblib"


def doc_text(row):
    return f"{row['conditions']} ; {row['interventions']} ; {row['design_text']}"


def build_index(df, path=INDEX_PATH):
    docs = df.fillna("").apply(doc_text, axis=1)
    vec = TfidfVectorizer(lowercase=True, stop_words="english", ngram_range=(1, 2), min_df=3,
                          max_features=60000, sublinear_tf=True, dtype="float32")
    mat = vec.fit_transform(docs)
    joblib.dump({"vectorizer": vec, "matrix": mat, "nct_ids": df.nct_id.tolist()}, path, compress=3)
    return vec, mat


# ---------------------------------------------------------------- queries
import numpy as np

_CACHE = {}


def load_index(path=INDEX_PATH):
    if path not in _CACHE:
        _CACHE[path] = joblib.load(path)
    return _CACHE[path]


def aligned_trials(trials, index):
    """Trials table reordered to match the index rows."""
    return trials.set_index("nct_id", drop=False).loc[index["nct_ids"]].reset_index(drop=True)


def similarities(text, index):
    """Cosine similarity (TF-IDF vectors are L2-normalised) of text to every indexed trial."""
    v = index["vectorizer"].transform([text])
    return (index["matrix"] @ v.T).toarray().ravel()


def query(text, trials, index=None, exclude=None, k_all=25, k_term=5):
    """Nearest k_all trials (any status) and nearest k_term TERMINATED trials.

    trials must be row-aligned with the index (use aligned_trials).
    Returns dict: near (DataFrame with 'similarity'), n_terminated, share_terminated,
    nearest_terminated (DataFrame with 'similarity'), found (False if no text overlap).
    """
    index = index or load_index()
    sims = similarities(text, index)
    if exclude is not None and exclude in index["nct_ids"]:
        sims[index["nct_ids"].index(exclude)] = -1.0
    if sims.max() <= 0:
        empty = trials.iloc[0:0].assign(similarity=[])
        return {"found": False, "near": empty, "n_terminated": 0, "share_terminated": float("nan"),
                "nearest_terminated": empty}
    top = np.argsort(-sims, kind="stable")[:k_all]
    near = trials.iloc[top].assign(similarity=sims[top])
    term_idx = np.flatnonzero(trials.terminated.values == 1)
    top_t = term_idx[np.argsort(-sims[term_idx], kind="stable")[:k_term]]
    nearest_t = trials.iloc[top_t].assign(similarity=sims[top_t])
    n_t = int(near.terminated.sum())
    return {"found": True, "near": near, "n_terminated": n_t, "share_terminated": n_t / len(near),
            "nearest_terminated": nearest_t}


def trial_text(feats_text):
    """feats_text: dict with conditions / interventions / design_text (see features.extract_text)."""
    return doc_text(feats_text)


def ctgov_link(nct_id):
    return f"https://clinicaltrials.gov/study/{nct_id}"
