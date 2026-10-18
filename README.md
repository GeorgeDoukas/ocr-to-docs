# OCR-to-Docs

OCR-to-Docs is a local, CPU-first command-line tool that converts PDFs, scans,
images, and handwritten notes into searchable PDF, editable Word, or Markdown.
It uses PaddleOCR-VL-1.6-0.9B for multilingual document parsing.

## Features

- Processes documents locally without uploading their contents.
- Accepts PDF, PNG, JPEG, and TIFF files.
- Combines several images, or every supported file in a folder, into one document.
- Recognizes multilingual text, including English and Greek.
- Detects headings, reading order, tables, formulas, images, and charts.
- Preserves native PDF text instead of OCR-processing it again.
- Enables orientation correction and document unwarping for scanned pages.
- Converts detected tables into Markdown or native Word tables.
- Preserves chart images and includes PaddleOCR's extracted chart content.
- Creates searchable PDFs by placing an invisible Unicode text layer over each scan.
- Reports each page as it starts and finishes, plus an elapsed-time update every 15 seconds during recognition.

## Requirements

- Python 3.11 or 3.12
- [uv](https://docs.astral.sh/uv/)
- A 64-bit CPU

The first OCR run downloads PaddleOCR model weights. The 0.9B VLM prioritizes
document quality over speed and needs substantially more time and memory than a
mobile OCR model.

## Installation

```powershell
py -m pip install uv
uv sync
```

`uv sync` installs the CPU build of PaddlePaddle, PaddleOCR's document parser,
the exporters, pytest, and Ruff from the checked-in `uv.lock`.

## Usage

Markdown:

```powershell
uv run ocr-to-docs .\scan.pdf --format md
```

Word:

```powershell
uv run ocr-to-docs .\notes.jpg --format docx --output .\notes.docx
```

Several photos, in the order given:

```powershell
uv run ocr-to-docs .\01.jpg .\02.jpg .\03.png --format docx --output .\doc_for_edit.docx
```

A folder of photos. Files are ordered by name, so `page-2` comes before `page-10`:

```powershell
uv run ocr-to-docs .\document-1-files --format docx --output .\doc_for_edit.docx
```

Only PDF, PNG, JPEG, and TIFF files directly inside the folder are included. Name the photos in page order before running the command. The same inputs work with `--format pdf` or `--format md`.

Searchable PDF with a fixed CPU thread count:

```powershell
uv run ocr-to-docs .\scan.tiff --format pdf --cpu-threads 8
```

By default, layout runs locally and VLM recognition goes through LM Studio's
OpenAI-compatible server at `http://127.0.0.1:1234/v1` with model
`paddleocr-vl-1.6`. Load that model in LM Studio, start the local server, then
run the CLI as usual. To force the old in-process CPU VLM instead:

```powershell
uv run ocr-to-docs .\scan.pdf --format md --vlm local
```

When `--output` is omitted, the command writes `<input-name>.ocr.<format>` next
to the input. Run `uv run ocr-to-docs --help` for all options.

## Output behavior

### Markdown

Headings, text, formulas, and tables are written in reading order. Extracted
chart and image crops are copied into a sibling `<output-name>_assets` folder
and referenced with relative links.

### Word

Text remains editable, detected headings use Word heading styles, Markdown
tables become native Word tables, and charts/images are embedded. DOCX output
is semantic rather than a pixel-perfect copy of the source.

### Searchable PDF

The original PDF page or source image remains visible. OCR text is added as an
invisible, positioned Unicode layer, so Greek and English text can be searched
and copied while page appearance remains unchanged.

## Model and language notes

The default parser is `PaddleOCR-VL-1.6-0.9B`, selected through PaddleOCR's
official page-level `v1.6` pipeline. Layout analysis still runs locally;
VLM recognition defaults to LM Studio (`--vlm lmstudio`). Chart recognition,
image-block OCR, orientation classification, unwarping, and Markdown block
formatting are enabled.

Paddle describes the model as multilingual, but does not publish a dedicated
Greek handwriting score for version 1.6. Accuracy depends on handwriting,
capture quality, page geometry, and chart complexity. Validate important
workloads with representative documents rather than treating model confidence
as a correctness guarantee.

Chart understanding does not recreate an editable chart. The exporters retain
the chart crop and include extracted data or descriptions when PaddleOCR
provides them.

## Quality and performance checks

The test suite covers Unicode text, Greek/English error metrics, native PDF
text bypass, image normalization, Paddle result normalization, tables, charts,
all three exporters, and the CLI conversion path.

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The reusable benchmark functions in `ocr_to_docs.benchmark` calculate character
error rate (CER) and word error rate (WER) from reference/hypothesis pairs.
No model-accuracy number is claimed by this repository until a representative,
versioned Greek/English document corpus has been measured. The CLI prints
wall-clock seconds and pages processed so results can be compared on the target
CPU.

## Known limitations

- Local `--vlm local` CPU inference with a 0.9B VLM is slow, especially for
  multi-page scans. Prefer the default LM Studio backend when available.
- Exact visual reconstruction is only provided by searchable PDF, not DOCX.
- Tables with unusual spanning cells may require manual correction.
- Handwriting quality varies significantly by writer.
- Password-protected or damaged PDFs are not supported.
