from ocr_to_docs.benchmark import evaluate_samples


def test_evaluate_samples_reports_average_error_rates() -> None:
    result = evaluate_samples(
        [
            ("Greek", "Greek"),
            ("hello world", "hello there"),
        ]
    )

    assert result.samples == 2
    assert result.character_error_rate > 0
    assert result.word_error_rate == 0.25
