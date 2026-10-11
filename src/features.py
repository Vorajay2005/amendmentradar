"""Registered-design proxy features from an API v2 study record.

The v2 API returns the CURRENT record, so only fields describing the design as
planned are used. FORBIDDEN lists what must never reach the feature matrix.
"""
import math
import re

# Columns that reflect what happened during/after the trial (or are the label).
FORBIDDEN = [
    "enrollment", "enrollment_count", "enrollment_type", "n_locations", "n_countries",
    "overall_status", "status", "why_stopped", "stop_reason", "terminated",
    "terminated_low_accrual", "completion_date", "primary_completion_date",
    "last_update", "results", "publications", "references",
]

CAT_FEATURES = ["phase", "masking", "allocation", "intervention_model", "sex",
                "therapeutic_area", "sponsor_class"]
NUM_FEATURES = [
    "n_arms", "n_interventions", "n_primary_outcomes", "n_secondary_outcomes",
    "elig_chars", "elig_criteria", "elig_inclusion", "elig_exclusion",
    "min_age_years", "max_age_years", "max_age_missing", "healthy_volunteers",
    "n_conditions", "start_year", "has_dmc", "fda_regulated_drug",
    "int_drug", "int_biological", "int_device", "int_procedure", "int_behavioral",
    "int_other",
]
FEATURES = CAT_FEATURES + NUM_FEATURES

AREAS = [  # ordered, first match wins
    ("oncology", r"cancer|carcinoma|tumou?r|neoplasm|lymphoma|leuk[a]?emia|myeloma|melanoma|sarcoma|"
                 r"glioma|glioblastoma|metasta|malignan|oncolog|blastoma"),
    ("infectious_disease", r"infect|virus|viral|hiv|hepatitis|influenza|covid|sars|tubercul|malaria|"
                           r"sepsis|bacter|pneumonia|fung|vaccin|herpes|hpv|cmv|pathogen"),
    ("cardiovascular", r"heart|cardi|coronary|hypertens|atrial|stroke|vascular|thromb|embol|angina|"
                       r"myocardial|arrhythm|aneurysm|blood pressure|dyslipid|cholesterol"),
    ("neurology", r"alzheimer|parkinson|epilep|seizure|multiple sclerosis|migraine|neuropath|dementia|"
                  r"neuro|\bALS\b|huntington|headache|spinal cord|stroke"),
    ("psychiatry", r"depress|schizo|bipolar|anxiety|psych|adhd|autism|ptsd|insomnia|addict|alcohol|"
                   r"opioid use|smoking|substance|cocaine"),
    ("endocrine_metabolic", r"diabet|obes|thyroid|metabolic|insulin|glyc[a]?emi|osteopor|growth hormone|"
                            r"hypogonad|lipid|gout|vitamin"),
    ("respiratory", r"asthma|copd|pulmon|lung|respirat|bronch|cystic fibrosis|rhinitis|apnea|emphysema"),
    ("immunology_rheumatology", r"arthritis|lupus|psoria|crohn|colitis|autoimmun|spondyl|rheumat|"
                                r"allerg|atopic|transplant|graft|inflammat|sclero"),
    ("gastro_hepatology", r"gastr|bowel|liver|hepat|cirrhosis|pancrea|\bibs\b|reflux|constipation|"
                          r"diarrh|nash|esophag|colon"),
    ("renal_urology", r"kidney|renal|nephr|dialysis|urinary|bladder|prostat|incontinence|erectile"),
    ("hematology", r"anemi|anaemi|hemophil|haemophil|sickle|thalass|neutropen|thrombocyt|coagul|bleeding"),
    ("dermatology_ophthalmology", r"skin|derm|acne|eczema|wound|ulcer|eye|ophthalm|retin|macular|"
                                  r"glaucoma|ocular|cornea|uveitis"),
    ("womens_health_reproductive", r"pregnan|contracept|menopaus|endometri|ovar|infertil|preterm|"
                                   r"labor|labour|cesarean|vagin|uterine|breastfeeding"),
    ("pain_musculoskeletal_anesthesia", r"pain|osteoarth|fracture|back pain|anesth|anaesth|muscle|"
                                        r"tendon|surgery|postoperative|nausea"),
]
AREA_RES = [(a, re.compile(p, re.I)) for a, p in AREAS]
OTHER_AREA = "other"


def therapeutic_area(conditions, keywords=()):
    text = " ; ".join(list(conditions) + list(keywords))
    for area, rx in AREA_RES:
        if rx.search(text):
            return area
    return OTHER_AREA


def parse_age_years(s):
    if not isinstance(s, str):
        return math.nan
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*(year|month|week|day|hour|minute)", s, re.I)
    if not m:
        return math.nan
    div = {"year": 1, "month": 12, "week": 52.14, "day": 365.25, "hour": 8766, "minute": 525960}
    return float(m.group(1)) / div[m.group(2).lower()]


_BULLET = re.compile(r"^\s*(?:[-*•·]|\d+[.)]|[a-z][.)])\s+", re.I)
_HEAD = re.compile(r"^\s*(?:inclusion|exclusion)\s+criteria\s*:?\s*$", re.I)


def parse_eligibility(text):
    """Return (chars, n_criteria, n_inclusion, n_exclusion)."""
    if not isinstance(text, str) or not text.strip():
        return 0, 0, 0, 0
    m = re.search(r"exclusion\s+criteria", text, re.I)
    inc_txt, exc_txt = (text[:m.start()], text[m.start():]) if m else (text, "")

    def count(t):
        n = 0
        for line in t.splitlines():
            if not line.strip() or _HEAD.match(line):
                continue
            if _BULLET.match(line):
                n += 1
        if n == 0:  # unbulleted prose: count non-empty non-heading lines
            n = sum(1 for l in t.splitlines() if l.strip() and not _HEAD.match(l)
                    and not re.match(r"^\s*(inclusion|exclusion) criteria", l, re.I))
        return n

    ni, ne = count(inc_txt), count(exc_txt)
    return len(text), ni + ne, ni, ne


def extract_features(study):
    """Features + id/text columns from one API v2 study dict (current record)."""
    p = study["protocolSection"]
    ident, status = p["identificationModule"], p["statusModule"]
    design = p.get("designModule", {})
    di = design.get("designInfo", {})
    arms = p.get("armsInterventionsModule", {})
    out = p.get("outcomesModule", {})
    el = p.get("eligibilityModule", {})
    sp = p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {})
    ov = p.get("oversightModule", {})
    cond = p.get("conditionsModule", {})
    conds, kws = cond.get("conditions", []), cond.get("keywords", [])
    itypes = {i.get("type") for i in arms.get("interventions", [])}
    phases = design.get("phases", [])
    chars, ncrit, ninc, nexc = parse_eligibility(el.get("eligibilityCriteria"))
    maxage = parse_age_years(el.get("maximumAge"))
    start = (status.get("startDateStruct") or {}).get("date", "")
    hv = el.get("healthyVolunteers")
    return {
        "nct_id": ident["nctId"],
        "phase": "/".join(x.replace("PHASE", "") for x in phases) or "NA",
        "masking": (di.get("maskingInfo") or {}).get("masking", "UNKNOWN"),
        "allocation": di.get("allocation", "UNKNOWN"),
        "intervention_model": di.get("interventionModel", "UNKNOWN"),
        "sex": el.get("sex", "UNKNOWN"),
        "therapeutic_area": therapeutic_area(conds, kws),
        "sponsor_class": sp.get("class", "UNKNOWN"),
        "n_arms": len(arms.get("armGroups", [])),
        "n_interventions": len(arms.get("interventions", [])),
        "n_primary_outcomes": len(out.get("primaryOutcomes", [])),
        "n_secondary_outcomes": len(out.get("secondaryOutcomes", [])),
        "elig_chars": chars, "elig_criteria": ncrit, "elig_inclusion": ninc, "elig_exclusion": nexc,
        "min_age_years": parse_age_years(el.get("minimumAge")),
        "max_age_years": maxage, "max_age_missing": int(math.isnan(maxage)),
        "healthy_volunteers": {True: 1, False: 0}.get(hv, 0) if hv is not None else 0,
        "n_conditions": len(conds),
        "start_year": int(start[:4]) if start[:4].isdigit() else math.nan,
        "has_dmc": int(bool(ov.get("oversightHasDmc"))),
        "fda_regulated_drug": int(bool(ov.get("isFdaRegulatedDrug"))),
        "int_drug": int("DRUG" in itypes), "int_biological": int("BIOLOGICAL" in itypes),
        "int_device": int("DEVICE" in itypes), "int_procedure": int("PROCEDURE" in itypes),
        "int_behavioral": int("BEHAVIORAL" in itypes),
        "int_other": int(bool(itypes - {"DRUG", "BIOLOGICAL", "DEVICE", "PROCEDURE", "BEHAVIORAL"})),
    }


def extract_text(study):
    """Descriptive text for TF-IDF retrieval (title, conditions, interventions, design)."""
    p = study["protocolSection"]
    di = p.get("designModule", {}).get("designInfo", {})
    return {
        "title": p["identificationModule"].get("briefTitle", ""),
        "conditions": "; ".join(p.get("conditionsModule", {}).get("conditions", [])),
        "interventions": "; ".join(i.get("name", "") for i in p.get("armsInterventionsModule", {}).get("interventions", [])),
        "design_text": " ".join([di.get("allocation", ""), di.get("interventionModel", ""),
                                 (di.get("maskingInfo") or {}).get("masking", "")]).strip(),
    }
