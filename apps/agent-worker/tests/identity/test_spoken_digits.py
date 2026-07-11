from tasks.identity_verification_task import normalize_spoken_digits


def test_numeric_digits():
    assert normalize_spoken_digits("4087") == "4087"


def test_french_spoken_digits():
    assert normalize_spoken_digits(
        "quatre zéro huit sept"
    ) == "4087"


def test_english_spoken_digits():
    assert normalize_spoken_digits(
        "four zero eight seven"
    ) == "4087"


def test_arabic_spoken_digits():
    assert normalize_spoken_digits(
        "أربعة صفر ثمانية سبعة"
    ) == "4087"


def test_rejects_three_digits():
    assert normalize_spoken_digits("quatre zéro huit") is None
