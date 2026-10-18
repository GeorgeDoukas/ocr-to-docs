import time
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


def test_parser_reports_page_progress_while_recognition_is_running(tmp_path: Path) -> None:
    image = tmp_path / "page.png"
    Image.new("RGB", (100, 40), "white").save(image)
    document = Document(source=str(image), pages=[Page(1, 100, 40, source_image=image)])
    messages: list[str] = []

    class SlowPipeline:
        def predict_iter(self, _path: str):
            time.sleep(0.2)
            yield FakeResult()

    PaddleVLParser(
        pipeline=SlowPipeline(),
        progress=messages.append,
        heartbeat_seconds=0.05,
    ).parse(document)

    assert "Recognizing page 1 (1/1)" in messages
    assert any(message.startswith("Still recognizing page 1") for message in messages)
    assert any(message.startswith("Finished page 1 in") for message in messages)


def test_parser_skips_pages_with_native_text() -> None:
    document = Document(
        source="native.pdf",
        pages=[Page(1, 100, 100, native_text=True)],
    )

    assert PaddleVLParser(pipeline=FakePipeline()).parse(document) is document


def test_pipeline_kwargs_default_to_lmstudio() -> None:
    kwargs = PaddleVLParser(cpu_threads=4)._pipeline_kwargs()

    assert kwargs["vl_rec_backend"] == "llama-cpp-server"
    assert kwargs["vl_rec_server_url"] == "http://127.0.0.1:1234/v1"
    assert kwargs["vl_rec_api_model_name"] == "paddleocr-vl-1.6"
    assert kwargs["cpu_threads"] == 4


def test_pipeline_kwargs_local_skips_server_backend() -> None:
    kwargs = PaddleVLParser(vlm="local", cpu_threads=2)._pipeline_kwargs()

    assert "vl_rec_backend" not in kwargs
    assert "vl_rec_server_url" not in kwargs
    assert kwargs["cpu_threads"] == 2
