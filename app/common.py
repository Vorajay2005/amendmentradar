"""Shared helpers for all Streamlit pages."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import streamlit as st

import modeling
import retrieval
import scoring

REPO = "https://github.com/Vorajay2005/amendmentradar"

CSS = """
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 3rem; max-width: 880px;}
h1 {font-size: 1.9rem !important; line-height: 1.2;}
h2, h3 {margin-top: 1.4rem;}
.tr-banner {border-left: 4px solid #b45309; background: rgba(180,83,9,0.09); padding: .6rem .9rem;
            border-radius: 4px; font-size: .86rem; line-height: 1.45; margin-bottom: 1rem;}
.tr-card {border: 1px solid rgba(128,128,128,.35); border-radius: 8px; padding: .9rem 1rem; margin: .5rem 0;}
.tr-big {font-size: 2rem; font-weight: 700; line-height: 1.1;}
.tr-sub {font-size: .85rem; opacity: .8;}
.tr-reason {font-size: .88rem; margin: .1rem 0 0 0;}
@media (max-width: 640px) {.tr-big {font-size: 1.6rem;}}
</style>
"""


def setup(title):
    st.set_page_config(page_title=f"TrialRadar: {title}", page_icon="📡", layout="centered")
    st.markdown(CSS, unsafe_allow_html=True)
    disclaimer()


def disclaimer():
    st.markdown(
        '<div class="tr-banner"><b>Please read.</b> '
        "Data are a <b>current-record snapshot</b> from ClinicalTrials.gov (records may have been edited after registration). "
        "Reasons for stopping are <b>keyword-derived labels</b>, not human review. "
        "TrialRadar produces risk estimates that <b>assist trial designers</b>; it is <b>not an approval tool</b> "
        "and does not say whether a design is good or bad.</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def trials():
    return modeling.load(ROOT / "data" / "processed" / "trials.csv.gz")


@st.cache_resource(show_spinner=False)
def index_and_aligned():
    idx = retrieval.load_index(str(ROOT / "data" / "tfidf_index.joblib"))
    return idx, retrieval.aligned_trials(trials(), idx)


@st.cache_resource(show_spinner=False)
def typical():
    return scoring.typical_values(trials())


@st.cache_data(show_spinner=False)
def benchmark_sections():
    """BENCHMARK.md split on '## ' headings -> {number: text}."""
    text = (ROOT / "BENCHMARK.md").read_text()
    parts = re.split(r"\n(?=## )", text)
    out = {"intro": parts[0]}
    for p in parts[1:]:
        m = re.match(r"## (\d+)\.", p)
        if m:
            out[int(m.group(1))] = p
    return out


def reliability_panel():
    """'How reliable is this?' -- tables taken straight from BENCHMARK.md."""
    s = benchmark_sections()
    st.markdown(
        "**Short answer:** the ranking is only **weak** for overall termination (AUC about 0.65) and "
        "**modest** for low accrual (AUC about 0.70, well calibrated). Use it as one screening input, not a verdict.")
    st.markdown(s[1].replace("## 1.", "#### 1."))
    st.markdown(s[2].replace("## 2.", "#### 2."))
    st.markdown(s[3].replace("## 3.", "#### 3."))
    with st.expander("Limits"):
        st.markdown(s[8].replace("## 8.", "#### 8."))
    st.caption("Tables above are read from BENCHMARK.md, produced by `make benchmark`. "
               "ROC-AUC: 0.5 = coin flip, 1.0 = perfect ranking.")


def link(nct):
    return retrieval.ctgov_link(nct)
