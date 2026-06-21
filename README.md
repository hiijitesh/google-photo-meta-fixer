# 📸 Google Photos → Google Drive Backup & Cleanup Tool

A unified python-based toolkit to process, sync, and fix timestamps of Google Photos backups on Google Drive using `rclone`. This project is designed to identify and organize **original-quality files** that consume storage quota and manage Google Photos metadata.

> [!NOTE]
> **LLM Context**: This file serves as the primary system architectural overview. Read this first to understand the codebase structure, directory layout, and entry points before making changes.

---

## 🏗️ Project Architecture & Code Structure

The project has been refactored from a collection of single-purpose scripts into a consolidated Python application with a unified CLI entry point.

```
.
├── cleaner.py                 # Main CLI entrypoint (argparse interface)
├── src/                       # Core python modules
│   ├── sync.py                # Cloud-to-cloud file backup/trash copying logic
│   ├── metadata.py            # Timestamp comparison and Drive fixing via 'rclone touch'
│   ├── process_backup.py      # Parses CSV & updates local file modification times
│   └── process_trash.py       # Parses trash CSV & updates local trash mtimes
├── js/
│   └── extract_photos.js      # Chrome browser toolkit userscript helper
├── data/                      # Contains inputs/caches (Ignored by Git except template/configs)
│   ├── csv/                   # Input metadata exports from Google Photos Toolkit (GPTK)
│   └── json/                  # Drive file listings (drive_index_photo_backUp.json, etc.)
└── logs/                      # Executables and commands logs (rclone commands lists)
```

---

## 🔧 CLI Entry Point (`cleaner.py`)

All operations are run via `cleaner.py` using positional commands:

### 1. File Synchronization (`sync`)
Handles synchronizing files inside Google Drive (cloud-to-cloud) or uploading missing local folders.

```bash
# Sync original-quality backup photos into year-wise folders
python3 cleaner.py sync backup --remote jiteshece:

# Sync recovered Google Photos trash files into organized subfolders
python3 cleaner.py sync trash --remote jiteshece:

# Compare space-consuming CSV metadata against Google Drive index (cloud-to-cloud sync)
# This finds files present on Drive but not in photos_backUp, and copies them to the backup directory
python3 cleaner.py sync consuming --csv "o consuming album metadata.csv" --remote jiteshece:

# Compare a local folder (e.g. GPH OP) against Drive index and upload missing files to a destination folder on Drive
# (Prevents duplicate files and folder structures)
python3 cleaner.py sync upload-local --dir "data/GPH OP/ALL_PHOTOS" --dest "O Consuming" --remote jiteshece:
```

### 2. Metadata & Timestamps (`metadata`)
Identifies, verifies, and fixes timestamp discrepancies between local files, Google Drive, and CSV database reports.

```bash
# Compare local and Drive indices, and execute 'rclone touch' directly on Drive to fix mismatched times
python3 cleaner.py metadata fix-drive --remote jiteshece:

# Fix local photo modification timestamps
python3 cleaner.py metadata fix-local

# Verify that local photo timestamps (EXIF & modify date) match dates in a Google Photos CSV file
python3 cleaner.py metadata verify-csv --csv "o consuming album metadata.csv" --dir "data/GPH OP/ALL_PHOTOS"
```

### 3. CSV Processing & Local Organizing (`process`)
Processes local files against GPTK metadata CSVs to extract correct timestamps and write them to the local files system (`os.utime`).

```bash
# Process and update timestamps for local backup photos
python3 cleaner.py process backup

# Process and update timestamps for local trashed photos
python3 cleaner.py process trash
```

---

## 🧠 Core System Design & Workflow

### 1. Data Source (Google Photos Toolkit)
Because the official Google Photos API strips GPS/EXIF metadata and hides the `takesUpSpace` attribute, this toolkit relies on the **Google Photos Toolkit (GPTK)** userscript (`js/extract_photos.js`).
1. Run the userscript in Tampermonkey on [photos.google.com](https://photos.google.com).
2. Filter for "Consuming" space and "Original" quality.
3. Click "Export Metadata" to get `metadata.csv` (or `trash_metadata_completed.csv` for trashed items).
4. Save the files under `data/csv/`.

### 2. Google Drive Indexing
We index files on Google Drive using `rclone` to avoid querying the API repeatedly:
```bash
rclone lsjson -R "jiteshece:photos_backUp" > data/json/drive_index_photo_backUp.json
```

### 3. Local Comparison & Cloud Execution
1. The script loads the local files (`data/photos/photos_backUp`) and indexes their sizes and modification times.
2. It compares them to the cached `drive_index_photo_backUp.json`.
3. If timestamps mismatch (e.g., due to timezone shifts or upload bugs), the `metadata fix-drive` command uses `rclone touch` to adjust the remote file's modified time without re-uploading the file payload.

---

## ⚠️ Important Rules for AI Developers
- **No Standalone Scripts**: Do not create new top-level `run_*.sh` or `*.py` scripts in the root or `scripts/`. Always implement logic as functions inside the `src/` modules and register them as subcommands in `cleaner.py`.
- **Paths**: Keep paths relative to the workspace. Local raw photo directories are typically ignored by git (e.g., `data/photos/`).
- **Parallelism**: When generating mass `rclone` commands, write the commands to `logs/` and execute them concurrently via `run_rclone_commands` in `src/sync.py` to optimize speed.
