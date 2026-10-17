from pathlib import Path

import pytest
from PIL import Image

from ocr_to_docs.cli import default_output, process
from ocr_to_docs.models import Block, BlockType, Document


class FakeParser:
    def parse(self, document: Document) -> Document:
        document.pages[0].blocks = [Block(BlockType.TEXT, "Hello κόσμε")]
        return document


def test_process_converts_an_image_to_markdown(tmp_path: Path) -> None:
    source = tmp_path / "note.png"
    output = tmp_path / "note.md"
    Image.new("RGB", (100, 50), "white").save(source)

    elapsed = process(source, output, "md", parser=FakeParser())

    assert output.read_text(encoding="utf-8") == "Hello κόσμε\n"
    assert elapsed >= 0


def test_default_pdf_output_does_not_overwrite_input() -> None:
    assert default_output(Path("scan.pdf"), "pdf") == Path("scan.ocr.pdf")


@pytest.mark.parametrize("output_format", ["md", "docx", "pdf"])
def test_process_never_overwrites_its_input(tmp_path: Path, output_format: str) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (10, 10), "white").save(source)

    with pytest.raises(ValueError, match="must differ"):
        process(source, source, output_format, parser=FakeParser())
