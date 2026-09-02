"""
End-to-end ingestion pipeline:

  PDF -> parse (text + images) -> caption images (vision) -> chunk -> embed -> Chroma

Run:
    python -m ingestion.pipeline --pdf data/sample.pdf --collection my_docs
"""

import argparse
import os
from tqdm import tqdm

from .config import Config
from .pdf_parser_docling import parse_pdf
from .vision_captioner import caption_image
from .chunker import build_documents, chunk_documents
from .vector_store import add_documents
from .latency_logger import timed_stage
from .table_store import register_table
from .vector_store import list_sources


def _load_ingested(collection_name: str) -> set[str]:
    return set(list_sources(collection_name))


def run_pipeline(pdf_path: str, collection_name: str):
    Config.validate()
    doc_id = os.path.splitext(os.path.basename(pdf_path))[0]

    # Stage 1: parse PDF into text + extracted images
    with timed_stage("pdf_parse", doc_id):
        pages = parse_pdf(pdf_path)

    total_tables = sum(len(p.tables) for p in pages)
    if total_tables > 0:
        with timed_stage("table_ingestion", doc_id, meta={"table_count": total_tables}):
            for page in pages:
                for table_idx, df in page.tables:
                    try:
                        register_table(
                            df, source=doc_id, page=page.page_num, table_idx=table_idx
                        )
                    except Exception as e:
                        print(
                            f"[warn] failed to register table p{page.page_num}#{table_idx}: {e}"
                        )

    total_images = sum(len(p.image_paths) for p in pages)
    print(f"Parsed {len(pages)} pages, {total_images} images, {total_tables} tables.")

    # Stage 2: caption every extracted image with a vision model
    captions: dict[str, str] = {}
    with timed_stage("vision_captioning", doc_id, meta={"image_count": total_images}):
        all_image_paths = [img for p in pages for img in p.image_paths]
        for img_path in tqdm(all_image_paths, desc="Captioning images"):
            captions[img_path] = caption_image(img_path)

    # Stage 3: build page-level documents (text + inline image captions)
    with timed_stage("build_documents", doc_id):
        raw_docs = build_documents(pages, captions, source_name=doc_id)

    # Stage 4: chunk documents
    with timed_stage("chunking", doc_id, meta={"raw_doc_count": len(raw_docs)}):
        chunks = chunk_documents(raw_docs)

    print(f"Produced {len(chunks)} chunks.")

    # Stage 5: embed + store in Chroma
    with timed_stage("embed_and_store", doc_id, meta={"chunk_count": len(chunks)}):
        add_documents(chunks, collection_name=collection_name)

    print(f"Done. Stored {len(chunks)} chunks in collection '{collection_name}'.")
    print(f"Latency log: {Config.LATENCY_LOG_PATH}")


INGESTED_LOG = os.path.join(Config.LOG_DIR, "ingested_docs.txt")


def run_pipeline_batch(pdf_dir: str, collection_name: str):
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print(f"No PDFs found in {pdf_dir}")
        return

    already_done = _load_ingested(collection_name)
    print(
        f"Found {len(pdf_files)} PDFs. {len(already_done)} already in Chroma, skipping those.\n"
    )

    for fname in pdf_files:
        doc_id = os.path.splitext(fname)[0]
        if doc_id in already_done:
            print(f"--- {fname} (already in Chroma, skipping) ---")
            continue

        print(f"--- {fname} ---")
        run_pipeline(os.path.join(pdf_dir, fname), collection_name)
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest PDF(s) into the RAG vector store."
    )
    parser.add_argument("--pdf", help="Path to a single PDF file")
    parser.add_argument(
        "--pdf_dir", help="Path to a directory of PDFs (ingests all of them)"
    )
    parser.add_argument("--collection", required=True, help="Chroma collection name")
    args = parser.parse_args()

    if not args.pdf and not args.pdf_dir:
        parser.error("Provide either --pdf or --pdf_dir")

    if args.pdf_dir:
        run_pipeline_batch(args.pdf_dir, args.collection)
    else:
        run_pipeline(args.pdf, args.collection)
