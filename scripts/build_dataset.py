"""Build data/processed/ from the cached API v2 pull (fetches if cache is empty)."""
import sys, json
sys.path.insert(0, "src")
import pandas as pd
from ctgov import fetch_all, get_json, BASE, ADVANCED
from features import extract_features, extract_text
from labels import make_labels

studies = fetch_all(log=lambda m: None)
rows = []
for s in studies:
    st = s["protocolSection"]["statusModule"]
    r = extract_features(s)
    r.update(extract_text(s))
    r["status"] = st["overallStatus"]
    r["why_stopped"] = st.get("whyStopped", "") if st["overallStatus"] == "TERMINATED" else ""
    r.update(make_labels(st["overallStatus"], st.get("whyStopped")))
    rows.append(r)
df = pd.DataFrame(rows)
assert df.nct_id.is_unique and df.start_year.between(2008, 2019).all()
df.to_csv("data/processed/trials.csv.gz", index=False)

# Selection-effect documentation: counts of excluded statuses under the same filter.
sel = {"included": {k: int(v) for k, v in df.status.value_counts().items()}, "excluded": {}}
for st in ["WITHDRAWN", "UNKNOWN", "RECRUITING", "ACTIVE_NOT_RECRUITING", "NOT_YET_RECRUITING",
           "ENROLLING_BY_INVITATION", "SUSPENDED", "NO_LONGER_AVAILABLE"]:
    d = get_json(BASE, {"filter.overallStatus": st, "filter.advanced": ADVANCED, "pageSize": 1,
                        "countTotal": "true", "format": "json"})
    sel["excluded"][st] = d.get("totalCount", 0)
json.dump(sel, open("data/processed/selection_counts.json", "w"), indent=1)
print(json.dumps(sel, indent=1))
print(df.shape)
