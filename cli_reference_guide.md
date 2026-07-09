# Google Photo Meta Fixer — CLI Reference Guide

> **Version:** See [pyproject.toml](pyproject.toml) for the current release version.  
> **Entrypoint:** `gp-cleaner`  
> **Package:** `google-photo-meta-fixer` on [PyPI](https://pypi.org/project/google-photo-meta-fixer/)

---

## Table of Contents

1. [Recommended Workflows](#-1-recommended-workflows)
2. [Prerequisites & rclone Configuration](#-2-prerequisites--rclone-configuration)
3. [Installation](#-3-installation)
4. [CSV Input Specification](#-4-csv-input-specification)
5. [Drive Index Cache Management](#-5-drive-index-cache-management)
6. [Subcommand Reference](#-6-subcommand-reference)
   - [sync](#-61-sync-subcommands)
   - [metadata](#-62-metadata-subcommands)
   - [process](#-63-process-subcommands)
7. [Advanced Mechanics & Algorithms](#-7-advanced-mechanics--algorithms)
8. [Troubleshooting](#-8-troubleshooting)

---

## 🗺️ 1. Recommended Workflows

### Workflow A: Google Takeout

Use when photos were downloaded via **Google Takeout** (includes sidecar `.json` files).

| Step | Command | Required |
|---|---|---|
| Merge companion JSON into photos | `gp-cleaner process takeout --dir <dir>` | ✅ Yes |
| Verify timestamps written correctly | `gp-cleaner metadata verify-takeout` | Optional |
| Cross-check against CSV export | `gp-cleaner metadata verify-csv --csv <csv> --dir <dir>` | Optional |

### Workflow B: Browser CSV Export (GPTK)

Use when photos were downloaded directly from the browser and you have a GPTK CSV export.

| Step | Command | Required |
|---|---|---|
| Write timestamps from CSV to EXIF + filesystem | `gp-cleaner metadata fix-local --csv <csv> --dir <dir>` | ✅ Yes |
| Verify timestamps against CSV | `gp-cleaner metadata verify-csv --csv <csv> --dir <dir>` | Optional |
| Sync storage-consuming files cloud-to-cloud | `gp-cleaner sync consuming --csv <csv> --remote <remote>` | Optional |
| Align Drive file timestamps without re-upload | `gp-cleaner metadata fix-drive --remote <remote>` | Optional |

---

## ⚙️ 2. Prerequisites & rclone Configuration

All cloud operations require `rclone` configured with a Google Drive remote.

### Install rclone

```bash
# macOS
brew install rclone

# Linux
sudo apt install rclone
# or via the official installer:
curl https://rclone.org/install.sh | sudo bash
```

### Configure a Google Drive Remote

```bash
rclone config
```

Follow the interactive prompts:
1. Select **`n`** — New remote.
2. Name it (e.g., `gdrive`).
3. Select **Google Drive** from the provider list.
4. Leave `client_id` and `client_secret` blank (uses defaults).
5. Set scope to **Full access** (`drive`).
6. Allow browser-based auto-config (`y`).

**Verify the connection:**
```bash
rclone lsd gdrive:
```

### Install exiftool

Required for writing EXIF date tags inside photo and video files. Without it, only filesystem dates are updated.

```bash
brew install exiftool             # macOS
sudo apt install libimage-exiftool-perl  # Debian/Ubuntu
```

---

## 📦 3. Installation

### Option A: Install from PyPI (Recommended)

```bash
pip install google-photo-meta-fixer

# macOS (Homebrew-managed Python) or Linux:
pip install google-photo-meta-fixer --break-system-packages
```

### Option B: Install from Source (Editable)

```bash
git clone https://github.com/hiijitesh/google-photo-meta-fixer.git
cd google-photo-meta-fixer
pip install -e . --break-system-packages
```

### Option C: Standalone Binary (macOS)

Compile a single-file executable that does not depend on system Python:

```bash
pip install pyinstaller --break-system-packages
pyinstaller --onefile cleaner.py --name gp-cleaner
./dist/gp-cleaner --help
```

---

## 📊 4. CSV Input Specification

The `sync consuming`, `metadata fix-local`, and `metadata verify-csv` commands consume metadata CSV files exported from the [Google Photos Toolkit](https://github.com/xob0t/Google-Photos-Toolkit) userscript.

| Column | Type | Description |
|:---|:---|:---|
| `fileName` | String | Exact filename (e.g., `IMG_20210728_123456.jpg`). |
| `takenAt` | String | UTC ISO 8601 creation timestamp (e.g., `2021-07-28T06:54:29.891Z`). |
| `timezoneOffsetMs` | Integer | Local timezone offset in milliseconds (e.g., `19800000` = IST +05:30). |
| `takesUpSpace` | Boolean | `true` if the photo consumes Google storage quota (Original Quality). |
| `isOriginalQuality` | Boolean | `true` if the file is not compressed by Storage Saver. |
| `durationMs` | Integer | Present on video files; used to distinguish photo vs. video categories. |

---

## ⚡ 5. Drive Index Cache Management

To avoid hitting Google Drive API rate limits, all cloud commands read from local JSON index files:

- `data/json/drive_index.json` — Full Drive listing.
- `data/json/drive_index_photo_backUp.json` — `photos_backUp/` folder listing.

**Before any sync/metadata command, always refresh your cache:**
```bash
rclone lsjson -R "gdrive:" > data/json/drive_index.json
rclone lsjson -R "gdrive:photos_backUp" > data/json/drive_index_photo_backUp.json
```

> The tool prompts you at startup to refresh the cache automatically. Press **Enter** to accept (`y` is the default).

---

## 🛠️ 6. Subcommand Reference

### 📂 6.1 sync Subcommands

#### `gp-cleaner sync backup`

Copies original-quality photos from the general Drive index into organized year-wise `photos_backUp/[Year]/` folders, cloud-to-cloud.

**Syntax:**
```bash
gp-cleaner sync backup [--remote REMOTE]
```

**Workflow:**
1. Refreshes `drive_index.json`.
2. Filters CSV rows where `takesUpSpace == true` and `isOriginalQuality == true`.
3. Looks up each file in the Drive index to find its current path.
4. Generates and executes parallel `rclone copyto` commands.

---

#### `gp-cleaner sync consuming`

Finds original-quality photos listed in a CSV that exist on Drive but are absent from `photos_backUp/`, then copies them cloud-to-cloud.

**Syntax:**
```bash
gp-cleaner sync consuming --csv CSV_PATH [--remote REMOTE]
```

**Example:**
```bash
gp-cleaner sync consuming --csv "data/csv/consuming_album.csv" --remote gdrive:
```

---

#### `gp-cleaner sync upload-local`

Compares a local folder against the Drive index and uploads only missing files using a single optimized multi-threaded `rclone copy` invocation.

**Syntax:**
```bash
gp-cleaner sync upload-local --dir LOCAL_DIR --dest DEST_FOLDER [--remote REMOTE]
```

**Example:**
```bash
gp-cleaner sync upload-local --dir "data/photos/GPH OP" --dest "O Consuming"
```

**Workflow:**
1. Refreshes `drive_index_photo_backUp.json`.
2. Scans local directory for all files.
3. Identifies files not present in the Drive cache.
4. Writes missing paths to `logs/upload_manifest.txt`.
5. Runs `rclone copy --files-from logs/upload_manifest.txt --transfers 10 --checkers 16`.

---

### 🔍 6.2 metadata Subcommands

#### `gp-cleaner metadata fix-local`

Reads a GPTK CSV and writes correct `takenAt` timestamps into each photo's EXIF headers (`DateTimeOriginal`, `CreateDate`, `ModifyDate`) **and** updates filesystem `mtime`.

**Syntax:**
```bash
gp-cleaner metadata fix-local --csv CSV_PATH --dir LOCAL_DIR
```

**Example:**
```bash
gp-cleaner metadata fix-local --csv "data/csv/metadata.csv" --dir "data/photos/GPH OP"
```

**Requirements:** `exiftool` must be installed for EXIF writes. Filesystem timestamps are updated regardless.

**Workflow:**
1. Reads all entries from the CSV.
2. Walks `--dir` and builds a filename-to-path index.
3. Matches files by filename with fuzzy tolerance (`-edited`, truncation).
4. Updates `mtime` via `os.utime`.
5. Batch-writes EXIF tags via `exiftool` if available.
6. Reports matched vs. unmatched summary.

---

#### `gp-cleaner metadata fix-drive`

Corrects mismatched modification dates on Google Drive files to align with local files using `rclone touch`. No payload is re-uploaded.

**Syntax:**
```bash
gp-cleaner metadata fix-drive [--remote REMOTE]
```

**Workflow:**
1. Refreshes `drive_index_photo_backUp.json`.
2. Scans local backup directories for media files.
3. Compares each Drive file's `ModTime` with the local file's `mtime`.
4. Generates `rclone touch --timestamp` commands for all files with drift > 2 seconds.
5. Prompts for confirmation before executing.

---

#### `gp-cleaner metadata verify-csv`

Audits local photo EXIF timestamps and filesystem dates against a GPTK CSV to confirm `fix-local` was applied correctly.

**Syntax:**
```bash
gp-cleaner metadata verify-csv --csv CSV_PATH --dir LOCAL_DIR [--show-missing]
```

| Flag | Description |
|:---|:---|
| `--csv CSV_PATH` | Path to the GPTK metadata CSV file. |
| `--dir LOCAL_DIR` | Directory containing photos to audit. |
| `--show-missing` | Print files missing from the directory and extra files not in the CSV. |

**Example:**
```bash
gp-cleaner metadata verify-csv --csv "data/csv/metadata.csv" --dir "data/photos/photos_backUp" --show-missing
```

---

#### `gp-cleaner metadata verify-takeout`

Audits files processed via `process takeout` against `data/json/takeout_match.json` to confirm EXIF tags and filesystem dates were successfully written.

**Syntax:**
```bash
gp-cleaner metadata verify-takeout
```

---

### ⚙️ 6.3 process Subcommands

#### `gp-cleaner process takeout`

Recursively walks a Google Takeout export directory, matches companion `.json` sidecar files to their photos/videos using fuzzy matching, and writes GPS, description, and timestamp metadata back into the files.

**Syntax:**
```bash
gp-cleaner process takeout --dir TAKEOUT_DIR
```

**Example:**
```bash
gp-cleaner process takeout --dir "/Users/you/Downloads/Takeout/Google Photos"
```

**Handled automatically:**
- Google name truncation (`very_long_photo_n.jpg.json` → `very_long_photo_name.jpg`)
- Supplemental metadata suffixes (`.supp.json`, `.supplemental-metadata.json`)
- Bracket-shift duplicates (`photo.jpg(1).json` → `photo(1).jpg`)
- Double-dot filenames (`photo.jpg..json` → `photo.jpg`)
- Android screenshot formats (`com.miui.gallery_*.jpg`)

**Output logs:**
- `data/json/takeout_match.json` — All matched files and their applied timestamps.
- `data/json/takeout_unmatched.json` — Any JSONs that could not be matched (empty `[]` on a clean run).

---

#### `gp-cleaner process backup`

Matches local photos inside `photos_backUp/` with CSV timestamps and corrects local filesystem dates (`mtime`).

**Syntax:**
```bash
gp-cleaner process backup [--csv [CSV ...]] [--dir [DIR ...]]
```

**Example:**
```bash
gp-cleaner process backup --csv "data/csv/metadata.csv" --dir "data/photos/photos_backUp"
```

---

## 🧠 7. Advanced Mechanics & Algorithms

### Fuzzy Filename Matching (Takeout)

Google Takeout companion JSON files frequently deviate from the original filename. The matching algorithm resolves this via a four-stage fallback chain:

1. **Exact match** — `filename.jpg` → `filename.jpg.json`
2. **Bracket-shift** — `photo(1).jpg` → `photo.jpg(1).json`
3. **Truncation fallback** — `my_long_name.jpg` → `my_long.jpg.json` (prefix match)
4. **Special character normalization** — strips double dots, normalizes extension ordering

### Parallel rclone Execution

Mass rclone commands are parallelized via a sliding-window PID manager rather than sequential subprocesses:

1. All `rclone` actions are written to `logs/rclone_commands_auto.sh`.
2. A Python worker launches up to **10 concurrent background jobs**.
3. Execution progress streams to `logs/rclone_execution.log`.

You can also invoke this helper directly in custom scripts:
```python
from src.sync import run_rclone_commands
run_rclone_commands(list_of_cmd_strings, max_jobs=10)
```

---

## 🛠️ 8. Troubleshooting

### IDE import errors: `Cannot find module src.sync`

**Cause:** Pyright/Pylance cannot resolve the `src` package without an `__init__.py`.

**Resolution:**
- `src/__init__.py` exists and establishes `src` as a proper Python package.
- `pyproject.toml` includes Pyright and Ruff settings that set `pythonPath` and `venvPath`.

---

### `rclone: command not found`

**Cause:** `rclone` is not installed or not on `PATH`.

**Resolution:**
```bash
brew install rclone    # macOS
# Then verify:
rclone --version
```

---

### `exiftool: command not found`

**Cause:** `exiftool` not installed. Tool falls back to filesystem-only date updates (EXIF tags are skipped).

**Resolution:**
```bash
brew install exiftool                        # macOS
sudo apt install libimage-exiftool-perl      # Debian/Ubuntu
```

---

### Drive cache is stale / duplicate uploads occurring

**Cause:** `data/json/drive_index*.json` is outdated.

**Resolution:** Always refresh the cache before running sync commands:
```bash
rclone lsjson -R "gdrive:" > data/json/drive_index.json
rclone lsjson -R "gdrive:photos_backUp" > data/json/drive_index_photo_backUp.json
```
