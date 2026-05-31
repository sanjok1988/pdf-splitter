#!/usr/bin/env python3
"""
pdf_splitter.py
---------------
Production-ready CLI application to split PDF files into custom page ranges.

Usage:
    python pdf_splitter.py "path/to/folder"
    python pdf_splitter.py "path/to/folder" --ranges "1-5,6-10,11-25"
    python pdf_splitter.py "path/to/folder" --ranges "1-10,15,20-30" --overwrite
    python pdf_splitter.py "path/to/folder" --ranges "1-50" --recursive --verbose

Features:
    - Split PDFs into custom page ranges
    - Support for comma-separated ranges (1-5, 6-10, 11-25)
    - Support for single pages (1, 5, 10)
    - Mixed ranges and single pages supported
    - ONE output PDF per page range (not one per page)
    - Comprehensive error handling and logging
    - Verbose output option
    - Progress indicators
    - JSON report generation

Requirements:
    pip install pypdf
"""

import argparse
import sys
import time
import json
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.errors import PdfReadError
except ImportError:
    print("[ERROR] 'pypdf' library is not installed.")
    print("        Run: pip install pypdf")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────
# SECTION 1 — Data Models
# ─────────────────────────────────────────────────────────────

@dataclass
class PageRange:
    """Represents a single page or range of pages."""
    start: int
    end: int

    def __post_init__(self):
        if self.start < 1:
            raise ValueError(f"Page numbers must be >= 1, got start={self.start}")
        if self.end < self.start:
            raise ValueError(f"End page ({self.end}) cannot be less than start ({self.start})")

    def contains_page(self, page_num: int) -> bool:
        """Check if a page number falls within this range."""
        return self.start <= page_num <= self.end

    def get_pages(self) -> List[int]:
        """Get all page numbers in this range."""
        return list(range(self.start, self.end + 1))

    def __str__(self) -> str:
        if self.start == self.end:
            return f"{self.start}"
        return f"{self.start}-{self.end}"


@dataclass
class ProcessingResult:
    """Result of processing a single PDF."""
    success: bool
    file_name: str
    pages_total: int
    pages_processed: int
    output_dir: Optional[Path]
    error: Optional[str]
    elapsed_time: float
    pages_saved: List[int]
    page_ranges_used: str
    output_files: List[str]  # NEW: Track output files per range


# ─────────────────────────────────────────────────────────────
# SECTION 2 — Page Range Parser
# ─────────────────────────────────────────────────────────────

def parse_page_ranges(ranges_str: str) -> List[PageRange]:
    """
    Parse user input page ranges into PageRange objects.

    Supports:
        - Single page: "5" → pages [5]
        - Range: "1-10" → pages [1,2,...,10]
        - Multiple: "1-5,10,15-20" → combined

    Args:
        ranges_str (str): Comma-separated page ranges

    Returns:
        List[PageRange]: Parsed and validated page ranges

    Raises:
        ValueError: If input format is invalid
    """
    if not ranges_str or not ranges_str.strip():
        return []

    ranges = []
    parts = [p.strip() for p in ranges_str.split(",")]

    for part in parts:
        if not part:
            continue

        try:
            if "-" in part:
                # Range format: "1-10"
                start_str, end_str = part.split("-", 1)
                start = int(start_str.strip())
                end = int(end_str.strip())
                ranges.append(PageRange(start, end))
            else:
                # Single page: "5"
                page = int(part.strip())
                ranges.append(PageRange(page, page))
        except (ValueError, IndexError) as e:
            raise ValueError(
                f"Invalid page range format: '{part}'. "
                f"Use format like '1-5', '10', or '1-5,10,15-20'"
            ) from e

    if not ranges:
        raise ValueError("No valid page ranges found in input")

    # Sort ranges by start page (do NOT merge to preserve separate output files)
    ranges.sort(key=lambda r: r.start)

    return ranges


def get_page_ranges_to_extract(
    ranges: List[PageRange],
    total_pages: int
) -> List[PageRange]:
    """
    Validate and adjust page ranges against PDF page count.

    Args:
        ranges (List[PageRange]): Parsed page ranges
        total_pages (int): Total pages in PDF

    Returns:
        List[PageRange]: Validated ranges (adjusted if necessary)

    Raises:
        ValueError: If any range is completely out of bounds
    """
    validated = []

    for page_range in ranges:
        if page_range.start > total_pages:
            raise ValueError(
                f"Page range {page_range} exceeds total pages ({total_pages})"
            )

        # Adjust end to not exceed total pages, but keep the range
        adjusted_end = min(page_range.end, total_pages)
        validated.append(PageRange(page_range.start, adjusted_end))

    return validated


# ─────────────────────────────────────────────────────────────
# SECTION 3 — Folder Validation
# ─────────────────────────────────────────────────────────────

def validate_folder(folder_path: str) -> Path:
    """
    Validate the provided folder path.

    Args:
        folder_path (str): Raw string path provided by the user.

    Returns:
        Path: A resolved Path object if valid.

    Raises:
        SystemExit: If the path is invalid
    """
    path = Path(folder_path).resolve()

    if not path.exists():
        print(f"[ERROR] The folder does not exist: {path}")
        sys.exit(1)

    if not path.is_dir():
        print(f"[ERROR] The provided path is not a folder: {path}")
        sys.exit(1)

    try:
        path.stat()
    except PermissionError:
        print(f"[ERROR] Permission denied when accessing: {path}")
        sys.exit(1)

    return path


# ─────────────────────────────────────────────────────────────
# SECTION 4 — PDF Discovery
# ─────────────────────────────────────────────────────────────

def find_pdf_files(folder: Path, recursive: bool = False) -> List[Path]:
    """
    Search for all PDF files in the given folder.

    Args:
        folder (Path): The root folder to search in
        recursive (bool): If True, search subdirectories

    Returns:
        List[Path]: Sorted list of PDF file paths
    """
    pattern = "**/*.pdf" if recursive else "*.pdf"
    pdf_files = sorted(folder.glob(pattern))

    if not pdf_files:
        level = "folder and its subfolders" if recursive else "folder"
        print(f"[WARNING] No PDF files found in the {level}: {folder}")
        sys.exit(0)

    return pdf_files


# ─────────────────────────────────────────────────────────────
# SECTION 5 — Output Management
# ─────────────────────────────────────────────────────────────

def resolve_output_folder(
    base_folder: Path,
    pdf_stem: str,
    suffix: str = "",
    overwrite: bool = False
) -> Path:
    """
    Determine the output subfolder for split pages.

    Args:
        base_folder (Path): Parent folder for output
        pdf_stem (str): PDF filename without extension
        suffix (str): Optional suffix for the folder name
        overwrite (bool): Allow overwriting existing folders

    Returns:
        Path: Output directory path
    """
    folder_name = f"{pdf_stem}{suffix}"
    output_dir = base_folder / folder_name

    if overwrite or not output_dir.exists():
        return output_dir

    # Generate unique folder name
    counter = 1
    while True:
        candidate = base_folder / f"{folder_name}_{counter}"
        if not candidate.exists():
            return candidate
        counter += 1


# ─────────────────────────────────────────────────────────────
# SECTION 6 — PDF Processing
# ─────────────────────────────────────────────────────────────

def split_pdf(
    pdf_path: Path,
    output_dir: Path,
    page_ranges: Optional[List[PageRange]] = None,
    overwrite: bool = False,
    verbose: bool = False
) -> ProcessingResult:
    """
    Split a PDF file into custom page ranges.

    FIXED BEHAVIOR:
    - Each PageRange produces ONE output PDF containing all pages in that range
    - NOT one file per page
    - Output files named: split_pages_<start>-<end>.pdf

    Args:
        pdf_path (Path): Source PDF file path
        output_dir (Path): Output directory for split files
        page_ranges (List[PageRange]): Specific page ranges to extract (None = all)
        overwrite (bool): Overwrite existing files
        verbose (bool): Verbose output

    Returns:
        ProcessingResult: Result of the operation
    """
    result = ProcessingResult(
        success=False,
        file_name=pdf_path.name,
        pages_total=0,
        pages_processed=0,
        output_dir=None,
        error=None,
        elapsed_time=0.0,
        pages_saved=[],
        page_ranges_used="",
        output_files=[]  # NEW: Track output files
    )

    start_time = time.time()

    if verbose:
        print(f"{'─' * 70}")
        print(f"  Processing: {pdf_path.name}")
        print(f"  Output Dir: {output_dir}")
        print(f"{'─' * 70}")

    # ── Step 1: Open and read PDF ───────────────────────────
    try:
        reader = PdfReader(str(pdf_path))
    except PdfReadError as e:
        result.error = f"Corrupted or unreadable PDF — {e}"
        if verbose:
            print(f"  [ERROR] {result.error}")
        return result
    except Exception as e:
        result.error = f"Unexpected error reading PDF — {e}"
        if verbose:
            print(f"  [ERROR] {result.error}")
        return result

    # ── Step 2: Check encryption ────────────────────────────
    if reader.is_encrypted:
        result.error = "PDF is password-protected"
        if verbose:
            print(f"  [ERROR] {result.error}")
        return result

    total_pages = len(reader.pages)
    result.pages_total = total_pages

    if total_pages == 0:
        result.error = "PDF contains no pages"
        if verbose:
            print(f"  [ERROR] {result.error}")
        return result

    if verbose:
        print(f"  Total Pages: {total_pages}")

    # ── Step 3: Determine page ranges to extract ────────────
    try:
        if page_ranges:
            ranges_to_extract = get_page_ranges_to_extract(page_ranges, total_pages)
            result.page_ranges_used = ", ".join(str(r) for r in ranges_to_extract)
            if verbose:
                print(f"  Extracting: {result.page_ranges_used}")
        else:
            # If no ranges specified, treat entire PDF as one range
            ranges_to_extract = [PageRange(1, total_pages)]
            result.page_ranges_used = f"1-{total_pages}"
            if verbose:
                print(f"  Mode: Extract all pages (1-{total_pages})")
    except ValueError as e:
        result.error = str(e)
        if verbose:
            print(f"  [ERROR] {result.error}")
        return result

    # ── Step 4: Create output directory ─────────────────────
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        result.error = f"Permission denied creating folder: {output_dir}"
        if verbose:
            print(f"  [ERROR] {result.error}")
        return result
    except OSError as e:
        result.error = f"Failed to create output folder — {e}"
        if verbose:
            print(f"  [ERROR] {result.error}")
        return result

    # ── Step 5: Process each page range ─────────────────────
    # CRITICAL: ONE iteration = ONE output file (not one per page)
    total_ranges = len(ranges_to_extract)

    for range_idx, page_range in enumerate(ranges_to_extract):
        # Generate output filename for this range
        range_filename = f"split_pages_{page_range.start}-{page_range.end}.pdf"
        range_output_path = output_dir / range_filename

        # Skip existing files unless overwrite is enabled
        if range_output_path.exists() and not overwrite:
            if verbose:
                print(f"  [SKIP] {range_filename} (already exists)")
            result.output_files.append(str(range_output_path))
            continue

        if verbose:
            print(f"  [{range_idx + 1}/{total_ranges}] Creating {range_filename}...")

        # Create a NEW writer for this range
        # This writer will accumulate ALL pages in the range
        writer = PdfWriter()

        # Accumulate all pages for this range into the same writer
        pages_in_range = page_range.get_pages()  # Get 1-based page numbers

        for page_num in pages_in_range:
            # Convert 1-based user page number to 0-based PDF index
            page_index = page_num - 1

            try:
                writer.add_page(reader.pages[page_index])
                result.pages_saved.append(page_num)
            except IndexError:
                if verbose:
                    print(f"    [ERROR] Page {page_num} index out of range")
                continue

        # Write the completed writer to disk ONCE per range
        # (not once per page)
        try:
            with open(range_output_path, "wb") as output_file:
                writer.write(output_file)

            result.output_files.append(str(range_output_path))
            result.pages_processed += len(pages_in_range)

            if verbose:
                pages_count = len(pages_in_range)
                print(f"    ✔ Written {pages_count} page(s)")

        except (PermissionError, OSError) as e:
            if verbose:
                print(f"    [ERROR] Failed to write {range_filename} — {e}")
            continue

    result.output_dir = output_dir
    result.success = True
    result.elapsed_time = time.time() - start_time

    if verbose:
        print(f"  ✔ Completed in {result.elapsed_time:.2f}s")

    return result


# ─────────────────────────────────────────────────────────────
# SECTION 7 — Report Generation
# ─────────────────────────────────────────────────────────────

def generate_report(
    results: List[ProcessingResult],
    output_folder: Path,
    page_ranges_input: Optional[str] = None
) -> Path:
    """
    Generate a JSON report of all processing results.

    Args:
        results (List[ProcessingResult]): All processing results
        output_folder (Path): Where to save the report
        page_ranges_input (str): Original page ranges input

    Returns:
        Path: Path to the generated report
    """
    report = {
        "generated_at": datetime.now().isoformat(),
        "total_pdfs": len(results),
        "successful": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
        "page_ranges_requested": page_ranges_input or "All pages",
        "results": [
            {
                **asdict(r),
                "output_dir": str(r.output_dir) if r.output_dir else None,
            }
            for r in results
        ]
    }

    report_path = output_folder / f"split_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    return report_path


# ─────────────────────────────────────────────────────────────
# SECTION 8 — Main Orchestrator
# ─────────────────────────────────────────────────────────────

def process_all_pdfs(
    folder: Path,
    page_ranges: Optional[List[PageRange]] = None,
    overwrite: bool = False,
    recursive: bool = False,
    verbose: bool = False,
    generate_json: bool = True
) -> None:
    """
    Discover and process all PDFs in target folder.

    Args:
        folder (Path): Root folder path
        page_ranges (List[PageRange]): Page ranges to extract
        overwrite (bool): Allow overwriting files
        recursive (bool): Search subfolders
        verbose (bool): Verbose output
        generate_json (bool): Generate JSON report
    """
    print(f"{'═' * 70}")
    print(f"  PDF Splitter — Advanced Page Range Edition (FIXED)")
    print(f"{'═' * 70}")
    print(f"  Folder    : {folder}")
    print(f"  Overwrite : {'Yes' if overwrite else 'No'}")
    print(f"  Recursive : {'Yes' if recursive else 'No'}")
    print(f"  Verbose   : {'Yes' if verbose else 'No'}")
    if page_ranges:
        ranges_str = ", ".join(str(r) for r in page_ranges)
        print(f"  Ranges    : {ranges_str}")
    else:
        print(f"  Mode      : Extract all pages as one file per range")
    print(f"{'═' * 70}")

    # Discover PDFs
    pdf_files = find_pdf_files(folder, recursive=recursive)
    total_found = len(pdf_files)
    print(f"  Found {total_found} PDF file(s) to process.")

    # Process each PDF
    results = []

    for index, pdf_path in enumerate(pdf_files, start=1):
        if not verbose:
            print(f"  [{index}/{total_found}] Processing: {pdf_path.name}...", end=" ")
        else:
            print(f"[{index}/{total_found}]")

        # Determine suffix for output folder
        suffix = ""
        if page_ranges:
            ranges_str = "_".join(str(r).replace("-", "to") for r in page_ranges)
            suffix = f"_range_{ranges_str}"

        output_dir = resolve_output_folder(
            pdf_path.parent,
            pdf_path.stem,
            suffix=suffix,
            overwrite=overwrite
        )

        result = split_pdf(
            pdf_path,
            output_dir,
            page_ranges=page_ranges,
            overwrite=overwrite,
            verbose=verbose
        )
        results.append(result)

        if not verbose:
            status = "✔" if result.success else "✘"
            num_output_files = len(result.output_files)
            print(f"{status} ({num_output_files} file(s), {result.pages_processed} pages)")

    # Generate summary
    print(f"{'═' * 70}")
    print(f"  SUMMARY")
    print(f"{'═' * 70}")
    print(f"  Total PDFs      : {len(results)}")
    print(f"  Successful      : {sum(1 for r in results if r.success)}")
    print(f"  Failed          : {sum(1 for r in results if not r.success)}")

    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    if successful:
        print(f"\n  ✔ Successful Files:")
        for item in successful:
            print(f"     • {item.file_name}")
            print(f"       └─ Pages: {item.pages_processed}/{item.pages_total}")
            print(f"       └─ Ranges: {item.page_ranges_used}")
            print(f"       └─ Output Files: {len(item.output_files)}")
            if item.output_files:
                for out_file in item.output_files:
                    filename = Path(out_file).name
                    print(f"          • {filename}")
            print(f"       └─ Directory: {item.output_dir}")

    if failed:
        print(f"\n  ✘ Failed Files:")
        for item in failed:
            print(f"     • {item.file_name}")
            print(f"       └─ Reason: {item.error}")

    total_time = sum(r.elapsed_time for r in results)
    print(f"\n  Total Time: {total_time:.2f}s")

    # Generate JSON report
    if generate_json:
        ranges_input = None
        if page_ranges:
            ranges_input = ", ".join(str(r) for r in page_ranges)
        report_path = generate_report(results, folder, ranges_input)
        print(f"  Report: {report_path}")

    print(f"{'═' * 70}")


# ─────────────────────────────────────────────────────────────
# SECTION 9 — CLI Interface
# ─────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="pdf_splitter",
        description=(
            "Production-ready PDF splitter with advanced page range support.\n"
            "One output PDF file per page range (NOT one per page)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Split all pages into one file per range
  python pdf_splitter.py "C:/Documents/PDFs"

  # Extract specific page ranges (each becomes one PDF)
  python pdf_splitter.py "./pdfs" --ranges "1-5,10,15-20"
    → Creates: split_pages_1-5.pdf, split_pages_10-10.pdf, split_pages_15-20.pdf

  # Single pages and ranges combined
  python pdf_splitter.py "./pdfs" --ranges "1-10,15,20-25"
    → Creates: split_pages_1-10.pdf, split_pages_15-15.pdf, split_pages_20-25.pdf

  # With options
  python pdf_splitter.py "./pdfs" --ranges "1-50" --overwrite --recursive --verbose

  # Generate report (automatic)
  python pdf_splitter.py "./pdfs" --ranges "1-10,20-30"

Page Range Format:
  • Single page: "5" → one PDF with that page
  • Range: "1-10" → one PDF with pages 1-10
  • Multiple: "1-5,10,15-20" → three PDFs with their respective pages
        """,
    )

    parser.add_argument(
        "folder",
        type=str,
        help="Path to folder containing PDF files",
    )

    parser.add_argument(
        "--ranges",
        type=str,
        default=None,
        help=(
            "Page ranges to extract (e.g., '1-5,10,15-20'). "
            "Each range becomes one output PDF file. "
            "If not specified, all pages are extracted as one file."
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Overwrite existing output folders and files",
    )

    parser.add_argument(
        "--recursive",
        action="store_true",
        default=False,
        help="Search for PDFs in subfolders",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Show detailed progress information",
    )

    parser.add_argument(
        "--no-report",
        action="store_true",
        default=False,
        help="Skip JSON report generation",
    )

    return parser


def main() -> None:
    """Application entry point."""
    parser = build_arg_parser()
    args = parser.parse_args()

    # Validate folder
    folder = validate_folder(args.folder)

    # Parse page ranges if provided
    page_ranges = None
    if args.ranges:
        try:
            page_ranges = parse_page_ranges(args.ranges)
        except ValueError as e:
            print(f"[ERROR] Invalid page ranges: {e}")
            sys.exit(1)

    # Run processing
    process_all_pdfs(
        folder=folder,
        page_ranges=page_ranges,
        overwrite=args.overwrite,
        recursive=args.recursive,
        verbose=args.verbose,
        generate_json=not args.no_report,
    )


if __name__ == "__main__":
    main()