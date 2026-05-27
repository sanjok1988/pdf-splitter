# Steps to Use PDF Splitter with Virtual Environment (venv)

Using a **virtual environment** is the professional approach. It keeps dependencies isolated and prevents conflicts with other Python projects.

---

## Step 1 — Prerequisites

Verify Python 3 is installed:
```bash
python --version
# or
python3 --version
```

Expected output: `Python 3.x.x`

---

## Step 2 — Create a Project Folder

Choose a location and create a folder for your project:

### Windows
```bash
# Create folder
mkdir C:\pdf-splitter-project
cd C:\pdf-splitter-project
```

### macOS / Linux
```bash
# Create folder
mkdir ~/pdf-splitter-project
cd ~/pdf-splitter-project
```

---

## Step 3 — Create a Virtual Environment

### Windows
```bash
python -m venv venv
```

### macOS / Linux
```bash
python3 -m venv venv
```

This creates a `venv` folder with an isolated Python environment.

---

## Step 4 — Activate the Virtual Environment

### Windows (Command Prompt)
```bash
venv\Scripts\activate
```

### Windows (PowerShell)
```bash
venv\Scripts\Activate.ps1
```
> If you get an error about script execution, run PowerShell as Administrator first.

### macOS / Linux (Bash/Zsh)
```bash
source venv/bin/activate
```

**You should see `(venv)` at the beginning of your terminal prompt:**
```
(venv) C:\pdf-splitter-project>
```
or
```
(venv) ~/pdf-splitter-project $
```

---

## Step 5 — Upgrade pip (Optional but Recommended)

```bash
pip install --upgrade pip
```

---

## Step 6 — Install Required Library

With the virtual environment **activated**, install `pypdf`:

```bash
pip install pypdf
```

Verify installation:
```bash
pip list
```

You should see `pypdf` in the list.

---

## Step 7 — Save the Script

Create a new file named **`pdf_splitter.py`** in your project folder:

```bash
# Windows
notepad pdf_splitter.py

# macOS / Linux
nano pdf_splitter.py
```

Or use any text editor (VS Code, Sublime, PyCharm, etc.)

**Folder structure now looks like:**
```
pdf-splitter-project/
  ├── venv/                    ← Virtual environment
  ├── pdf_splitter.py          ← Your script
  └── documents/               ← Your PDF folder (optional)
       ├── invoice.pdf
       └── report.pdf
```

Paste the complete code from the earlier prompt into `pdf_splitter.py` and **save**.

---

## Step 8 — Make the Script Executable (Optional — Linux/macOS)

```bash
chmod +x pdf_splitter.py
```

---

## Step 9 — Prepare Your PDF Folder

Create or prepare a folder with your PDF files:

```
pdf-splitter-project/
  ├── venv/
  ├── pdf_splitter.py
  └── documents/               ← Folder with PDFs
       ├── invoice.pdf
       ├── report.pdf
       └── contract.pdf
```

---

## Step 10 — Run the Application

**Make sure the virtual environment is still activated** (you should see `(venv)` in the prompt).

### Basic Usage
```bash
python pdf_splitter.py "documents"
```

### With Full Path
```bash
# Windows
python pdf_splitter.py "C:\pdf-splitter-project\documents"

# macOS / Linux
python pdf_splitter.py "~/pdf-splitter-project/documents"

# Or relative path
python pdf_splitter.py "./documents"
```

### With Flags
```bash
# Overwrite existing output
python pdf_splitter.py "documents" --overwrite

# Search in subfolders
python pdf_splitter.py "documents" --recursive

# Both flags
python pdf_splitter.py "documents" --overwrite --recursive
```

### Get Help
```bash
python pdf_splitter.py --help
```

---

## Step 11 — Watch the Progress

The terminal will show **live progress**:

```
════════════════════════════════════════════════════════════
  PDF Splitter — Starting
  Folder    : /home/user/pdf-splitter-project/documents
  Overwrite : No
  Recursive : No
════════════════════════════════════════════════════════════

  Found 3 PDF file(s) to process.

[1/3]
────────────────────────────────────────────────────────────
  Processing : invoice.pdf
  Output Dir : /home/user/pdf-splitter-project/documents/invoice
────────────────────────────────────────────────────────────
  Pages Found: 5
  [████████████████████] 100.0%  Saving page 005/005  →  page_005.pdf
  Done  ✔  5/5 pages saved in 0.12s

[2/3]
────────────────────────────────────────────────────────────
  Processing : report.pdf
  ...
```

---

## Step 12 — Check the Output

After completion, your folder structure will be:

```
pdf-splitter-project/
  ├── venv/
  ├── pdf_splitter.py
  └── documents/
       ├── invoice.pdf
       ├── report.pdf
       ├── contract.pdf
       │
       ├── invoice/
       │     ├── page_001.pdf
       │     ├── page_002.pdf
       │     └── page_003.pdf
       │
       ├── report/
       │     ├── page_001.pdf
       │     └── page_002.pdf
       │
       └── contract/
             └── page_001.pdf
```

---

## Step 13 — Deactivate Virtual Environment (When Done)

When you're finished, exit the virtual environment:

```bash
deactivate
```

The `(venv)` prefix will disappear from your terminal.

---

## Bonus — Create a Batch/Shell Script for Easy Reuse

### Windows — Create `run.bat`

```batch
@echo off
REM Activate virtual environment and run the script
call venv\Scripts\activate
python pdf_splitter.py %*
```

**Usage:**
```bash
run.bat "documents"
run.bat "documents" --overwrite
```

### macOS/Linux — Create `run.sh`

```bash
#!/bin/bash
# Activate virtual environment and run the script
source venv/bin/activate
python pdf_splitter.py "$@"
```

**Make executable and use:**
```bash
chmod +x run.sh
./run.sh documents
./run.sh documents --overwrite
```

---

## Project Structure (Final)

```
pdf-splitter-project/
│
├── venv/                          ← Virtual environment (don't edit)
│     ├── Scripts/                 (Windows)
│     └── bin/                     (macOS/Linux)
│
├── pdf_splitter.py                ← Main script
│
├── run.bat                        ← Optional: Windows launcher
├── run.sh                         ← Optional: Linux/macOS launcher
│
└── documents/                     ← Your PDFs go here
      ├── invoice.pdf
      ├── report.pdf
      └── contract.pdf
```

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `(venv)` not showing | Run activation command again from Step 4 |
| `No module named 'pypdf'` | Ensure venv is activated, then `pip install pypdf` |
| `Command not found: python` | Try `python3` instead of `python` |
| PowerShell script error | Run PowerShell as Administrator, then: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| Permission denied on `run.sh` | Run `chmod +x run.sh` |

---

## Quick Reference

```bash
# 1. Create & activate venv
mkdir pdf-splitter-project
cd pdf-splitter-project
python -m venv venv
source venv/bin/activate          # macOS/Linux
# or
venv\Scripts\activate             # Windows

# 2. Install dependency
pip install pypdf

# 3. Save pdf_splitter.py in project folder

# 4. Run
python pdf_splitter.py "documents"

# 5. Deactivate when done
deactivate
```