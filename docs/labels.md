# Label definitions

Source: ClinicalTrials.gov API v2 (NLM). Population: interventional, Phase 2 /
Phase 2-3 / Phase 3, Drug or Biological intervention, start date 2008-2019,
overall status COMPLETED or TERMINATED. N = 41,380 (the entire matching set; no
sampling).

## Binary labels
| Label | Definition |
|---|---|
| `terminated` | 1 if overall status is TERMINATED, 0 if COMPLETED. |
| `terminated_low_accrual` | 1 if terminated AND the why-stopped text is classified `low_accrual` (below). Completed trials are 0. |

## Stop-reason classes (terminated trials only)
Rules are applied **in order, most specific first; the first match wins**
(case-insensitive regex, `src/labels.py`).

1. **safety**: safety, adverse, toxic*, side effect, SAE, tolerab*, death, harm,
   hepatotox/cardiotox, "risk to patient". 
2. **efficacy_futility**: efficacy, futility, interim analysis, lack of
   benefit/effect, no benefit, "did not show/meet/achieve ... primary/efficacy/endpoint/benefit",
   ineffective, no difference/effect, primary endpoint/outcome.
3. **sponsor_business**: sponsor, business, strategic, funding/funds, financial,
   portfolio, "development plan", decision (not) to / decided (not) to, company,
   commercial, priorit*, budget, acquisition, merger, discontinued
   development/program, withdrawal/lack of support or funding.
4. **low_accrual**: a recruitment word (recruit, accrual, enrol(l)ment) AND a
   difficulty word (slow, low, poor, insufficient, inadequate, lack of,
   difficult*, fail(ure) to, unable, not enough, too few, few, limited,
   challeng*, unsuccessful, issue(s), problem(s), shortfall, not met/reached,
   "did not enrol") or "no patients/participants/subjects enrolled". Bare
   "patients", "participants", "low", "slow", "enrollment" never match alone.
5. **other_unspecified**: empty text or no match (includes drug supply,
   PI departure, COVID-19, regulatory/clinical hold, etc.).

### Negation handling
Before rules 1 and 2, negated mentions are stripped up to the end of the clause,
so "Terminated *not based on safety concerns*, but due to insufficient efficacy"
is efficacy and "Business Decision; *No Safety or Efficacy Concerns*" is
sponsor/business. Without this, 350 trials were wrongly labeled safety in our
first audit.

### Worked examples
| why-stopped text | class |
|---|---|
| "Enrollment was stopped after the sponsor's decision not to pursue ..." | sponsor_business |
| "Interim analysis ... did not show evidence of treatment benefit" | efficacy_futility |
| "lack of study recruitment" | low_accrual |
| "Slow accrual" | low_accrual |
| "Problems with drug supply" | other_unspecified |

## Known limits of the labels
- Free text is keyword-matched, not understood. Expect some mislabeling in
  both directions; we eyeballed 30-example samples per revision, no gold set.
- Order matters: a record that states an accrual problem and then says "the
  sponsor decided to stop" is `sponsor_business`, so `terminated_low_accrual`
  is conservative (undercounts true accrual-driven stops).
- 738 of 7,085 terminated trials (10.4%) have no why-stopped text; they are
  `other_unspecified` and are never counted as low accrual.
- `whyStopped` is used ONLY to build labels. It is never a model feature.
- Records are the CURRENT version; status/reason may reflect later edits.

## Selection effect
Excluded under the same filters (counts from the API at build time, see
`data/processed/selection_counts.json`): WITHDRAWN 2,204; UNKNOWN 6,774;
RECRUITING 567; ACTIVE_NOT_RECRUITING 1,669; SUSPENDED 139;
ENROLLING_BY_INVITATION 25; NOT_YET_RECRUITING 11. Withdrawn trials (stopped
before enrolling anyone) and unknown-status trials (often abandoned sites) are
plausibly more failure-prone, so true termination/non-completion rates for the
registry as a whole are likely higher than the 17.1% observed here.
