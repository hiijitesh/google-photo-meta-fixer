# 📸 Google Photos → Google Drive Backup & Cleanup Tool

A unified python-based toolkit and React Native companion app to process, sync, and fix timestamps of Google Photos backups on Google Drive using `rclone`. This project is designed to identify and organize **original-quality files** that consume storage quota and manage Google Photos metadata.

---

## ⚙️ Prerequisites

To use this toolkit, you must have `rclone` installed and configured on your system:

1. **Install rclone:** Follow the [rclone installation instructions](https://rclone.org/install/).
2. **Configure your Google Drive remote:** Set up your Google Drive connection by running:
   ```bash
   rclone config
   ```
   Follow the step-by-step prompts to create a new remote (e.g. `gdrive:`). Refer to the official [rclone config command guide](https://rclone.org/commands/rclone_config/) for more details.
3. **Verify configuration:** Make sure you can list your drive contents:
   ```bash
   rclone lsd gdrive:
   ```

To run the React Native Android companion app, you will also need:
* **Node.js** (v18 or higher) and **npm** installed.
* **Expo Go** app installed on your Android device (or an Android emulator configured via Android Studio).

---

## 🚀 High-Level End-User Guide

Follow this standard sequence to backup, audit, and clean up your Google Photos storage:

1. **Install Browser Userscript:**
   - Install the **Tampermonkey** browser extension.
   - Install the [google_photos_toolkit.user.js](file:///Users/hiijitesh/Documents/google-photos-cleaner/google_photos_toolkit.user.js) userscript (located in the root of this repo).
   - Go to [photos.google.com](https://photos.google.com), filter by "Consuming" space / "Original" quality, and click **Export Metadata** to download a CSV file. Place it in `data/csv/`.

2. **Google Drive Sync (Cloud-to-Cloud):**
   - Run the python CLI or the companion Android app to compare your exported CSV metadata against your actual Google Drive.
   - Automatically copy missing files cloud-to-cloud to your backup directory.

3. **Verify & Fix Timestamps:**
   - Run the metadata touch tools to align Drive modification timestamps with your photo's local EXIF/CSV datetimes using `rclone touch` without re-uploading payloads.

4. **Pixel Re-upload & Deletion Workflow (Free Storage Sync):**
   - To safely clean up cloud storage and re-upload original files via Pixel phone, see the [Pixel Re-upload Guide](file:///Users/hiijitesh/Documents/google-photos-cleaner/docs/Pixel_Reupload_Guide.md).

---

## 🏗️ Project Architecture & Code Structure

```
.
├── cleaner.py                 # Main CLI entrypoint (argparse interface)
├── google_photos_toolkit.user.js # Browser userscript for metadata export & Drive sync
├── src/                       # Core python modules
│   ├── sync.py                # Cloud-to-cloud file backup copying logic
│   ├── metadata.py            # Timestamp comparison and Drive fixing via 'rclone touch'
│   └── process_backup.py      # Parses CSV & updates local file modification times
├── android-app/               # React Native/Expo Android companion application
├── data/                      # Contains inputs/caches (Ignored by Git except templates/configs)
│   ├── csv/                   # Input metadata exports from Google Photos Toolkit (GPTK)
│   └── json/                  # Drive file listings (drive_index_photo_backUp.json, etc.)
└── logs/                      # Executables and commands logs (rclone commands lists)
```

---

## 📦 Installation & Packaging

You can install the package directly from PyPI, run it as a local script, or compile it into a standalone executable.

### 1. Install from PyPI (Recommended)
Install the stable release directly:
```bash
pip install google-photo-meta-fixer

# If using externally managed Python environment (e.g. macOS Homebrew)
pip install google-photo-meta-fixer --break-system-packages
```
Once installed, invoke the CLI tool from any directory:
```bash
gp-cleaner [command] [options]
```

### 2. Run Directly as a Script
Run directly from the repository root:
```bash
python3 cleaner.py [command] [options]
```

### 3. Install as a Local CLI Command (From Source)
You can install the tool locally in editable mode:
```bash
# Install in editable mode
pip install -e .

# If using an externally managed environment
pip install -e . --break-system-packages --user
```
Once installed, invoke the tool:
```bash
gp-cleaner [command] [options]
```

### 4. Build a Standalone macOS Executable Binary
To package the app into a single compiled binary:

1. Install PyInstaller:
   ```bash
   pip install pyinstaller --break-system-packages --user
   ```
2. Compile the binary:
   ```bash
   pyinstaller --onefile cleaner.py --name gp-cleaner
   ```
3. Run the standalone binary from the `dist/` directory:
   ```bash
   ./dist/gp-cleaner [command] [options]
   ```

---

## 🔧 CLI Entry Point

All operations are run via `cleaner.py` (or `gp-cleaner` if installed) using positional commands:

### 1. File Synchronization (`sync`)
Handles synchronizing files inside Google Drive (cloud-to-cloud) or uploading missing local folders.

```bash
# Sync original-quality backup photos into year-wise folders
gp-cleaner sync backup --remote gdrive:

# Compare space-consuming CSV metadata against Google Drive index (cloud-to-cloud sync)
# This finds files present on Drive but not in photos_backUp, and copies them to the backup directory
gp-cleaner sync consuming --csv "o consuming album metadata.csv" --remote gdrive:

# Compare a local folder (e.g. GPH OP) against Drive index and upload missing files to a destination folder on Drive
# (Prevents duplicate files and folder structures)
gp-cleaner sync upload-local --dir "data/GPH OP/ALL_PHOTOS" --dest "O Consuming" --remote gdrive:
```

### 2. Metadata & Timestamps (`metadata`)
Identifies, verifies, and fixes timestamp discrepancies between local files, Google Drive, and CSV database reports.

```bash
# Compare local and Drive indices, and execute 'rclone touch' directly on Drive to fix mismatched times
gp-cleaner metadata fix-drive --remote gdrive:

# Fix local photo modification timestamps
gp-cleaner metadata fix-local

# Verify that local photo timestamps (EXIF & modify date) match dates in a Google Photos CSV file
gp-cleaner metadata verify-csv --csv "o consuming album metadata.csv" --dir "data/GPH OP/ALL_PHOTOS"
```

### 3. CSV Processing & Local Organizing (`process`)
Processes local files against GPTK metadata CSVs to extract correct timestamps and write them to the local files system (`os.utime`).

```bash
# Process and update timestamps for local backup photos
gp-cleaner process backup
```

### 4. Google Takeout Metadata Merger (`process takeout`)
Recursively walks a Google Takeout directory to find companion JSON files, extract timestamps, descriptions, and GPS tags, and embed them into the photos/videos.

```bash
# Process and merge Google Takeout directory metadata
gp-cleaner process takeout --dir <takeout_dir>

# Verify Google Takeout metadata updates
gp-cleaner metadata verify-takeout
```

---

## 📱 React Native Android Companion App

The project includes an Expo-based Android companion application located under the `android-app/` directory. This app allows you to:
1. View and index local photo directories.
2. Connect to the Google Photos API to audit large storage-consuming files.
3. Track and verify Google Takeout processing logs directly on your mobile device.

### Running the App:

1. **Install Dependencies:**
   ```bash
   cd android-app
   npm install
   ```

2. **Start the Development Server:**
   ```bash
   npx expo start
   ```

3. **Open on Device:**
   - Scan the QR code displayed in your terminal using the **Expo Go** app on your Android device.
   - Alternatively, press `a` in your terminal to open it in a running Android emulator.

---

## 🧠 Core System Design & Workflow

### 1. Data Source (Google Photos Toolkit)
Because the official Google Photos API strips GPS/EXIF metadata and hides the `takesUpSpace` attribute, this toolkit relies on the **Google Photos Toolkit (GPTK)** userscript ([google_photos_toolkit.user.js](file:///Users/hiijitesh/Documents/google-photos-cleaner/google_photos_toolkit.user.js) in the root).
1. Run the userscript in Tampermonkey on [photos.google.com](https://photos.google.com).
2. Filter for "Consuming" space and "Original" quality.
3. Click "Export Metadata" to get `metadata.csv`.
4. Save the files under `data/csv/`.

### 2. Google Drive Indexing
We index files on Google Drive using `rclone` to avoid querying the API repeatedly:
```bash
rclone lsjson -R "gdrive:photos_backUp" > data/json/drive_index_photo_backUp.json
```

### 3. Local Comparison & Cloud Execution
1. The script loads the local files (`data/photos/photos_backUp`) and indexes their sizes and modification times.
2. It compares them to the cached `drive_index_photo_backUp.json`.
3. If timestamps mismatch (e.g., due to timezone shifts or upload bugs), the `metadata fix-drive` command uses `rclone touch` to adjust the remote file's modified time without re-uploading the file payload.

### 4. Google Takeout Metadata Merger & Matching Logic
For a complete guide of the algorithms, code snippets, and design choices behind this feature, see [LEARNING.md](file:///Users/hiijitesh/Documents/google-photos-cleaner/LEARNING.md). Below is a summary of the core concepts:
- **Fuzzy Filename Matching:** Resolves Takeout quirks such as name truncations, supplemental suffixes (e.g. `.supplemental-metadata.json`, `.supp.json`), double dots (`..json`), and duplicate bracket shifts (e.g. `photo.jpg(1).json` matching `photo(1).jpg`).
- **Batch Exiftool Operations:** Minimizes process startup overhead by writing all modifications to a single temporary JSON and importing it in one command using `exiftool -json=temp.json -@ files.txt`.
- **Filesystem Date Correction:** Updates the filesystem `mtime` using Python's `os.utime()` to match the JSON's true epoch timestamp (seconds since epoch) so that Finder and File Explorer sort photos chronologically.

---

## ⚠️ Important Rules for AI Developers
- **No Standalone Scripts**: Do not create new top-level `run_*.sh` or `*.py` scripts in the root or `scripts/`. Always implement logic as functions inside the `src/` modules and register them as subcommands in `cleaner.py`.
- **Paths**: Keep paths relative to the workspace. Local raw photo directories are typically ignored by git (e.g., `data/photos/`).
- **Parallelism**: When generating mass `rclone` commands, write the commands to `logs/` and execute them concurrently via `run_rclone_commands` in `src/sync.py` to optimize speed.
