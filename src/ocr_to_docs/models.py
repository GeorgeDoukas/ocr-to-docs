from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class BlockType(StrEnum):
    TEXT = "text"
    HEADING = "heading"
    TABLE = "table"
    CHART = "chart"
    FORMULA = "formula"
    IMAGE = "image"
    LIST = "list"


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        if self.x0 > self.x1 or self.y0 > self.y1:
            raise ValueError("Bounding-box coordinates must be ordered")


@dataclass(slots=True)
class Block:
    kind: BlockType
    text: str = ""
    bbox: BoundingBox | None = None
    confidence: float | None = None
    html: str | None = None
    image_path: Path | None = None


@dataclass(slots=True)
class Page:
    number: int
    width: float
    height: float
    blocks: list[Block] = field(default_factory=list)
    source_image: Path | None = None
    source_pdf: Path | None = None
    native_text: bool = False
    physical_width: float | None = None
    physical_height: float | None = None

    @property
    def plain_text(self) -> str:
        return "\n".join(block.text for block in self.blocks if block.text)


@dataclass(slots=True)
class Document:
    source: str
    pages: list[Page] = field(default_factory=list)

    @property
    def plain_text(self) -> str:
        return "\n\n".join(page.plain_text for page in self.pages if page.plain_text)
