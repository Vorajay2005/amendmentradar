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


def get_json(url, params=None, tries=5):
    key = hashlib.md5((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    RAW.mkdir(parents=True, exist_ok=True)
    f = RAW / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text())
    for i in range(tries):
        wait = MIN_GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=60)
            if r.status_code == 200:
                f.write_text(r.text)
                return r.json()
            if r.status_code not in (429, 500, 502, 503, 504):
                r.raise_for_status()
        except requests.RequestException:
            if i == tries - 1:
                raise
        time.sleep(2 ** i)
    raise RuntimeError(f"failed after retries: {url}")


def fetch_page(status, page_size=1000, page_token=None):
    p = {"filter.overallStatus": status, "filter.advanced": ADVANCED,
         "pageSize": page_size, "countTotal": "true", "format": "json"}
    if page_token:
        p["pageToken"] = page_token
    return get_json(BASE, p)
