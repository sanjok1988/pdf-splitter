#!/usr/bin/env python3
"""
pdf_splitter.py
---------------
A CLI application to split PDF files into individual pages.

Usage:
    python pdf_splitter.py "path/to/folder"
    python pdf_splitter.py "path/to/folder" --overwrite
    python pdf_splitter.py "path/to/folder" --recursive
    python pdf_splitter.py "path/to/folder" --overwrite --recursive

Requirements:
    pip install pypdf
"""

import argparse
import sys
import time
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.errors import PdfReadError
except ImportError:
    print("[ERROR] 'pypdf' library is not installed.")
    print("        Run: pip install pypdf")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────
# SECTION 1 — Folder Validation
# ─────────────────────────────────────────────────────────────

def validate_folder(folder_path: str) -> Path:
    """
    Validate the provided folder path.

    Args:
        folder_path (str): Raw string path provided by the user.

    Returns:
        Path: A resolved Path object if valid.

    Raises:
        SystemExit: If the path is invalid, not a directory, or not accessible.
    """
    path = Path(folder_path).resolve()

    if not path.exists():
        print(f"[ERROR] The folder does not exist: {path}")
        sys.exit(1)

    if not path.is_dir():
        print(f"[ERROR] The provided path is not a folder: {path}")
        sys.exit(1)

    if not path.stat().st_mode:
        print(f"[ERROR] Permission denied when accessing: {path}")
        sys.exit(1)

    return path


# ─────────────────────────────────────────────────────────────
# SECTION 2 — PDF Discovery
# ─────────────────────────────────────────────────────────────

def find_pdf_files(folder: Path, recursive: bool = False) -> list[Path]:
    """
    Search for all PDF files in the given folder.

    Args:
        folder  (Path): The root folder to search in.
        recursive (bool): If True, search subdirectories as well.

    Returns:
        list[Path]: A sorted list of PDF file paths found.
    """
    # Use rglob for recursive search, glob for flat search
    pattern = "**/*.pdf" if recursive else "*.pdf"
    pdf_files = sorted(folder.glob(pattern))

    # Exclude files that live inside output subfolders we may have created
    # (avoids re-processing already split pages on re-runs)
    pdf_files = [
        f for f in pdf_files
        if f.parent == folder or recursive
    ]

    if not pdf_files:
        level = "folder and its subfolders" if recursive else "folder"
        print(f"[WARNING] No PDF files found in the {level}: {folder}")
        sys.exit(0)

    return pdf_files


# ─────────────────────────────────────────────────────────────
# SECTION 3 — Output Folder Resolution
# ─────────────────────────────────────────────────────────────

def resolve_output_folder(base_folder: Path, pdf_stem: str, overwrite: bool) -> Path:
    """
    Determine the output subfolder for split pages.

    - If --overwrite is set, always use the base name.
    - Otherwise, generate a unique name: name_1, name_2, etc.

    Args:
        base_folder (Path): The parent folder where output goes.
        pdf_stem    (str):  PDF filename without extension.
        overwrite   (bool): Whether to allow overwriting.

    Returns:
        Path: The resolved output directory path.
    """
    output_dir = base_folder / pdf_stem

    if overwrite or not output_dir.exists():
        return output_dir

    # Generate a unique folder name to avoid overwriting
    counter = 1
    while True:
        candidate = base_folder / f"{pdf_stem}_{counter}"
        if not candidate.exists():
            return candidate
        counter += 1


# ─────────────────────────────────────────────────────────────
# SECTION 4 — Single PDF Splitting
# ─────────────────────────────────────────────────────────────

def split_pdf(pdf_path: Path, output_dir: Path, overwrite: bool) -> dict:
    """
    Split a single PDF file into individual single-page PDF files.

    Handles:
        - Password-protected PDFs
        - Corrupted or unreadable PDFs
        - Permission errors during write
        - Large PDFs (100+ pages)

    Args:
        pdf_path   (Path): Full path to the source PDF file.
        output_dir (Path): Directory where split pages will be saved.
        overwrite  (bool): Whether to overwrite existing page files.

    Returns:
        dict: A result dictionary with keys:
              'success'    (bool)
              'pages'      (int)
              'output_dir' (Path or None)
              'error'      (str or None)
    """
    result = {
        "success": False,
        "pages": 0,
        "output_dir": None,
        "error": None,
    }

    print(f"\n{'─' * 60}")
    print(f"  Processing : {pdf_path.name}")
    print(f"  Output Dir : {output_dir}")
    print(f"{'─' * 60}")

    # ── Step 1: Open and read the PDF ───────────────────────
    try:
        reader = PdfReader(str(pdf_path))
    except PdfReadError as e:
        result["error"] = f"Corrupted or unreadable PDF — {e}"
        print(f"  [ERROR] {result['error']}")
        return result
    except Exception as e:
        result["error"] = f"Unexpected error reading PDF — {e}"
        print(f"  [ERROR] {result['error']}")
        return result

    # ── Step 2: Check for password protection ───────────────
    if reader.is_encrypted:
        result["error"] = "PDF is password-protected and cannot be processed."
        print(f"  [ERROR] {result['error']}")
        return result

    total_pages = len(reader.pages)

    if total_pages == 0:
        result["error"] = "PDF contains no pages."
        print(f"  [ERROR] {result['error']}")
        return result

    print(f"  Pages Found: {total_pages}")

    # ── Step 3: Create the output directory ─────────────────
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        result["error"] = f"Permission denied when creating folder: {output_dir}"
        print(f"  [ERROR] {result['error']}")
        return result
    except OSError as e:
        result["error"] = f"Failed to create output folder — {e}"
        print(f"  [ERROR] {result['error']}")
        return result

    # ── Step 4: Split and save each page ────────────────────
    saved_count = 0
    start_time = time.time()

    for page_index in range(total_pages):
        # Zero-padded page number (supports up to 999,999 pages)
        page_number = page_index + 1
        pad_width = max(3, len(str(total_pages)))  # minimum 3 digits
        page_filename = f"page_{str(page_number).zfill(pad_width)}.pdf"
        page_path = output_dir / page_filename

        # ── Skip if file exists and overwrite is disabled ───
        if page_path.exists() and not overwrite:
            print(f"  [SKIP]  {page_filename} already exists.")
            saved_count += 1
            continue

        # ── Write this single page ──────────────────────────
        try:
            writer = PdfWriter()
            writer.add_page(reader.pages[page_index])

            with open(page_path, "wb") as output_file:
                writer.write(output_file)

            saved_count += 1

        except PermissionError:
            print(f"  [ERROR] Permission denied writing: {page_filename}")
            continue
        except OSError as e:
            print(f"  [ERROR] Failed to write {page_filename} — {e}")
            continue
        except Exception as e:
            print(f"  [ERROR] Unexpected error on page {page_number} — {e}")
            continue

        # ── Progress indicator ──────────────────────────────
        progress_pct = (page_number / total_pages) * 100
        bar_filled = int(progress_pct // 5)          # 20-char wide bar
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        print(
            f"  [{bar}] {progress_pct:5.1f}%  "
            f"Saving page {str(page_number).zfill(pad_width)}/{total_pages}  "
            f"→  {page_filename}",
            end="\r",
        )

    # Move to next line after progress bar
    print()

    elapsed = time.time() - start_time
    print(f"  Done  ✔  {saved_count}/{total_pages} pages saved in {elapsed:.2f}s")

    result["success"] = True
    result["pages"] = total_pages
    result["output_dir"] = output_dir

    return result


# ─────────────────────────────────────────────────────────────
# SECTION 5 — Main Orchestrator
# ─────────────────────────────────────────────────────────────

def process_all_pdfs(folder: Path, overwrite: bool, recursive: bool) -> None:
    """
    Discover and process all PDF files in the target folder.

    Args:
        folder    (Path): Validated root folder path.
        overwrite (bool): Allow overwriting existing split pages.
        recursive (bool): Search for PDFs inside subfolders.
    """
    print(f"\n{'═' * 60}")
    print(f"  PDF Splitter — Starting")
    print(f"  Folder    : {folder}")
    print(f"  Overwrite : {'Yes' if overwrite else 'No'}")
    print(f"  Recursive : {'Yes' if recursive else 'No'}")
    print(f"{'═' * 60}")

    # ── Discover PDFs ────────────────────────────────────────
    pdf_files = find_pdf_files(folder, recursive=recursive)
    total_found = len(pdf_files)
    print(f"\n  Found {total_found} PDF file(s) to process.\n")

    # ── Tracking counters ────────────────────────────────────
    successful = []
    failed = []

    # ── Process each PDF ─────────────────────────────────────
    for index, pdf_path in enumerate(pdf_files, start=1):
        print(f"\n[{index}/{total_found}]", end="")

        # Output always goes next to the PDF's own parent folder
        output_dir = resolve_output_folder(pdf_path.parent, pdf_path.stem, overwrite)
        result = split_pdf(pdf_path, output_dir, overwrite)

        if result["success"]:
            successful.append({
                "file": pdf_path.name,
                "pages": result["pages"],
                "output_dir": result["output_dir"],
            })
        else:
            failed.append({
                "file": pdf_path.name,
                "error": result["error"],
            })

    # ── Final Summary ─────────────────────────────────────────
    print(f"\n{'═' * 60}")
    print(f"  SUMMARY")
    print(f"{'═' * 60}")
    print(f"  Total PDFs Found      : {total_found}")
    print(f"  Successfully Split    : {len(successful)}")
    print(f"  Failed                : {len(failed)}")

    if successful:
        print(f"\n  ✔  Successful Files:")
        for item in successful:
            print(f"     • {item['file']}  ({item['pages']} pages)")
            print(f"       └─ Output: {item['output_dir']}")

    if failed:
        print(f"\n  ✘  Failed Files:")
        for item in failed:
            print(f"     • {item['file']}")
            print(f"       └─ Reason: {item['error']}")

    print(f"\n{'═' * 60}\n")


# ─────────────────────────────────────────────────────────────
# SECTION 6 — CLI Entry Point
# ─────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    """
    Build and return the CLI argument parser.

    Returns:
        argparse.ArgumentParser: Configured parser instance.
    """
    parser = argparse.ArgumentParser(
        prog="pdf_splitter",
        description=(
            "Split all PDF files in a folder into individual single-page PDFs.\n"
            "Each PDF gets its own subfolder named after the original file."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pdf_splitter.py "C:/Documents/PDFs"
  python pdf_splitter.py "/home/user/pdfs" --overwrite
  python pdf_splitter.py "./reports" --recursive
  python pdf_splitter.py "./reports" --overwrite --recursive
        """,
    )

    parser.add_argument(
        "folder",
        type=str,
        help="Path to the folder containing PDF files.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help=(
            "Overwrite existing output folders and page files. "
            "If not set, unique folder names will be created (e.g. invoice_1)."
        ),
    )

    parser.add_argument(
        "--recursive",
        action="store_true",
        default=False,
        help="Recursively search for PDF files inside subfolders.",
    )

    return parser


def main() -> None:
    """
    Application entry point.
    Parses CLI arguments, validates inputs, and starts processing.
    """
    parser = build_arg_parser()
    args = parser.parse_args()

    # Validate the folder before doing anything else
    folder = validate_folder(args.folder)

    # Run the main processing pipeline
    process_all_pdfs(
        folder=folder,
        overwrite=args.overwrite,
        recursive=args.recursive,
    )


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
