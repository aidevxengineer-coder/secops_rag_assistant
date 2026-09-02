"""
Turns parsed pages (text + captioned images) into LangChain Document chunks
ready for embedding. Keeps rich metadata (page, type, source) so retrieval
results can be traced back and re-ranked meaningfully.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from .config import Config
from .pdf_parser_docling import PageContent


def build_documents(
    pages: list[PageContent], captions: dict[str, str], source_name: str
) -> list[Document]:
    """
    captions: mapping of image_path -> caption text (already generated).
    Returns raw Documents (pre-split) — one per page combining text + image captions.
    """
    raw_docs = []
    for page in pages:
        content_parts = []
        if page.text:
            content_parts.append(page.text)

        for img_path in page.image_paths:
            caption = captions.get(img_path, "")
            if caption:
                content_parts.append(f"[Image description: {caption}]")

        full_content = "\n\n".join(content_parts).strip()
        if not full_content:
            continue

        raw_docs.append(
            Document(
                page_content=full_content,
                metadata={
                    "source": source_name,
                    "page": page.page_num,
                    "has_images": len(page.image_paths) > 0,
                    "image_count": len(page.image_paths),
                    "has_tables": len(page.tables) > 0,
                    "table_count": len(page.tables),
                },
            )
        )
    return raw_docs


def chunk_documents(raw_docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=Config.CHUNK_SIZE,
        chunk_overlap=Config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(raw_docs)

    for i, chunk in enumerate(chunks):
        chunk.metadata.setdefault("block_type", "text")
        chunk.metadata["chunk_id"] = (
            f"{chunk.metadata['source']}_p{chunk.metadata['page']}_c{i}"
        )

    return chunks
