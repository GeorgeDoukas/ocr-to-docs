from __future__ import annotations

import argparse
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from time import perf_counter
from typing import Protocol

from ocr_to_docs import __version__
from ocr_to_docs.exporters import export_docx, export_markdown, export_searchable_pdf
from ocr_to_docs.ingest import collect_inputs, ingest_inputs
from ocr_to_docs.models import Document
from ocr_to_docs.parser import PaddleVLParser, VlmBackend


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
    source: Path | Sequence[Path],
    output: Path,
    output_format: str,
    *,
    cpu_threads: int | None = None,
    vlm: VlmBackend = "lmstudio",
    parser: Parser | None = None,
    progress: Callable[[str], None] | None = None,
) -> float:
    sources = [source] if isinstance(source, Path) else list(source)
    if output_format not in EXPORTERS:
        raise ValueError(f"Unsupported output format: {output_format}")
    files = collect_inputs(sources)
    if output.resolve() in {path.resolve() for path in files}:
        raise ValueError("Output path must differ from the input path")

    started = perf_counter()
    notify = progress or (lambda _message: None)
    with tempfile.TemporaryDirectory(prefix="ocr-to-docs-") as temporary:
        notify(f"Loading {len(files)} file(s)")
        document = ingest_inputs(sources, Path(temporary))
        ocr_pages = sum(not page.native_text for page in document.pages)
        if ocr_pages:
            where = "via LM Studio" if vlm == "lmstudio" else "on CPU"
            notify(f"Parsing {ocr_pages} page(s) with PaddleOCR-VL-1.6 {where}")
        document = (
            parser or PaddleVLParser(cpu_threads=cpu_threads, vlm=vlm, progress=notify)
        ).parse(document)
        EXPORTERS[output_format](document, output)

    elapsed = perf_counter() - started
    notify(f"Wrote {output} ({len(document.pages)} page(s) in {elapsed:.2f}s)")
    return elapsed


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ocr-to-docs",
        description="Convert local PDFs and images to searchable PDF, DOCX, or Markdown.",
    )
    parser.add_argument(
        "input",
        nargs="+",
        type=Path,
        help="PDF, PNG, JPEG, or TIFF files, or a folder containing them",
    )
    parser.add_argument("--format", choices=EXPORTERS, default="md", help="Output format")
    parser.add_argument("-o", "--output", type=Path, help="Output path")
    parser.add_argument("--cpu-threads", type=int, help="PaddleOCR CPU worker threads")
    parser.add_argument(
        "--vlm",
        choices=("lmstudio", "local"),
        default="lmstudio",
        help="Where to run VLM recognition (default: lmstudio)",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argument_parser = build_argument_parser()
    arguments = argument_parser.parse_args(argv)
    if arguments.cpu_threads is not None and arguments.cpu_threads < 1:
        argument_parser.error("--cpu-threads must be at least 1")

    output = arguments.output or default_output(arguments.input[0], arguments.format)
    try:
        process(
            arguments.input,
            output,
            arguments.format,
            cpu_threads=arguments.cpu_threads,
            vlm=arguments.vlm,
            progress=print,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        argument_parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
