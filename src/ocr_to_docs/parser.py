from __future__ import annotations

import os
import threading
from collections.abc import Callable, Iterable, Mapping
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, Protocol

from PIL import Image

from ocr_to_docs.models import Block, BlockType, BoundingBox, Document, Page

VlmBackend = Literal["lmstudio", "local"]

DEFAULT_LMSTUDIO_URL = "http://127.0.0.1:1234/v1"
DEFAULT_LMSTUDIO_MODEL = "paddleocr-vl-1.6"


class Pipeline(Protocol):
    def predict_iter(self, input_path: str) -> Iterable[Any]: ...


LABEL_TYPES = {
    "doc_title": BlockType.HEADING,
    "paragraph_title": BlockType.HEADING,
    "table": BlockType.TABLE,
    "chart": BlockType.CHART,
    "formula": BlockType.FORMULA,
    "image": BlockType.IMAGE,
    "list": BlockType.LIST,
}


class PaddleVLParser:
    def __init__(
        self,
        pipeline: Pipeline | None = None,
        cpu_threads: int | None = None,
        progress: Callable[[str], None] | None = None,
        heartbeat_seconds: float = 15,
        vlm: VlmBackend = "lmstudio",
        vlm_url: str = DEFAULT_LMSTUDIO_URL,
        vlm_model: str = DEFAULT_LMSTUDIO_MODEL,
    ) -> None:
        self._pipeline = pipeline
        self._cpu_threads = cpu_threads or min(os.cpu_count() or 1, 10)
        self._progress = progress
        self._heartbeat_seconds = heartbeat_seconds
        self._vlm = vlm
        self._vlm_url = vlm_url
        self._vlm_model = vlm_model

    def parse(self, document: Document) -> Document:
        pages_to_parse = [page for page in document.pages if not page.native_text]
        if not pages_to_parse:
            return document

        pipeline = self._pipeline or self._create_pipeline()
        total = len(pages_to_parse)
        for index, page in enumerate(pages_to_parse, start=1):
            if page.source_image is None:
                raise ValueError(f"Page {page.number} has no image to parse")
            label = f"page {page.number} ({index}/{total})"
            self._notify(f"Recognizing {label}")
            started = perf_counter()
            with _heartbeat(self._progress, label, self._heartbeat_seconds):
                results = iter(pipeline.predict_iter(str(page.source_image)))
                try:
                    page.blocks = _blocks_from_result(next(results), page)
                except StopIteration as error:
                    message = f"PaddleOCR returned no result for page {page.number}"
                    raise RuntimeError(message) from error
            self._notify(f"Finished page {page.number} in {perf_counter() - started:.0f}s")
        return document

    def _notify(self, message: str) -> None:
        if self._progress is not None:
            self._progress(message)

    def _pipeline_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "pipeline_version": "v1.6",
            "device": "cpu",
            "cpu_threads": self._cpu_threads,
            "use_doc_orientation_classify": True,
            "use_doc_unwarping": True,
            "use_layout_detection": True,
            "use_chart_recognition": True,
            "use_ocr_for_image_block": True,
            "format_block_content": True,
        }
        if self._vlm == "lmstudio":
            kwargs.update(
                vl_rec_backend="llama-cpp-server",
                vl_rec_server_url=self._vlm_url,
                vl_rec_api_model_name=self._vlm_model,
            )
        return kwargs

    def _create_pipeline(self) -> Pipeline:
        try:
            from paddleocr import PaddleOCRVL
        except ImportError as error:
            raise RuntimeError(
                "PaddleOCR is not installed. Run `uv sync` before processing documents."
            ) from error

        return PaddleOCRVL(**self._pipeline_kwargs())


@contextmanager
def _heartbeat(
    progress: Callable[[str], None] | None,
    label: str,
    interval: float,
) -> Any:
    if progress is None:
        yield
        return

    stop = threading.Event()
    started = perf_counter()

    def report() -> None:
        while not stop.wait(interval):
            elapsed = perf_counter() - started
            progress(f"Still recognizing {label} ({elapsed:.0f}s)")

    thread = threading.Thread(target=report, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=1)


def _blocks_from_result(result: Any, page: Page) -> list[Block]:
    payload = result.json
    if callable(payload):
        payload = payload()
    if not isinstance(payload, Mapping):
        raise RuntimeError("PaddleOCR returned an unexpected result")
    data = payload.get("res", payload)
    raw_blocks = data.get("parsing_res_list", [])

    blocks = []
    for index, raw in enumerate(raw_blocks):
        if not isinstance(raw, Mapping):
            continue
        bbox = _bounding_box(raw.get("block_bbox"))
        kind = LABEL_TYPES.get(str(raw.get("block_label", "")).lower(), BlockType.TEXT)
        image_path = _crop_visual(page, bbox, kind, index)
        blocks.append(
            Block(
                kind=kind,
                text=str(raw.get("block_content", "")).strip(),
                bbox=bbox,
                image_path=image_path,
            )
        )
    return blocks


def _bounding_box(value: Any) -> BoundingBox | None:
    if value is None:
        return None
    coordinates = [float(number) for number in value]
    if len(coordinates) == 4:
        return BoundingBox(*coordinates)
    if len(coordinates) >= 8 and len(coordinates) % 2 == 0:
        return BoundingBox(
            min(coordinates[::2]),
            min(coordinates[1::2]),
            max(coordinates[::2]),
            max(coordinates[1::2]),
        )
    return None


def _crop_visual(page: Page, bbox: BoundingBox | None, kind: BlockType, index: int) -> Path | None:
    if kind not in {BlockType.CHART, BlockType.IMAGE} or bbox is None or page.source_image is None:
        return None

    output = page.source_image.with_name(f"page-{page.number}-{kind}-{index}.png")
    with Image.open(page.source_image) as image:
        image.crop((bbox.x0, bbox.y0, bbox.x1, bbox.y1)).save(output)
    return output
