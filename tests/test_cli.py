from pathlib import Path

import pytest
from docx import Document as WordDocument
from PIL import Image

from ocr_to_docs.cli import build_argument_parser, default_output, process
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


def test_process_combines_a_folder_into_one_word_document(tmp_path: Path) -> None:
    folder = tmp_path / "document-1-files"
    folder.mkdir()
    Image.new("RGB", (10, 10), "red").save(folder / "02.png")
    Image.new("RGB", (10, 10), "blue").save(folder / "01.png")

    class EveryPage:
        def parse(self, document: Document) -> Document:
            for page in document.pages:
                page.blocks = [Block(BlockType.TEXT, f"page {page.number}")]
            return document

    output = tmp_path / "doc_for_edit.docx"
    process(folder, output, "docx", parser=EveryPage())

    word = WordDocument(output)
    assert [paragraph.text for paragraph in word.paragraphs if paragraph.text] == [
        "page 1",
        "page 2",
    ]


@pytest.mark.parametrize("output_format", ["md", "docx", "pdf"])
def test_process_never_overwrites_its_input(tmp_path: Path, output_format: str) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (10, 10), "white").save(source)

    with pytest.raises(ValueError, match="must differ"):
        process(source, source, output_format, parser=FakeParser())


def test_cli_defaults_vlm_to_lmstudio() -> None:
    arguments = build_argument_parser().parse_args(["note.png"])
    assert arguments.vlm == "lmstudio"


def test_cli_accepts_local_vlm() -> None:
    arguments = build_argument_parser().parse_args(["note.png", "--vlm", "local"])
    assert arguments.vlm == "local"
