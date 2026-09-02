import os

PDF_DIR = "data/raw_pdfs"


def main():
    if not os.path.isdir(PDF_DIR):
        print(f"{PDF_DIR} doesn't exist yet.")
        return

    all_files = [f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")]
    seen_files = set()
    unique_files = []

    # Identify and optionally delete duplicates
    for f in all_files:
        if f in seen_files:
            os.remove(os.path.join(PDF_DIR, f))  # Deletes the exact duplicate name
            print(f"Deleted duplicate: {f}")
        else:
            seen_files.add(f)
            unique_files.append(f)

    unique_files.sort()
    total_size = 0

    print(f"{'File':<55} {'Size (KB)':>10}")
    print("-" * 66)

    for f in unique_files:
        size_kb = os.path.getsize(os.path.join(PDF_DIR, f)) / 1024
        total_size += size_kb
        print(f"{f:<55} {size_kb:>10.1f}")

    print("-" * 66)
    print(f"Total PDFs: {len(unique_files)}")
    print(f"Total size: {total_size/1024:.1f} MB")


if __name__ == "__main__":
    main()
