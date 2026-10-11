from labels import classify_why_stopped as c, make_labels


def test_worked_examples():
    assert c("Enrollment was stopped after the sponsor's decision not to pursue the development of X") == "sponsor_business"
    assert c("Interim analysis was performed; it did not show evidence of treatment benefit") == "efficacy_futility"
    assert c("lack of study recruitment") == "low_accrual"
    assert c("Slow accrual") == "low_accrual"
    assert c("") == "other_unspecified" and c(None) == "other_unspecified"


def test_bare_words_do_not_match_accrual():
    for s in ["patients", "participants", "low", "slow", "enrollment", "Low dose"]:
        assert c(s) != "low_accrual"


def test_negation_and_order():
    assert c("Terminated not based on safety concerns, but due to insufficient efficacy.") == "efficacy_futility"
    assert c("Business Decision; No Safety or Efficacy Concerns.") == "sponsor_business"
    assert c("Low enrollment due to safety concerns") == "safety"  # safety outranks accrual
    assert c("pharmaceutical company decision") == "sponsor_business"  # 'harm' not matched inside 'pharma'


def test_make_labels():
    assert make_labels("COMPLETED", "") == {"terminated": 0, "terminated_low_accrual": 0, "stop_reason": None}
    assert make_labels("TERMINATED", "Slow accrual")["terminated_low_accrual"] == 1
    assert make_labels("TERMINATED", "Sponsor decision")["terminated_low_accrual"] == 0
