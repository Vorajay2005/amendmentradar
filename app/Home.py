"""TrialRadar home: look up an NCT ID or describe a design, get a risk read-out."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import st, pd, scoring, retrieval

common.setup("Home")
st.title("📡 TrialRadar")
st.caption("Early-stopping risk for clinical trial designs, learned from 41,380 real ClinicalTrials.gov records. "
           "A decision-support aid for trial designers.")

REASON = {"low_accrual": "Low accrual", "safety": "Safety", "efficacy_futility": "Efficacy / futility",
          "sponsor_business": "Sponsor / business", "other_unspecified": "Other / unspecified"}
trials = common.trials()
idx, aligned = common.index_and_aligned()
meta = scoring.models()["meta"]

# ---------------------------------------------------------------- input
mode = st.radio("How do you want to describe the trial?", ["ClinicalTrials.gov NCT ID", "Manual design form"],
                horizontal=True, help="NCT lookup fetches the current public record (works for trials that have not started yet). "
                                      "The form lets you describe a design that is not registered.")
study = None
if mode.startswith("Clinical"):
    c1, c2 = st.columns([3, 1])
    nct = c1.text_input("NCT ID", value="", placeholder="NCT01234567", label_visibility="collapsed")
    go = c2.button("Analyze", type="primary", use_container_width=True)
    if go:
        st.session_state.pop("result", None)
        st.session_state.pop("result_row", None)
        try:
            with st.spinner("Fetching record from ClinicalTrials.gov..."):
                study = scoring.fetch_study(nct)
            st.session_state["offline_note"] = None
        except ValueError as e:
            st.error(str(e))
        except LookupError as e:
            st.error(str(e))
        except Exception:
            q = nct.strip().upper()
            if q in set(trials.nct_id):
                st.warning("Could not reach ClinicalTrials.gov, so the stored snapshot of this trial is used instead.")
                row = trials[trials.nct_id == q].iloc[0]
                study = None
                st.session_state["result_row"] = row
            else:
                st.error("Could not reach ClinicalTrials.gov (offline or rate-limited). Try again, or use the manual form.")
else:
    with st.form("manual"):
        st.markdown("Describe the planned design. Defaults are sensible starting values.")
        a, b = st.columns(2)
        phase = a.selectbox("Phase", ["PHASE2", "PHASE2/PHASE3", "PHASE3"], index=2,
                            help="Phase 2 tests efficacy/dose in patients; Phase 3 confirms in larger groups.")
        sponsor = b.selectbox("Lead sponsor class", ["INDUSTRY", "OTHER", "NIH", "FED", "OTHER_GOV", "NETWORK", "INDIV"],
                              help="INDUSTRY = company; OTHER = e.g. universities and hospitals; NIH/FED/OTHER_GOV = government; NETWORK = research network; INDIV = individual.")
        conds = st.text_input("Condition(s), comma separated", "Type 2 diabetes")
        ints = st.text_input("Intervention name(s), comma separated", "metformin, placebo")
        itypes = st.multiselect("Intervention type(s)", ["DRUG", "BIOLOGICAL", "DEVICE", "PROCEDURE", "BEHAVIORAL", "OTHER"], default=["DRUG"])
        a, b, c = st.columns(3)
        alloc = a.selectbox("Allocation", ["RANDOMIZED", "NON_RANDOMIZED", "NA"], help="How participants are assigned to arms.")
        model = b.selectbox("Intervention model", ["PARALLEL", "CROSSOVER", "SINGLE_GROUP", "FACTORIAL", "SEQUENTIAL"],
                            help="PARALLEL: each group gets one treatment. CROSSOVER: everyone gets each treatment in turn.")
        mask = c.selectbox("Masking (blinding)", ["NONE", "SINGLE", "DOUBLE", "TRIPLE", "QUADRUPLE"],
                           help="Who does not know which treatment is given.")
        a, b, c, d = st.columns(4)
        arms = a.number_input("Arms", 1, 20, 2)
        nint = b.number_input("Interventions", 1, 20, 2)
        npri = c.number_input("Primary outcomes", 1, 20, 1)
        nsec = d.number_input("Secondary outcomes", 0, 50, 4)
        elig = st.text_area("Eligibility criteria (paste text; bullets and an 'Exclusion Criteria' heading are used to count items)",
                            "Inclusion Criteria:\n- Adults with type 2 diabetes\n- HbA1c 7-10%\n\nExclusion Criteria:\n- Pregnancy\n- Kidney disease", height=140)
        a, b, c, d = st.columns(4)
        minage = a.number_input("Min age (years)", 0, 120, 18)
        maxage = b.number_input("Max age (0 = none)", 0, 120, 0)
        sex = c.selectbox("Sex", ["ALL", "FEMALE", "MALE"])
        hv = d.checkbox("Healthy volunteers", help="Whether people without the condition may join.")
        a, b, c = st.columns(3)
        dmc = a.checkbox("Data monitoring committee", help="An independent group that reviews safety/efficacy data during the trial.")
        fda = b.checkbox("FDA-regulated drug")
        year = c.number_input("Planned start year", 2008, 2035, 2026)
        sub = st.form_submit_button("Analyze", type="primary", use_container_width=True)
    if sub:
        study = scoring.study_from_inputs(dict(
            phase=phase, sponsor_class=sponsor, conditions=conds, intervention_names=ints, intervention_types=itypes,
            allocation=alloc, intervention_model=model, masking=mask, n_arms=arms, n_interventions=nint,
            n_primary=npri, n_secondary=nsec, eligibility=elig, min_age=minage, max_age=maxage or None,
            sex=sex, healthy_volunteers=hv, has_dmc=dmc, fda_drug=fda, start_year=year))

if study is not None:
    feats, text, info = scoring.prepare(study)
    st.session_state["result"] = (feats, text, info)
    st.session_state.pop("result_row", None)
elif "result_row" in st.session_state:  # offline fallback to stored snapshot
    r = st.session_state["result_row"]
    feats = {k: r[k] for k in scoring.FEATURES}
    text = {k: ("" if pd.isna(r[k]) else r[k]) for k in ["conditions", "interventions", "design_text", "title"]}
    st.session_state["result"] = (feats, text, {"nct_id": r.nct_id, "title": r.title, "status": r.status, "raw_start_year": r.start_year})

# ---------------------------------------------------------------- output
if "result" in st.session_state:
    feats, text, info = st.session_state["result"]
    is_manual = info["nct_id"] == "MANUAL"
    st.divider()
    if is_manual:
        st.subheader("Your design")
    else:
        st.subheader(f"{info['nct_id']}")
        st.markdown(f"[{info['title']}]({common.link(info['nct_id'])})  \nCurrent status on ClinicalTrials.gov: **{info['status'].replace('_', ' ').title()}**")
    in_data = (not is_manual) and info["nct_id"] in set(trials.nct_id)
    if in_data:
        yr = int(trials.loc[trials.nct_id == info["nct_id"], "start_year"].iloc[0])
        if yr <= 2016:
            st.info("This trial was part of the data the models were trained on (start 2008-2016), so its scores are optimistic. "
                    "It is excluded from its own list of similar trials.")
        else:
            st.info("This trial started in 2017-2019: it belongs to the benchmark test period, so the models did not train on it. "
                    "It is excluded from its own list of similar trials, and its real outcome is already in the data.")
    if not is_manual and isinstance(info["raw_start_year"], float) and math.isnan(info["raw_start_year"]):
        st.caption("No start date on record; the model fills in a typical value.")
    elif info["raw_start_year"] and info["raw_start_year"] > 2019:
        st.caption(f"Start year {int(info['raw_start_year'])} is outside the 2008-2019 training range; it is scored as 2019.")

    s = scoring.score(feats)
    near = retrieval.query(retrieval.trial_text(text), common.index_and_aligned()[1], idx,
                           exclude=None if is_manual else info["nct_id"])
    lo = s["terminated_low_accrual"]; mn = s["terminated"]
    base_low = meta["test_rate"]["terminated_low_accrual"] * 100
    # 1) low accrual first
    st.markdown("### Risk of stopping early for low accrual")
    st.markdown(
        f'<div class="tr-card"><div class="tr-sub">Estimated chance of being terminated for low accrual</div>'
        f'<div class="tr-big">{lo["p"]*100:.1f}%</div>'
        f'<div class="tr-sub">Band: <b>{lo["band"]}</b> of predicted risk, relative to trials starting 2017-2019. '
        f'The 2017-2019 average was {base_low:.1f}%.</div></div>', unsafe_allow_html=True)
    st.caption("Low accrual means too few participants joined. This estimate was well calibrated on 2017-2019 trials "
               "(AUC about 0.70, 441 test positives). It is a base-rate-anchored estimate, not a prediction for this specific trial.")
    # 2) main label as relative band only
    st.markdown("### Overall early-termination risk (relative)")
    st.markdown(
        f'<div class="tr-card"><div class="tr-sub">Band relative to trials starting 2017-2019</div>'
        f'<div class="tr-big">{mn["band"]}</div></div>', unsafe_allow_html=True)
    st.caption("Shown as a band, not a percentage: the model under-predicts termination for 2017-2019 starts "
               "(partly COVID-19), so a raw probability would mislead. Overall ranking skill is weak (AUC about 0.65).")

    # 3) similar trials
    st.markdown("### What happened to similar trials")
    if not near["found"]:
        st.warning("No similar trials were found (no overlapping condition or intervention words).")
    else:
        n_t = near["n_terminated"]
        st.markdown(f"**{n_t} of the 25 most similar trials were terminated** "
                    f"({near['share_terminated']*100:.0f}%; {meta['base_rate_all']['terminated']*100:.1f}% of all trials in the data).")
        nt = near["nearest_terminated"]
        st.markdown("**The 5 nearest terminated trials and their stated reasons**")
        for _, r in nt.iterrows():
            raw = r.why_stopped if isinstance(r.why_stopped, str) and r.why_stopped.strip() else "(no reason given)"
            st.markdown(
                f'<div class="tr-card"><a href="{common.link(r.nct_id)}" target="_blank"><b>{r.nct_id}</b></a> '
                f'<span class="tr-sub">· similarity {r.similarity:.2f} · started {int(r.start_year)}</span><br>'
                f'{r.title}<p class="tr-reason"><b>Classified as:</b> {REASON.get(r.stop_reason, r.stop_reason)}<br>'
                f'<b>Stated reason:</b> <i>{raw[:400]}</i></p></div>', unsafe_allow_html=True)

    # 4) drivers
    st.markdown("### What moves the estimate")
    st.caption("How each feature changes the estimate compared with a typical 2008-2016 trial. These are associations "
               "in past records, not causes, and not advice to change anything.")
    tab1, tab2 = st.tabs(["Low accrual", "Overall termination"])
    for tab, lab in [(tab1, "terminated_low_accrual"), (tab2, "terminated")]:
        with tab:
            up, down = scoring.drivers(feats, lab, common.typical())
            if not up and not down:
                st.write("No single feature stands out from a typical trial.")
            for x in up:
                st.markdown("▲ " + x)
            for x in down:
                st.markdown("▼ " + x)

    # 5) design checks
    st.markdown("### Design checks (descriptive)")
    if near["found"]:
        chk = pd.DataFrame(scoring.percentile_checks(feats, near["near"]))
        st.caption("Where this design sits among its 25 most similar trials. A value at either extreme is just unusual "
                   "for this group; it is not a finding that anything is wrong, and it does not say what would change the outcome.")
        for _, r in chk.iterrows():
            tag = f" — **{r['note']}**" if r["note"] else ""
            st.markdown(f"- {r['measure']}: {r['this trial']} (similar trials' median {r['median of similar']}; "
                        f"higher than ~{r['percentile among 25 similar']}% of them){tag}")
    else:
        st.write("Not available without similar trials.")

    with st.expander("How reliable is this?", expanded=False):
        common.reliability_panel()
else:
    with st.expander("How reliable is this?"):
        common.reliability_panel()
