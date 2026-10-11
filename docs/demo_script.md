# TrialRadar: 3-minute demo script

Total 3:00. Keep the browser on the app (`make run`), disclaimer banner visible the whole time.
Say "estimate", never "prediction of what will happen". Both examples below are **illustrative**
retrospective cases from the 2017-2019 benchmark test set, chosen by a fixed rule
(the test-set low-accrual positives ranked at the 90th and 10th percentile of the model's score),
not by looking for flattering cases. The models never trained on them.

| Time | Say | Show |
|---|---|---|
| 0:00-0:25 | **Problem.** Trials that stop early waste time and money. Tufts CSDD (Regeneron "Site Unseen" sheet): about 11% of chosen sites enroll zero patients and 37% enroll fewer than promised. TrialRadar learns from what actually happened to 41,380 real ClinicalTrials.gov trials. | Home page, banner. |
| 0:25-0:50 | **Honest framing up front.** Current-record snapshot, keyword-derived reasons, assists designers, not an approval tool. Then the headline numbers: low-accrual AUC about 0.70 and well calibrated; overall termination only about 0.65, so we show it as a relative band, never a percentage. | Open "How reliable is this?" and point at the AUC table. |
| 0:50-1:35 | **Illustrative hit.** Type `NCT03827850` (FGFR inhibitor, cancer, started 2019; it was in fact terminated for patient-enrolment difficulties). Show the low-accrual estimate (the model gave it about 13%, versus a 4.5% average for 2017-2019, upper third). Scroll: "X of the 25 most similar trials were terminated", the 5 nearest terminated trials with classified reason AND the raw stated reason, click one link to ClinicalTrials.gov. | Result page. Say: "this is a retrospective hit; the model had never seen it." |
| 1:35-2:10 | **Illustrative miss.** Type `NCT03598036` (voclosporin, started 2018, terminated for "Low recruitment rate"). The model put it in the lower third (about 1.7%). Say plainly: "we missed this one. The score is a ranking aid, not a verdict." Cite the band table from the benchmark: in 2017-2019 the upper third had about 8% low-accrual terminations versus about 2% in the lower third, so it separates groups, it does not identify individual trials. | Result page, then the band table in the panel. |
| 2:10-2:30 | **Design checks and drivers.** Show "What moves the estimate" and the percentile-vs-similar-trials list. Say: these describe where the design sits among similar trials; they do not say changing anything would help. | Drivers tab, design checks. |
| 2:30-2:50 | **Dashboard.** Termination rate by area, phase, sponsor and year (rise in 2017-2019, partly COVID-19). Point out "other" area is 12% and "other / unspecified" reasons are 37.9%; we show them rather than hide them. | Dashboard page. |
| 2:50-3:00 | **Close.** Open source (MIT), no LLMs, no API keys, runs offline from a clone: `make setup && make run`. Data: ClinicalTrials.gov, NLM. | About & Limits page, then repo URL. |

Backup if the network is down: both example trials are in the stored data, so the NCT lookup falls back
to the stored snapshot with a warning.
