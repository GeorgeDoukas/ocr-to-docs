from pathlib import Path

import pymupdf

from ocr_to_docs.models import Document, Page


def export_searchable_pdf(document: Document, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    source = Path(document.source)
    if source.suffix.lower() == ".pdf":
        if source.resolve() == output.resolve():
            raise ValueError("Searchable PDF output must differ from the input PDF")
        pdf = pymupdf.open(source)
    else:
        pdf = pymupdf.open()
        for page in document.pages:
            pdf_page = pdf.new_page(
                width=page.physical_width or page.width,
                height=page.physical_height or page.height,
            )
            if page.source_image:
                pdf_page.insert_image(pdf_page.rect, filename=str(page.source_image))

    try:
        for page_index, source_page in enumerate(document.pages):
            if source_page.native_text:
                continue
            _overlay_text(pdf[page_index], source_page)
        pdf.save(output, garbage=4, deflate=True)
    finally:
        pdf.close()


def _overlay_text(pdf_page: pymupdf.Page, source_page: Page) -> None:
    font = pymupdf.Font("notos")
    pdf_page.insert_font(fontname="ocrfont", fontbuffer=font.buffer)
    scale_x = pdf_page.rect.width / source_page.width
    scale_y = pdf_page.rect.height / source_page.height

    for block in source_page.blocks:
        if not block.text or block.bbox is None:
            continue
        box = block.bbox
        rect = pymupdf.Rect(
            box.x0 * scale_x,
            box.y0 * scale_y,
            box.x1 * scale_x,
            box.y1 * scale_y,
        )
        lines = block.text.splitlines() or [block.text]
        line_height = rect.height / len(lines)
        for line_index, line in enumerate(lines):
            if not line:
                continue
            width_at_one_point = max(font.text_length(line, fontsize=1), 1)
            font_size = max(1.0, min(14.0, line_height * 0.8, rect.width / width_at_one_point))
            pdf_page.insert_text(
                (rect.x0, rect.y0 + (line_index + 0.8) * line_height),
                line,
                fontname="ocrfont",
                fontsize=font_size,
                render_mode=3,
                overlay=True,
            )
