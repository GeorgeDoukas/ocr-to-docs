from dataclasses import dataclass

from ocr_to_docs.metrics import character_error_rate, word_error_rate


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    samples: int
    character_error_rate: float
    word_error_rate: float


def evaluate_samples(samples: list[tuple[str, str]]) -> BenchmarkResult:
    if not samples:
        return BenchmarkResult(0, 0.0, 0.0)

    return BenchmarkResult(
        samples=len(samples),
        character_error_rate=sum(character_error_rate(*sample) for sample in samples)
        / len(samples),
        word_error_rate=sum(word_error_rate(*sample) for sample in samples) / len(samples),
    )
