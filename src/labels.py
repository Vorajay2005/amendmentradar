"""Label logic. Rules are ORDERED, most specific first; first match wins.
Documented in docs/labels.md."""
import re

REASONS = ["safety", "efficacy_futility", "sponsor_business", "low_accrual", "other_unspecified"]

SAFETY = re.compile(
    r"safety|adverse|toxic|side[- ]effect|\bsae\b|\bsaes\b|tolerab|\bdeaths?\b|\bharm|"
    r"hepatotox|cardiotox|risk to (the )?(patient|participant|subject)", re.I)

EFFICACY = re.compile(
    r"efficac|futil|interim analys|lack of (benefit|effect)|no (clinical )?benefit|"
    r"(did not|didn'?t|failed to|not|unable to) (show|demonstrate|meet|achieve|reach|establish) "
    r"(\w+ ){0,3}(primary|efficacy|end-?point|benefit|superiority|non-?inferiority|statistical)|"
    r"ineffective|not effective|no (significant )?(difference|effect)|"
    r"unlikely to (show|meet|achieve|demonstrate)|primary (end ?point|outcome)", re.I)

SPONSOR = re.compile(
    r"sponsor|business|strateg|funding|\bfunds?\b|financ|portfolio|development plan|"
    r"decision (not )?to|decided (not )?to|company|commercial|priorit|budget|"
    r"acqui[rs]ition|merger|discontinu\w* (of )?(the )?(development|program)|"
    r"(withdr[ae]w|withdrawal of|lack of) (of )?(support|funding)", re.I)

# Negated mentions ("not based on safety concerns", "No Safety or Efficacy Concerns")
# are removed up to the end of the clause before the safety/efficacy rules run.
NEG_SAFETY = re.compile(
    r"\b(?:not|no|without|unrelated to|neither|nor|independent of)\b[^.;,]{0,40}?"
    r"\b(?:safety|adverse|toxic\w*|side[- ]effects?|tolerab\w*)[^.;,]*", re.I)
NEG_EFFICACY = re.compile(
    r"\b(?:not (?:based on|due to|related to|because of|for)|unrelated to)\b[^.;,]{0,25}?efficac[^.;,]*", re.I)

ACCRUAL_WORD = re.compile(r"recruit|accrual|accru|enrol|enrolment|enroll|under-?enrol", re.I)
DIFFICULTY = re.compile(
    r"slow|\blow\b|poor|insufficient|inadequate|lack of|difficult|fail(ed|ure)? to|unable|"
    r"not enough|too few|\bfew\b|limited|challeng|unsuccessful|\bissues?\b|\bproblems?\b|"
    r"shortfall|not (been )?(met|reached|achieved)|did not (enrol|enroll|recruit)|"
    r"unable to|low[- ]enrol|under-?enrol|\bno (patients?|participants?|subjects?)\b", re.I)
NO_ONE_ENROLLED = re.compile(
    r"\bno (patients?|participants?|subjects?|one)\b.{0,30}(enrol|enroll|recruit)", re.I)


def classify_why_stopped(text):
    """Return one of REASONS for a whyStopped string."""
    if not isinstance(text, str) or not text.strip():
        return "other_unspecified"
    clean = NEG_EFFICACY.sub(" ", NEG_SAFETY.sub(" ", text))
    if SAFETY.search(clean):
        return "safety"
    if EFFICACY.search(clean):
        return "efficacy_futility"
    if SPONSOR.search(text):
        return "sponsor_business"
    if ACCRUAL_WORD.search(text) and (DIFFICULTY.search(text) or NO_ONE_ENROLLED.search(text)):
        return "low_accrual"
    return "other_unspecified"


def make_labels(status, why_stopped):
    """terminated (1/0) and terminated_low_accrual (1/0) plus the reason class."""
    terminated = int(status == "TERMINATED")
    reason = classify_why_stopped(why_stopped) if terminated else None
    return {
        "terminated": terminated,
        "terminated_low_accrual": int(terminated and reason == "low_accrual"),
        "stop_reason": reason,
    }
