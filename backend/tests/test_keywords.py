from app.keywords import is_candidate, matched_keywords


def test_greek_with_accents_and_inflection():
    assert is_candidate("Νέα ένταση με την Τουρκία στο Αιγαίο")
    assert is_candidate("Ο Ερντογάν απείλησε ξανά")
    assert is_candidate("Τουρκικά αλιευτικά στα χωρικά ύδατα")


def test_hebrew_with_prefix():
    assert is_candidate("ארדואן תקף את ישראל")
    assert is_candidate("השגריר בטורקיה זומן לשיחה")


def test_english():
    assert "erdogan" in matched_keywords("Erdoğan meets Mitsotakis")
    assert is_candidate("Türkiye signs new deal")


def test_unrelated_text_is_not_candidate():
    assert not is_candidate("Νέα μέτρα για την ακρίβεια", "ממשלה חדשה בירושלים", "Weather in Athens")
