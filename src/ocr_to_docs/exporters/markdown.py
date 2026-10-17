import shutil
from pathlib import Path

from ocr_to_docs.models import Block, BlockType, Document


def export_markdown(document: Document, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    assets = output.with_name(f"{output.stem}_assets")
    pages = [
        "\n\n".join(_render_block(block, assets) for block in page.blocks).strip()
        for page in document.pages
    ]
    output.write_text("\n\n---\n\n".join(filter(None, pages)) + "\n", encoding="utf-8")


def _render_block(block: Block, assets: Path) -> str:
    if block.kind == BlockType.HEADING:
        return f"# {block.text}"
    if block.kind == BlockType.FORMULA:
        return f"$$\n{block.text}\n$$"
    if block.kind in {BlockType.CHART, BlockType.IMAGE} and block.image_path:
        assets.mkdir(parents=True, exist_ok=True)
        destination = assets / block.image_path.name
        shutil.copy2(block.image_path, destination)
        label = "Chart" if block.kind == BlockType.CHART else "Image"
        image = f"![{label}]({assets.name}/{destination.name})"
        return f"{image}\n\n{block.text}".strip()
    return block.text
