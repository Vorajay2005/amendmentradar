"""Models, metrics and helpers shared by the benchmark and the app."""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from features import CAT_FEATURES, FEATURES, GROUPS, NUM_FEATURES, assert_no_leakage

LABELS = {"terminated": "Terminated (main)", "terminated_low_accrual": "Terminated for low accrual"}
TRAIN_YEARS, TEST_YEARS = (2008, 2016), (2017, 2019)
SEED = 0


def load(path="data/processed/trials.csv.gz"):
    return pd.read_csv(path, keep_default_na=False, na_values=[""])


def feature_frame(df, features=None):
    cols = list(features or FEATURES)
    assert_no_leakage(cols)
    return df[cols]


def split(df):
    tr = df.start_year.between(*TRAIN_YEARS)
    te = df.start_year.between(*TEST_YEARS)
    return df[tr], df[te]


def make_model(kind, features):
    cats = [c for c in features if c in CAT_FEATURES]
    nums = [c for c in features if c in NUM_FEATURES]
    num_steps = [("imp", SimpleImputer(strategy="median", add_indicator=False))]
    if kind == "lr":
        num_steps.append(("sc", StandardScaler()))
    pre = ColumnTransformer([
        ("num", Pipeline(num_steps), nums),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20, sparse_output=False), cats),
    ])
    if kind == "lr":
        clf = LogisticRegression(max_iter=2000, C=1.0)  # fixed a priori, not tuned
    else:  # fixed a priori, not tuned; early stopping uses a validation split of TRAIN only
        clf = HistGradientBoostingClassifier(learning_rate=0.05, max_iter=300, max_depth=4,
                                             min_samples_leaf=50, l2_regularization=1.0,
                                             early_stopping=True, validation_fraction=0.15,
                                             n_iter_no_change=20, random_state=SEED)
    return Pipeline([("pre", pre), ("clf", clf)])


def fit(kind, df, label, features=None):
    feats = list(features or FEATURES)
    m = make_model(kind, feats)
    m.fit(feature_frame(df, feats), df[label])
    return m


def predict(model, df, features=None):
    return model.predict_proba(feature_frame(df, features))[:, 1]


def boot_ci(y, p, fn, n=1000, seed=SEED):
    y, p = np.asarray(y), np.asarray(p)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() == y[i].max():
            continue
        vals.append(fn(y[i], p[i]))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def metrics(y, p):
    return {
        "auc": roc_auc_score(y, p), "auc_ci": boot_ci(y, p, roc_auc_score),
        "pr_auc": average_precision_score(y, p), "pr_ci": boot_ci(y, p, average_precision_score),
    }


def calibration_table(y, p, bins=10):
    d = pd.DataFrame({"y": np.asarray(y), "p": np.asarray(p)})
    d["bin"] = pd.qcut(d.p, bins, duplicates="drop")
    g = d.groupby("bin", observed=True).agg(n=("y", "size"), mean_pred=("p", "mean"), observed=("y", "mean"))
    return g.reset_index(drop=True)


def area_baseline(train, test, label):
    rates = train.groupby("therapeutic_area")[label].mean()
    return test.therapeutic_area.map(rates).fillna(train[label].mean()).values
