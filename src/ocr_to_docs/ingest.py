from pathlib import Path

import pymupdf
from PIL import Image, ImageOps, ImageSequence

from ocr_to_docs.models import Block, BlockType, BoundingBox, Document, Page

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def ingest(source: Path, work_dir: Path) -> Document:
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Input file does not exist: {source}")
    if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Unsupported input type {source.suffix!r}; expected one of: {supported}")

    work_dir.mkdir(parents=True, exist_ok=True)
    pages = (
        _ingest_pdf(source, work_dir)
        if source.suffix.lower() == ".pdf"
        else _ingest_images(source, work_dir)
    )
    return Document(source=str(source), pages=pages)


def _ingest_images(source: Path, work_dir: Path) -> list[Page]:
    pages = []
    with Image.open(source) as image:
        dpi_x, dpi_y = _valid_dpi(image.info.get("dpi", (72, 72)))
        if image.getexif().get(274, 1) in {5, 6, 7, 8}:
            dpi_x, dpi_y = dpi_y, dpi_x
        for index, frame in enumerate(ImageSequence.Iterator(image), start=1):
            output = work_dir / f"page-{index}.png"
            normalized = ImageOps.exif_transpose(frame.copy()).convert("RGB")
            normalized.save(output)
            width, height = normalized.size
            pages.append(
                Page(
                    number=index,
                    width=width,
                    height=height,
                    source_image=output,
                    physical_width=width * 72 / dpi_x,
                    physical_height=height * 72 / dpi_y,
                )
            )
    return pages


def _ingest_pdf(source: Path, work_dir: Path) -> list[Page]:
    pages: list[Page] = []
    with pymupdf.open(source) as pdf:
        for index, pdf_page in enumerate(pdf):
            text_blocks = [
                Block(
                    kind=BlockType.TEXT,
                    text=str(raw[4]).strip(),
                    bbox=BoundingBox(*map(float, raw[:4])),
                )
                for raw in pdf_page.get_text("blocks")
                if str(raw[4]).strip()
            ]
            page_area = pdf_page.rect.width * pdf_page.rect.height
            largest_image_coverage = max(
                (
                    pymupdf.Rect(image["bbox"]).get_area() / page_area
                    for image in pdf_page.get_image_info()
                ),
                default=0.0,
            )
            native_characters = sum(len(block.text) for block in text_blocks)
            scan_with_stray_text = largest_image_coverage >= 0.75 and native_characters < 100
            if text_blocks and not scan_with_stray_text:
                pages.append(
                    Page(
                        number=index + 1,
                        width=pdf_page.rect.width,
                        height=pdf_page.rect.height,
                        blocks=text_blocks,
                        source_pdf=source,
                        native_text=True,
                        physical_width=pdf_page.rect.width,
                        physical_height=pdf_page.rect.height,
                    )
                )
                continue

            output = work_dir / f"page-{index + 1}.png"
            pixmap = pdf_page.get_pixmap(dpi=200, alpha=False)
            pixmap.save(output)
            pages.append(
                Page(
                    number=index + 1,
                    width=pixmap.width,
                    height=pixmap.height,
                    source_image=output,
                    source_pdf=source,
                    physical_width=pdf_page.rect.width,
                    physical_height=pdf_page.rect.height,
                )
            )
    return pages


def _valid_dpi(value: object) -> tuple[float, float]:
    if not isinstance(value, (tuple, list)) or len(value) < 2:
        return 72.0, 72.0
    try:
        dpi_x, dpi_y = float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return 72.0, 72.0
    return (dpi_x if dpi_x > 0 else 72.0, dpi_y if dpi_y > 0 else 72.0)
