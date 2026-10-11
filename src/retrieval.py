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
