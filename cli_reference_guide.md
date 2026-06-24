# Google Photos Cleaner - Ultimate CLI Reference Guide 📸💻

This guide provides deep technical documentation, usage examples, workflow descriptions, and troubleshooting guides for the **Google Photos Cleaner** tool.

---

## 🚀 1. High-Level Customer Workflow
To back up and clean up your Google Photos metadata, follow these standard command sequences:

### 📂 Google Takeout Workflow (In Order)
If you are processing photos exported via **Google Takeout**:
1.  **Merge Metadata JSONs into Photos:**
    Updates EXIF headers and filesystem dates for all photos/videos and companion videos matching a Takeout JSON:
    ```bash
    gp-cleaner process takeout --dir "/path/to/Takeout"
    ```
2.  **Verify Takeout Merger:**
    Audits the updated folders to ensure EXIF headers and filesystem timestamps are correct:
    ```bash
    gp-cleaner metadata verify-takeout
    ```
3.  **Verify Takeout Photos Against CSV (Optional):**
    If you also have a custom browser CSV export, audit the Takeout photos against the CSV to confirm alignment:
    ```bash
    gp-cleaner metadata verify-csv --csv "path/to/metadata.csv" --dir "/path/to/Takeout/Google Photos/Album"
    ```

### 📊 GPTK Browser CSV Workflow (In Order)
If you are processing space-consuming photos and using a browser-level **GPTK CSV** metadata export:
1.  **Sync Consuming Photos (Cloud-to-Cloud):**
    Identifies space-consuming files from your CSV and copies them cloud-to-cloud into your backup folder:
    ```bash
    gp-cleaner sync consuming --csv "path/to/metadata.csv" --remote gdrive:
    ```
2.  **Fix Local Photo Timestamps (EXIF + Filesystem):**
    Matches downloaded photos to your CSV and writes the correct timestamps into both the EXIF headers and filesystem dates:
    ```bash
    gp-cleaner metadata fix-local --csv "path/to/metadata.csv" --dir "/path/to/photos"
    ```
3.  **Verify Local Timestamps Against CSV:**
    Audits the folder to check if local photo times match the CSV:
    ```bash
    gp-cleaner metadata verify-csv --csv "path/to/metadata.csv" --dir "/path/to/photos"
    ```
4.  **Fix Drive Timestamps:**
    Compares local timestamps against Google Drive files and aligns the remote timestamps via `rclone touch`:
    ```bash
    gp-cleaner metadata fix-drive --remote gdrive:
    ```

---

## ⚙️ 2. Prerequisites & Rclone Configuration

Because this tool performs cloud-to-cloud operations and metadata touching directly on Google Drive, you must configure `rclone` before running the commands.

### A. Install rclone
Ensure `rclone` is installed on your macOS:
```bash
brew install rclone
```

### B. Configure your Google Drive Remote
1. Launch the interactive configuration wizard:
   ```bash
   rclone config
   ```
2. Follow these prompts to set up a new remote:
   *   Select `n` for **New remote**.
   *   Name the remote (e.g., `gdrive`).
   *   Select **Google Drive** (number in the list, e.g., `18`).
   *   Leave `client_id` and `client_secret` blank (to use defaults), or supply your own Google API Console credentials for faster speeds.
   *   Set the scope to `1` (**Full access to all files**).
   *   Leave the root folder ID and service account file blank.
   *   Allow auto-config (choose `y` to open the web browser and authorize).
   *   Confirm the remote definition is correct.
3. **Verify the connection:**
   Make sure rclone can list your remote root:
   ```bash
   rclone lsd gdrive:
   ```

---

## 📦 3. Installation & Executable Options

### Method A: Standalone macOS Compiled Binary (Recommended)
You can compile a single-file executable binary that doesn't depend on system Python installations:
```bash
# Install PyInstaller
pip install pyinstaller --break-system-packages --user

# Compile the standalone binary
pyinstaller --onefile cleaner.py --name gp-cleaner

# Execute the binary directly
./dist/gp-cleaner [command] [options]
```

### Method B: Locally Installed Python Package
Install the project as an editable command (`gp-cleaner`):
```bash
pip install -e . --break-system-packages --user
```
Add the Python user bin directory to your `~/.zshrc` path:
```bash
export PATH="$PATH:$HOME/Library/Python/3.14/bin"
```
Once configured, run the tool globally from any directory:
```bash
gp-cleaner [command] [options]
```

---

## 📊 4. Google Photos Toolkit (GPTK) CSV Specification

The `sync consuming`, `process backup`, and `metadata verify-csv` commands parse metadata CSV files exported from the browser-level Google Photos Toolkit userscript.

The tool inspects the following columns:

| Column Name | Type | Description |
| :--- | :--- | :--- |
| `fileName` | String | The exact name of the file (e.g., `IMG_20210728_123456.jpg`). |
| `takenAt` | String | UTC ISO 8601 creation timestamp (e.g., `2021-07-28T06:54:29.891Z`). |
| `timezoneOffsetMs` | Integer | Local timezone offset in milliseconds (e.g., `19800000` for IST +05:30). |
| `takesUpSpace` | Boolean | True if the photo consumes Google storage quota (Original Quality). |
| `isOriginalQuality`| Boolean | True if the file has not been compressed by Google's "Storage Saver". |
| `durationMs` | Integer | Present on video files; used to distinguish photos from video categories. |

---

## ⚡ 5. Automatic Cache Refreshing Flow

To prevent hitting Google Drive API rate-limiting thresholds, the tool reads local index files (`data/json/drive_index.json` and `data/json/drive_index_photo_backUp.json`).

Before executing any sync or cloud-metadata subcommand, the tool prompts you to refresh the cache:
1.  **Prompt:** `Do you want to refresh the Google Drive index cache (drive_index.json)? (y/n) [y]:`
2.  If you enter **`y` (or press Enter)**:
    *   The tool runs `rclone lsjson -R "gdrive:"` to fetch all file nodes.
    *   It overwrites the local cache JSON file.
3.  If you enter **`n`**:
    *   The tool skips the network scan and immediately reads the existing local cache file (executing in under a second).

---

## 🛠️ 6. Subcommand Reference & Workflows

### 📂 6.1 The `sync` Commands

#### 🔹 `gp-cleaner sync backup`
*   **Purpose:** Copies original quality photos from the general Drive index into organized year-wise folders cloud-to-cloud.
*   **Workflow:**
    1.  Prompts to refresh `drive_index.json`.
    2.  Loads `data/csv/metadata.csv`.
    3.  Filters for rows where `takesUpSpace == "true"` and `isOriginalQuality == "true"`.
    4.  Looks up each file in the Drive index to find its current path.
    5.  Generates `rclone copyto` commands to move files to `photos_backUp/[Year]/[fileName]`.
    6.  Runs commands in parallel.
*   **Syntax:**
    ```bash
    gp-cleaner sync backup [--remote REMOTE_NAME]
    ```



#### 🔹 `gp-cleaner sync consuming`
*   **Purpose:** Finds original quality photos listed in a CSV that exist on Drive but are missing from the `photos_backUp/` folder, and copies them to the backup folder cloud-to-cloud.
*   **Syntax:**
    ```bash
    gp-cleaner sync consuming --csv CSV_PATH [--remote REMOTE_NAME]
    ```
*   **Example:**
    ```bash
    gp-cleaner sync consuming --csv "data/csv/o consuming album metadata.csv" --remote gdrive:
    ```

#### 🔹 `gp-cleaner sync upload-local`
*   **Purpose:** Checks local folder files against the remote Drive index and uploads files that are missing.
*   **Workflow:**
    1.  Prompts to refresh `drive_index_photo_backUp.json`.
    2.  Scans the local directory and computes the relative paths of all files.
    3.  Identifies files that are not registered in the Drive backup cache.
    4.  Writes missing relative paths to `logs/upload_manifest.txt`.
    5.  Runs a single optimized multi-threaded `rclone copy` command using `--files-from logs/upload_manifest.txt`.
*   **Syntax:**
    ```bash
    gp-cleaner sync upload-local --dir LOCAL_DIR --dest DEST_FOLDER [--remote REMOTE_NAME]
    ```
*   **Example:**
    ```bash
    gp-cleaner sync upload-local --dir "data/photos/GPH OP" --dest "O Consuming"
    ```

---

### 🔍 6.2 The `metadata` Commands

#### 🔹 `gp-cleaner metadata fix-drive`
*   **Purpose:** Directly corrects mismatched remote file modification dates on Google Drive to align with local files using `rclone touch`. No payload is re-uploaded.
*   **Workflow:**
    1.  Prompts to refresh `drive_index_photo_backUp.json`.
    2.  Scans both `data/photos/photos_backUp` and `data/photos/Trashed Photos-3-001` for local files.
    3.  Compares each Drive file's `ModTime` with the corresponding local file's `mtime`.
    4.  Generates `rclone touch --timestamp` commands for all files with a drift greater than 2 seconds.
    5.  Prompts you to confirm before executing.
*   **Syntax:**
    ```bash
    gp-cleaner metadata fix-drive [--remote REMOTE_NAME]
    ```

#### 🔹 `gp-cleaner metadata fix-local`
*   **Purpose:** Reads a GPTK metadata CSV and writes the correct `takenAt` timestamps directly into each local photo's EXIF headers (`DateTimeOriginal`, `CreateDate`, `ModifyDate`) **and** updates its filesystem modification time (`mtime`). Use this after downloading files locally to ensure dates are accurate before re-uploading.
*   **Workflow:**
    1.  Reads all entries from the given CSV file.
    2.  Walks the local `--dir` directory to find all media files.
    3.  Matches each file to its CSV row by filename (with fuzzy `-edited` / truncation tolerance).
    4.  Updates filesystem `mtime` via `os.utime` for all matched files.
    5.  If `exiftool` is installed, batch-writes EXIF date tags for all matched files.
    6.  Reports a summary of matched vs unmatched files.
*   **Syntax:**
    ```bash
    gp-cleaner metadata fix-local --csv CSV_PATH --dir LOCAL_DIR
    ```
*   **Example:**
    ```bash
    gp-cleaner metadata fix-local --csv "data/csv/T2-hiijitesh.csv" --dir "data/photos/GPH OP"
    ```
*   **Requirements:** `exiftool` must be installed for EXIF header writes (`brew install exiftool`). Filesystem timestamps are always updated regardless.

#### 🔹 `gp-cleaner metadata verify-csv`
*   **Purpose:** Checks local photo files against a CSV file to verify if local filesystem `mtime` and EXIF creation tags match the expected `takenAt` timestamps.
*   **Options:**
    | Flag | Description |
    | :--- | :--- |
    | `--csv CSV_PATH` | Path to the GPTK metadata CSV file. |
    | `--dir LOCAL_DIR` | Directory containing photos to audit. |
    | `--show-missing` | Print the full list of files missing from the directory **and** extra files not in the CSV. |
*   **Syntax:**
    ```bash
    gp-cleaner metadata verify-csv --csv CSV_PATH --dir LOCAL_DIR [--show-missing]
    ```
*   **Example:**
    ```bash
    gp-cleaner metadata verify-csv --csv "data/csv/T2-hiijitesh.csv" --dir "data/photos/photos_backUp" --show-missing
    ```

#### 🔹 `gp-cleaner metadata verify-takeout`
*   **Purpose:** Audits files processed via Google Takeout against `data/json/takeout_match.json` to confirm filesystem dates and EXIF tags were successfully written.
*   **Syntax:**
    ```bash
    gp-cleaner metadata verify-takeout
    ```

---

### ⚙️ 6.3 The `process` Commands

#### 🔹 `gp-cleaner process backup`
*   **Purpose:** Matches local photos inside `photos_backUp/` with CSV timestamps and corrects local filesystem dates (`mtime`).
*   **Syntax:**
    ```bash
    gp-cleaner process backup [--csv [CSV ...]] [--dir [DIR ...]]
    ```
*   **Example:**
    ```bash
    gp-cleaner process backup --csv "data/csv/metadata.csv" --dir "data/photos/photos_backUp"
    ```



#### 🔹 `gp-cleaner process takeout`
*   **Purpose:** Matches companion JSON metadata files to photos/videos in a Google Takeout folder and updates EXIF headers and filesystem modification times.
*   **Syntax:**
    ```bash
    gp-cleaner process takeout --dir TAKEOUT_DIR
    ```
*   **Example:**
    ```bash
    gp-cleaner process takeout --dir "/Users/hiijitesh/Downloads/Takeout"
    ```

---

## 🧠 7. Advanced Mechanics & Algorithms

### A. Fuzzy Filename Matching (Google Takeout)
Google Takeout companion JSON files often suffix filenames or truncate characters (e.g. `my_extremely_long_photo_name.jpg` matching `my_extremely_long_photo_n.jpg.json`).
The matching algorithm resolves these using:
1.  **Direct match:** File matches `[filename].json` or `[filename](1).json` directly.
2.  **Truncation fallback:** Checks if the JSON name starts with the truncated filename prefix.
3.  **Special characters removal:** Normalizes name shifts, double dots, and bracket increments.

### B. Parallel Rclone Command execution
Instead of calling `subprocess.run` sequentially hundreds of times (which adds severe process overhead), the tool:
1.  Writes all `rclone` actions into a shell script file at `logs/rclone_commands_auto.sh`.
2.  Uses shell job controls (a sliding window of background PIDs) to launch up to 10 commands in parallel.
3.  Streams logs to `logs/rclone_execution.log`.

---

## 🛠️ 8. Troubleshooting

### Linter Warning: `Cannot find module src.sync`
*   **Symptoms:** IDE language servers (like Pyright or Pylance) display import errors under lines like `from src.sync import ...`.
*   **Fixes implemented:**
    1.  An empty `src/__init__.py` has been created, establishing `src` as a proper Python package.
    2.  `pyproject.toml` has been updated with settings for `pyright` and `ruff`.
    3.  A symbolic link `src/src` has been created pointing to `src/` (`.`). The linter resolves the import path seamlessly.
