"""Method, glossary, limits."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common
from common import st, ROOT

common.setup("About & Limits")
st.title("About & Limits")
st.markdown("""
**What TrialRadar does.** It learned from every Phase 2/3 drug or biological trial in ClinicalTrials.gov that started in
2008-2019 and ended as completed or terminated (41,380 trials). From design fields only (phase, masking, number of
arms and outcomes, eligibility length, sponsor type, therapeutic area, ...) it estimates how likely a similar design
was to be stopped early, and shows the most similar past trials with the reasons they gave.

**What it is not.** It does not approve or reject a design, and it does not say that changing a value will change
the outcome. Associations in past records are not causes.
""")
st.markdown("### How reliable is this?")
common.reliability_panel()
with st.expander("Full benchmark report"):
    st.markdown((ROOT / "BENCHMARK.md").read_text())
with st.expander("Label definitions (how 'low accrual' is decided)"):
    st.markdown((ROOT / "docs" / "labels.md").read_text())
st.markdown("### Glossary")
st.markdown("""
- **Terminated**: the registry status is TERMINATED, meaning the trial stopped early.
- **Low accrual**: terminated for too few participants joining ("accrual" and "enrollment" mean the same here).
- **ROC-AUC**: how well a score ranks trials. 0.5 is a coin flip; 1.0 is perfect. Ours: about 0.65 (overall) and 0.70 (low accrual).
- **Calibration**: whether "5%" really means about 5 in 100.
- **Band relative to 2017-2019**: lower / middle / upper third of the model's scores for trials that started in 2017-2019.
- **Masking**: who does not know which treatment a participant receives. **Allocation**: random or not.
- **Data monitoring committee (DMC)**: an independent group that reviews data during a trial.
- **Phase 2 / 3**: mid-stage (efficacy, dosing) and late-stage (confirmatory) trials.
""")
st.markdown("### Sources and license")
st.markdown(f"""
Data: [ClinicalTrials.gov](https://clinicaltrials.gov), U.S. National Library of Medicine, via the public API v2 (no key).
Context: Tufts CSDD figures from the Regeneron challenge sheet "Site Unseen": about 11% of chosen sites enroll zero
patients and 37% enroll fewer than promised.
Code: MIT license, [{common.REPO}]({common.REPO}). No LLMs and no API keys are used.
""")
