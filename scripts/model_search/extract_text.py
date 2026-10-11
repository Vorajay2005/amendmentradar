"""Phase A helper: pull sponsor name + eligibility text from the cached API v2 pages.

PROTOCOL: only trials with start year <= MAX_YEAR are kept at read time. Phase A uses MAX_YEAR=2016, so no
2017-2019 (test-period) record is ever held in memory beyond the read loop. Reads data/raw only (no network).
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"


def extract(max_year, out):
    rows = []
    for f in sorted(RAW.glob("*.json")):
        d = json.loads(f.read_text())
        for s in d.get("studies", []) if isinstance(d, dict) else []:
            p = s["protocolSection"]
            sd = (p["statusModule"].get("startDateStruct") or {}).get("date", "")
            if not sd[:4].isdigit() or int(sd[:4]) > max_year:
                continue  # protocol: later-period records are dropped immediately
            if p["statusModule"].get("overallStatus") not in ("COMPLETED", "TERMINATED"):
                continue
            rows.append({"nct_id": p["identificationModule"]["nctId"],
                         "sponsor_name": p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", ""),
                         "eligibility_text": p.get("eligibilityModule", {}).get("eligibilityCriteria", "") or ""})
    df = pd.DataFrame(rows).drop_duplicates("nct_id")
    df.to_csv(out, index=False, compression="gzip")
    return df


if __name__ == "__main__":
    max_year = int(sys.argv[1]); out = sys.argv[2]
    df = extract(max_year, out)
    print(len(df), "trials with start year <=", max_year, "->", out)
