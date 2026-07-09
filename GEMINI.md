# Google Photo Meta Fixer - AI Developer Instructions (`GEMINI.md`) 🤖💡

This file outlines the architecture, coding standards, and execution constraints for LLMs modifying or extending the **Google Photo Meta Fixer** repository. Read this file fully before making any edits.

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
   rclone lsjson -R "gdrive:photos_backUp" > data/json/drive_index_photo_backUp.json
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

---

## 📱 5. Android & React Native Sub-Project Guidelines

# React Native Android: First Principles

> [!NOTE]
> Your goal is to bridge declarative JavaScript to native Android UI without congestion. Maximize UI thread performance, respect Android hardware constraints, and maintain strict type safety.

## 1. The Big Picture

React Native does not draw pixels directly. It calculates a component tree in JavaScript and passes layout instructions to native Android views.

Performance degrades when the communication layer is congested. Fast apps keep the JS thread lean and run UI updates natively.

## 2. How It Works: Mental Models

### The Two Threads
- **JS Thread:** Handles React lifecycle, state updates, and business logic.
- **UI Thread (Main):** Handles drawing views and receiving touch events.
*Trap:* Executing heavy compute (like large JSON parsing) on the JS thread drops UI frames and causes stuttering.

### Communication
Data must travel between JS and native Android code.
*Intuition:* Avoid passing large datasets back and forth. Keep data and intensive processing as close to the native layer as possible.

## 3. How to Apply It: Directives

### Architecture & State
- **Structure:** Group by feature (e.g., `/features/auth`), not by technical type (`/components`, `/hooks`). This minimizes cognitive load and keeps context local.
- **State:** Keep state localized. Use React Context for scoped UI state and Zustand for lightweight global state. Predictable state yields predictable renders.

### Android-Specific Mechanics
- **Hardware Back Button:** Always implement `BackHandler`. Native Android users intuitively use the physical back button to navigate or close modals. If unhandled, the app will unexpectedly exit.
- **Keyboard:** Android handles keyboard offsets differently than iOS. Use `KeyboardAvoidingView` with `behavior="height"` for Android.
- **Safe Area:** Device screens have diverse notches and punch-holes. Use `react-native-safe-area-context` to safely pad headers and bottom bars.

### Performance & Memory
- **Lists:** Default to `FlashList` (Shopify). If `FlatList` is strictly required, define `getItemLayout` for fixed-size items to eliminate expensive measurement calculations.
- **Animations:** Use Reanimated 3. All continuous animations must run purely on the UI thread (`runOnUI`) to avoid JS thread blockage.
- **Images:** Use `react-native-fast-image` for aggressive caching and efficient memory usage on constrained Android devices.

## 4. Verification Checklist

Before finalizing any module, verify:
1. Are all TypeScript props and state strictly typed without using `any`?
2. Are heavy computations memoized with `useMemo`?
3. Is `StyleSheet.create` placed completely outside the component to prevent re-allocation on every render?
4. Are touch targets at least 48x48 dp for Material Design compliance?
