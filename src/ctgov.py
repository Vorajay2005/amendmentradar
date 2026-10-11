"""Polite ClinicalTrials.gov API v2 client (public endpoint, no key).

Only /api/v2/studies is used. Responses are cached in data/raw/.
"""
import hashlib
import json
import time
from pathlib import Path

import requests

BASE = "https://clinicaltrials.gov/api/v2/studies"
UA = "TrialRadar-HackRU2026/0.1 (open-source student project; https://github.com/Vorajay2005/amendmentradar)"
RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
MIN_GAP = 0.6
_last = [0.0]

ADVANCED = (
    "AREA[StudyType]INTERVENTIONAL AND AREA[Phase](PHASE2 OR PHASE3) "
    "AND AREA[InterventionType](DRUG OR BIOLOGICAL) "
    "AND AREA[StartDate]RANGE[2008-01-01,2019-12-31]"
)


def get_json(url, params=None, tries=5, use_cache=True, timeout=60, backoff=1.0):
    key = hashlib.md5((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    RAW.mkdir(parents=True, exist_ok=True)
    f = RAW / f"{key}.json"
    if use_cache and f.exists():
        return json.loads(f.read_text())
    for i in range(tries):
        wait = MIN_GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=timeout)
            if r.status_code == 200:
                if use_cache:
                    f.write_text(r.text)
                return r.json()
            if r.status_code not in (429, 500, 502, 503, 504):
                r.raise_for_status()
        except requests.RequestException:
            if i == tries - 1:
                raise
        time.sleep(backoff * 2 ** i)
    raise RuntimeError(f"failed after retries: {url}")


def fetch_page(status, page_size=1000, page_token=None):
    p = {"filter.overallStatus": status, "filter.advanced": ADVANCED,
         "pageSize": page_size, "countTotal": "true", "format": "json"}
    if page_token:
        p["pageToken"] = page_token
    return get_json(BASE, p)


# Only fields needed for allowed features / labels / retrieval. Enrollment,
# locations, completion dates, results and references are deliberately NOT requested.
FIELDS = "|".join([
    "NCTId", "BriefTitle", "OverallStatus", "WhyStopped", "StartDate", "StudyFirstPostDate",
    "Phase", "DesignAllocation", "DesignInterventionModel", "DesignPrimaryPurpose", "DesignMasking",
    "ArmGroupLabel", "ArmGroupType", "InterventionType", "InterventionName",
    "PrimaryOutcomeMeasure", "SecondaryOutcomeMeasure",
    "EligibilityCriteria", "HealthyVolunteers", "Gender", "MinimumAge", "MaximumAge",
    "Condition", "Keyword", "LeadSponsorName", "LeadSponsorClass",
    "OversightHasDMC", "IsFDARegulatedDrug",
])


def fetch_all(page_size=1000, log=print):
    """Whole matching population (COMPLETED + TERMINATED); resumable via cache."""
    studies, token, n = [], None, 0
    while True:
        p = {"filter.overallStatus": "COMPLETED|TERMINATED", "filter.advanced": ADVANCED,
             "fields": FIELDS, "pageSize": page_size, "countTotal": "true", "format": "json"}
        if token:
            p["pageToken"] = token
        d = get_json(BASE, p)
        studies += d["studies"]
        n += 1
        log(f"page {n}: {len(studies)}/{d.get('totalCount')}")
        token = d.get("nextPageToken")
        if not token:
            return studies
