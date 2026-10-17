from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from ocr_to_docs.ingest import ingest


def test_ingest_uses_native_pdf_text_without_rendering(tmp_path: Path) -> None:
    source = tmp_path / "native.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page(width=300, height=200)
    page.insert_text((20, 40), "Native English text")
    pdf.save(source)
    pdf.close()

    document = ingest(source, tmp_path / "work")

    assert document.pages[0].native_text is True
    assert document.pages[0].source_image is None
    assert "Native English text" in document.plain_text


def test_ingest_normalizes_an_image_for_ocr(tmp_path: Path) -> None:
    source = tmp_path / "note.png"
    Image.new("RGB", (80, 40), "white").save(source)

    document = ingest(source, tmp_path / "work")

    page = document.pages[0]
    assert (page.width, page.height) == (80, 40)
    assert page.source_image is not None
    assert page.source_image.exists()


def test_ingest_preserves_all_tiff_frames(tmp_path: Path) -> None:
    source = tmp_path / "notes.tiff"
    frames = [Image.new("RGB", (80, 40), color) for color in ("white", "gray")]
    frames[0].save(source, save_all=True, append_images=frames[1:])

    document = ingest(source, tmp_path / "work")

    assert len(document.pages) == 2
    assert all(page.source_image and page.source_image.exists() for page in document.pages)


def test_ingest_ocr_processes_pdf_page_with_large_scan_and_stray_text(tmp_path: Path) -> None:
    scan = tmp_path / "scan.png"
    Image.new("RGB", (200, 200), "white").save(scan)
    source = tmp_path / "mixed.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page(width=200, height=200)
    page.insert_image(page.rect, filename=str(scan))
    page.insert_text((10, 20), "watermark")
    pdf.save(source)
    pdf.close()

    document = ingest(source, tmp_path / "work")

    assert document.pages[0].native_text is False
    assert document.pages[0].source_image is not None


def test_ingest_keeps_native_text_on_page_with_regular_figure(tmp_path: Path) -> None:
    figure = tmp_path / "figure.png"
    Image.new("RGB", (200, 200), "white").save(figure)
    source = tmp_path / "illustrated.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page(width=300, height=400)
    page.insert_image(pymupdf.Rect(0, 0, 200, 200), filename=str(figure))
    page.insert_text(
        (10, 250),
        "This is a substantial native paragraph that must remain selectable in the output.",
    )
    pdf.save(source)
    pdf.close()

    document = ingest(source, tmp_path / "work")

    assert document.pages[0].native_text is True
    assert "substantial native paragraph" in document.plain_text


def test_ingest_swaps_anisotropic_dpi_when_exif_rotates_image(tmp_path: Path) -> None:
    source = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (300, 600), "white").save(
        source,
        dpi=(300, 150),
        exif=exif,
    )

    document = ingest(source, tmp_path / "work")

    page = document.pages[0]
    assert (page.width, page.height) == (600, 300)
    assert page.physical_width == pytest.approx(288, abs=1)
    assert page.physical_height == pytest.approx(72, abs=1)
