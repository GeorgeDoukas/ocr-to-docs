import pytest

from ocr_to_docs.models import Block, BlockType, BoundingBox, Document, Page


def test_bounding_box_rejects_inverted_coordinates() -> None:
    with pytest.raises(ValueError, match="ordered"):
        BoundingBox(10, 0, 5, 20)


def test_document_plain_text_follows_page_and_block_order() -> None:
    document = Document(
        source="sample.png",
        pages=[
            Page(
                number=1,
                width=100,
                height=100,
                blocks=[
                    Block(BlockType.HEADING, "Title"),
                    Block(BlockType.TEXT, "Body"),
                ],
            )
        ],
    )

    assert document.plain_text == "Title\nBody"
