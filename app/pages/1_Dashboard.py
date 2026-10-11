"""What the 41,380 trials say: termination rates and stop reasons."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common
from common import st, pd

common.setup("Dashboard")
st.title("Dashboard")
st.caption("Every number here is computed from the full data set: Phase 2, 2/3 and 3 trials with a drug or biological "
           "intervention, started 2008-2019, that ended as COMPLETED or TERMINATED. Withdrawn, unknown-status and "
           "still-running trials are not included, so true non-completion is probably higher.")
df = common.trials()
t = df[df.terminated == 1]

c1, c2, c3 = st.columns(3)
c1.metric("Trials", f"{len(df):,}")
c2.metric("Terminated", f"{df.terminated.mean()*100:.1f}%", help="Share of trials whose status is TERMINATED (stopped early).")
c3.metric("Low accrual", f"{df.terminated_low_accrual.mean()*100:.1f}%",
          help="Terminated AND the stated reason reads as too few participants (keyword rules, see About & Limits).")


def rate_table(col, order=None):
    g = df.groupby(col).agg(trials=("nct_id", "size"), terminated=("terminated", "mean"),
                            low_accrual=("terminated_low_accrual", "mean"))
    g["terminated"] *= 100; g["low_accrual"] *= 100
    g = g.rename(columns={"terminated": "terminated %", "low_accrual": "low-accrual %"})
    return g.loc[order] if order else g.sort_values("terminated %", ascending=False)


def show(title, g, note=None):
    st.markdown(f"### {title}")
    if note:
        st.caption(note)
    st.bar_chart(g[["terminated %", "low-accrual %"]], horizontal=len(g) > 6, height=max(260, 28 * len(g)) if len(g) > 6 else 300)
    st.dataframe(g.round(1), use_container_width=True)


area = rate_table("therapeutic_area")
n_other = int((df.therapeutic_area == "other").sum())
show("By therapeutic area", area,
     f"Areas come from a keyword mapping on condition names. **'other' holds {n_other:,} trials "
     f"({n_other/len(df)*100:.0f}%)**: conditions the mapping did not recognise. Treat area rates as approximate.")
show("By phase", rate_table("phase"), "Phase 2/3 trials are a combined design.")
show("By lead sponsor class", rate_table("sponsor_class"),
     "INDUSTRY = company; OTHER = mostly universities and hospitals; NIH / FED / OTHER_GOV = government; NETWORK = research networks; INDIV = individuals.")
yr = rate_table("start_year", order=sorted(df.start_year.unique()))
yr.index = yr.index.astype(int).astype(str)
st.markdown("### By start year")
st.caption("The rate rises for 2017-2019 starts. Terminations that cite COVID-19 are part of this, not all of it.")
st.line_chart(yr[["terminated %", "low-accrual %"]])
st.dataframe(yr.round(1), use_container_width=True)

st.markdown("### Why trials were stopped")
vc = t.stop_reason.value_counts()
rs = pd.DataFrame({"trials": vc, "% of terminated": (vc / len(t) * 100).round(1)})
rs.index = rs.index.map({"low_accrual": "Low accrual", "safety": "Safety", "efficacy_futility": "Efficacy / futility",
                         "sponsor_business": "Sponsor / business", "other_unspecified": "Other / unspecified"})
st.bar_chart(rs[["% of terminated"]], horizontal=True, height=300)
st.dataframe(rs, use_container_width=True)
empty = int((t.why_stopped.fillna("") == "").sum())
oth = int((t.stop_reason == "other_unspecified").sum())
st.warning(
    f"**'Other / unspecified' is the largest group: {oth:,} of {len(t):,} terminated trials ({oth/len(t)*100:.1f}%).** "
    f"{empty:,} of them ({empty/len(t)*100:.1f}% of all terminated) gave no reason at all; the rest have a reason our "
    "keyword rules do not recognise (for example drug supply, investigator left, regulatory hold). "
    "The reason classes therefore describe only the trials where a reason was stated and matched.")
