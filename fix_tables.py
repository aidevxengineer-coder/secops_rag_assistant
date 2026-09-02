"""
Re-extracts and re-registers ONLY the tables for one PDF — skips vision
captioning (slow, rate-limited) and skips re-embedding into Chroma (already
done). Use this to fix table_store failures without redoing the full pipeline.

Run: python fix_tables.py data/raw_pdfs/BestPracticesforMITREATTCKMapping.pdf
"""

import sys
import os
import traceback
from ingestion.pdf_parser_docling import parse_pdf
from ingestion.table_store import register_table


def main(pdf_path: str):
    doc_id = os.path.splitext(os.path.basename(pdf_path))[0]
    print(f"Re-parsing {pdf_path} (this still re-runs Docling, but nothing else)...")
    pages = parse_pdf(pdf_path)

    total_tables = sum(len(p.tables) for p in pages)
    print(f"Found {total_tables} tables.\n")

    for page in pages:
        for table_idx, df in page.tables:
            try:
                name = register_table(
                    df, source=doc_id, page=page.page_num, table_idx=table_idx
                )
                print(f"  registered: {name} ({len(df)} rows)")
            except Exception as e:
                print(f"  [STILL FAILED] p{page.page_num}#{table_idx}: {e}")
                traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_tables.py <path_to_pdf>")
        sys.exit(1)
    main(sys.argv[1])
