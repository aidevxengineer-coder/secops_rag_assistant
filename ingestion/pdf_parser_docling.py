"""
Parses a PDF using Docling — layout-aware, keeps tables as proper markdown
tables (not garbled text), preserves reading order across columns, and
extracts pictures as separate elements with page provenance.

This replaces raw PyMuPDF text dumping. Docling is genuinely what a lot of
production RAG pipelines use for the parsing layer now.
"""

import os
from dataclasses import dataclass, field
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.datamodel.base_models import InputFormat
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling_core.types.doc import TableItem, PictureItem, TextItem

from .config import Config


@dataclass
class PageContent:
    page_num: int
    content_blocks: list[str] = field(
        default_factory=list
    )  # ordered text + table markdown
    image_paths: list[str] = field(default_factory=list)
    tables: list = field(default_factory=list)  # list of (table_idx, pandas.DataFrame)

    @property
    def text(self) -> str:
        return "\n\n".join(self.content_blocks)


def _build_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.generate_picture_images = (
        True  # needed so we can save images to disk
    )
    pipeline_options.images_scale = 1.0  # higher res for better vision captioning later
    pipeline_options.do_ocr = (
        False  # our PDFs are digitally-born, already have a real text layer
    )
    pipeline_options.do_table_structure = True  # required for any table parsing at all
    pipeline_options.table_structure_options.mode = (
        TableFormerMode.ACCURATE
    )  # slower, but needed
    # for dense multi-column numeric tables (test vectors, S-boxes, parameter tables) —
    # the default FAST mode misaligns cells more often on these
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                backend=PyPdfiumDocumentBackend,  # reads text layer directly, never invokes OCR
            )
        }
    )


def parse_pdf(pdf_path: str) -> list[PageContent]:
    """
    Returns a list of PageContent, one per page, with content blocks
    (paragraphs + tables-as-markdown) in original reading order, and
    paths to extracted images saved under data/images/<doc_id>/.
    """
    doc_id = os.path.splitext(os.path.basename(pdf_path))[0]
    out_dir = os.path.join(Config.IMAGE_DIR, doc_id)
    os.makedirs(out_dir, exist_ok=True)

    converter = _build_converter()
    result = converter.convert(pdf_path)
    doc = result.document

    pages_map: dict[int, PageContent] = {}
    img_counter = 0
    table_counter = 0

    def _get_page(page_no: int) -> PageContent:
        if page_no not in pages_map:
            pages_map[page_no] = PageContent(page_num=page_no)
        return pages_map[page_no]

    for item, _level in doc.iterate_items():
        if not getattr(item, "prov", None):
            continue
        page_no = item.prov[0].page_no
        page = _get_page(page_no)

        if isinstance(item, TableItem):
            table_counter += 1
            try:
                df = item.export_to_dataframe(doc)
                page.tables.append((table_counter, df))

                pointer = (
                    f"[TABLE: page {page_no}, {len(df)} rows x {len(df.columns)} columns, "
                    f"columns: {', '.join(str(c) for c in df.columns)}. "
                    f"Query the structured table store for exact values.]"
                )
                page.content_blocks.append(pointer)
            except Exception as e:
                print(f"[warn] failed to export table on page {page_no}: {e}")

        elif isinstance(item, PictureItem):
            try:
                img_counter += 1
                pil_image = item.get_image(doc)
                if pil_image is not None:
                    img_path = os.path.join(
                        out_dir, f"page{page_no}_img{img_counter}.png"
                    )
                    pil_image.save(img_path)
                    page.image_paths.append(img_path)
            except Exception as e:
                print(f"[warn] failed to extract image on page {page_no}: {e}")

        elif isinstance(item, TextItem):
            if item.text and item.text.strip():
                page.content_blocks.append(item.text.strip())

    return [pages_map[k] for k in sorted(pages_map.keys())]


if __name__ == "__main__":
    import sys

    pages = parse_pdf(sys.argv[1])
    for p in pages:
        print(f"Page {p.page_num}: {len(p.text)} chars, {len(p.image_paths)} images")
