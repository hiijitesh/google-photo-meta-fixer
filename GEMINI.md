# Google Photos Cleaner - AI Developer Instructions (`GEMINI.md`) 🤖💡

This file outlines the architecture, coding standards, and execution constraints for LLMs modifying or extending the **Google Photos Cleaner** repository. Read this file fully before making any edits.

---

## 🎯 1. Purpose of the Project

The official Google Photos API has strict limitations: it hides storage-quota consumption details, strips GPS metadata, and does not provide access to raw file locations.

This toolkit bypasses those limitations by providing a unified Python-based pipeline to:
1. **Identify space-consuming files** using metadata exported via the browser-level Google Photos Toolkit (GPTK) userscript.
2. **Perform cloud-to-cloud synchronization** on Google Drive via `rclone` (organizing files into backup structures without re-downloading/uploading raw payloads).
3. **Audit and fix photo timestamps** locally (writing to EXIF and system dates) and in the cloud (using `rclone touch` directly on Drive).

---

## 🧱 2. Strict Modular Coding Standards

To keep the repository clean and maintainable, future LLMs must adhere to the following rules:

### ⚠️ **Rule 1: No Standalone Scripts**
* Do **NOT** create new executable scripts (e.g. `run_*.sh`, `*.py`) in the root directory or in `scripts/`.
* Any new functionality must be implemented as helper functions/classes inside the `src/` directory.

### 🔌 **Rule 2: Unified CLI Entrypoint**
* All user actions must be triggered through the main argparse interface in `cleaner.py`.
* When adding a new feature, register it as a subcommand (e.g., `python3 cleaner.py command subcommand --flags`).

### 🎨 **Rule 3: Code Formatting (Black)**
* All Python code must be formatted using the `black` formatter.
* AI developers and LLMs MUST run `black` (e.g., `black src/*.py cleaner.py`) to format all modified or newly created Python code before completing tasks to avoid dirty diffs on save.

### 📁 Directory Layout Checklist
```
.
├── cleaner.py                 # Main CLI entrypoint (argparse interface)
├── src/                       # Core python modules
│   ├── sync.py                # Cloud-to-cloud & local upload rclone logic
│   ├── metadata.py            # Local & Drive timestamp comparison & verification logic
│   └── process_backup.py      # Local file time correction logic
├── data/                      # Contains inputs/caches (Ignored by Git)
│   ├── csv/                   # Input metadata exports from Google Photos Toolkit (GPTK)
│   └── json/                  # Drive file listings (drive_index.json, drive_index_photo_backUp.json)
└── logs/                      # Executables and commands logs (rclone commands lists)
```

---

## ⚡ 3. Rclone Execution & Parallelism Guidelines

When interacting with Google Drive via `rclone`:

1. **Avoid Sequential Subprocesses:** Running hundreds of sequential `rclone` commands inside Python is extremely slow.
2. **Use the Parallel Launcher:** Write mass commands into a shell script and run them in parallel. Import and use the helper:
   ```python
   from src.sync import run_rclone_commands
   run_rclone_commands(list_of_cmd_strings, max_jobs=10)
   ```
   This helper automatically saves logs under `logs/rclone_execution.log`.
3. **Use Native Rclone Parallelism for Bulk Transfers:** When uploading/copying specific lists of files, do not spawn multiple background processes. Instead, write the relative file paths to a manifest file and run a single `rclone copy` command using `--files-from <manifest>`, `--transfers 10`, and `--checkers 16` for native multi-threaded execution.
4. **Use Local JSON Caches (Always Refresh First):** Instead of query-polling the Drive API directly (which leads to rate-limiting), parse the local JSON caches. **CRITICAL:** You must always run `rclone lsjson` to get a fresh, up-to-date index of the remote directory before performing any check or upload task to prevent duplicate uploads or stale data mismatches:
   ```bash
   rclone lsjson -R "jiteshece:photos_backUp" > data/json/drive_index_photo_backUp.json
   ```

---

## 🛠️ 4. Quick Command Reference for LLMs

### File Sync Subcommands
* **Cloud Sync Consuming Photos:** Compare a local metadata CSV with the Drive index and copy missing files cloud-to-cloud into the backup folder:
  ```bash
  python3 cleaner.py sync consuming --csv <csv_path> --remote <remote_name>
  ```
* **Upload Local Photos:** Upload files from a local directory directly into a Drive subfolder, skipping files that are already present in the index cache (avoiding duplicates):
  ```bash
  python3 cleaner.py sync upload-local --dir <local_dir> --dest <dest_folder> --remote <remote_name>
  ```

### Metadata Subcommands
* **Fix Drive Timestamps:** Match local file times with Drive paths and execute `rclone touch` to align them without re-uploading payloads:
  ```bash
  python3 cleaner.py metadata fix-drive --remote <remote_name>
  ```
* **Verify CSV Timestamps:** Audit the EXIF timestamps of local files against the expected datetimes stored in a GPTK CSV metadata export:
  ```bash
  python3 cleaner.py metadata verify-csv --csv <csv_path> --dir <local_dir>
  ```
* **Verify Takeout Timestamps:** Audit the EXIF timestamps and filesystem modification dates of files matching the Google Takeout match log index (`data/json/takeout_match.json`):
  ```bash
  python3 cleaner.py metadata verify-takeout
  ```

### Processing Subcommands
* **Merge Google Takeout JSON Metadata:** Recursively walk a Google Takeout directory to find companion JSON files, match them to their media files, update the EXIF tags (using `exiftool` if installed), and update local filesystem modification times:
  ```bash
  python3 cleaner.py process takeout --dir <takeout_dir>
  ```
