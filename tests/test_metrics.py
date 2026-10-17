from ocr_to_docs.metrics import character_error_rate, word_error_rate


def test_character_error_rate_counts_unicode_characters() -> None:
    assert character_error_rate("Καλημέρα", "Καλημερα") == 1 / 8


def test_word_error_rate_counts_word_substitutions() -> None:
    assert word_error_rate("the quick fox", "the slow fox") == 1 / 3


def test_error_rate_handles_empty_reference() -> None:
    assert character_error_rate("", "") == 0.0
    assert character_error_rate("", "text") == 1.0
