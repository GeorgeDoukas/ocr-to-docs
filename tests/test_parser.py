from pathlib import Path
from typing import ClassVar

from PIL import Image

from ocr_to_docs.models import Document, Page
from ocr_to_docs.parser import PaddleVLParser


class FakeResult:
    json: ClassVar = {
        "res": {
            "parsing_res_list": [
                {
                    "block_bbox": [1, 2, 90, 20],
                    "block_label": "doc_title",
                    "block_content": "Annual report",
                },
                {
                    "block_bbox": [1, 30, 90, 80],
                    "block_label": "table",
                    "block_content": "| Year | Sales |\n|---|---|\n| 2026 | 10 |",
                },
                {
                    "block_bbox": [1, 90, 90, 140],
                    "block_label": "chart",
                    "block_content": "2026: 10",
                },
            ]
        }
    }


class FakePipeline:
    def predict_iter(self, _path: str):
        yield FakeResult()


def test_parser_normalizes_paddle_blocks_and_crops_chart(tmp_path: Path) -> None:
    image = tmp_path / "page.png"
    Image.new("RGB", (100, 150), "white").save(image)
    document = Document(
        source=str(image),
        pages=[Page(1, 100, 150, source_image=image)],
    )

    parsed = PaddleVLParser(pipeline=FakePipeline()).parse(document)

    assert [block.kind for block in parsed.pages[0].blocks] == ["heading", "table", "chart"]
    assert parsed.pages[0].blocks[2].image_path is not None
    assert parsed.pages[0].blocks[2].image_path.exists()


def test_parser_skips_pages_with_native_text() -> None:
    document = Document(
        source="native.pdf",
        pages=[Page(1, 100, 100, native_text=True)],
    )

    assert PaddleVLParser(pipeline=FakePipeline()).parse(document) is document
