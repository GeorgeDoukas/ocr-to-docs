from __future__ import annotations

import argparse
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from time import perf_counter
from typing import Protocol

from ocr_to_docs import __version__
from ocr_to_docs.exporters import export_docx, export_markdown, export_searchable_pdf
from ocr_to_docs.ingest import ingest
from ocr_to_docs.models import Document
from ocr_to_docs.parser import PaddleVLParser


class Parser(Protocol):
    def parse(self, document: Document) -> Document: ...


EXPORTERS = {
    "md": export_markdown,
    "docx": export_docx,
    "pdf": export_searchable_pdf,
}


def default_output(source: Path, output_format: str) -> Path:
    return source.with_name(f"{source.stem}.ocr.{output_format}")


def process(
    source: Path,
    output: Path,
    output_format: str,
    *,
    cpu_threads: int | None = None,
    parser: Parser | None = None,
    progress: Callable[[str], None] | None = None,
) -> float:
    if output_format not in EXPORTERS:
        raise ValueError(f"Unsupported output format: {output_format}")
    if source.resolve() == output.resolve():
        raise ValueError("Output path must differ from the input path")

    started = perf_counter()
    notify = progress or (lambda _message: None)
    with tempfile.TemporaryDirectory(prefix="ocr-to-docs-") as temporary:
        notify(f"Loading {source}")
        document = ingest(source, Path(temporary))
        ocr_pages = sum(not page.native_text for page in document.pages)
        if ocr_pages:
            notify(f"Parsing {ocr_pages} page(s) with PaddleOCR-VL-1.6 on CPU")
        document = (parser or PaddleVLParser(cpu_threads=cpu_threads)).parse(document)
        EXPORTERS[output_format](document, output)

    elapsed = perf_counter() - started
    notify(f"Wrote {output} ({len(document.pages)} page(s) in {elapsed:.2f}s)")
    return elapsed


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ocr-to-docs",
        description="Convert local PDFs and images to searchable PDF, DOCX, or Markdown.",
    )
    parser.add_argument("input", type=Path, help="PDF, PNG, JPEG, or TIFF input")
    parser.add_argument("--format", choices=EXPORTERS, default="md", help="Output format")
    parser.add_argument("-o", "--output", type=Path, help="Output path")
    parser.add_argument("--cpu-threads", type=int, help="PaddleOCR CPU worker threads")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argument_parser = build_argument_parser()
    arguments = argument_parser.parse_args(argv)
    if arguments.cpu_threads is not None and arguments.cpu_threads < 1:
        argument_parser.error("--cpu-threads must be at least 1")

    output = arguments.output or default_output(arguments.input, arguments.format)
    try:
        process(
            arguments.input,
            output,
            arguments.format,
            cpu_threads=arguments.cpu_threads,
            progress=print,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        argument_parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
