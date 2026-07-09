# 📸 Google Photo Meta Fixer (GPMF)

A unified CLI toolkit and React Native companion app to process, sync, and fix timestamps of Google Photos backups on Google Drive using `rclone`. 

Identify and organize **original-quality files** that consume storage quota and fix photo metadata discrepancies safely.

---

## 🔄 High-Level Storage Saving Workflow

To identify and migrate space-consuming original images from Google Photos:

1. **Filter & Group:** Use the [Google Photos Toolkit](https://github.com/xob0t/Google-Photos-Toolkit) userscript in your browser to find original-quality / storage-consuming photos, and **add them to a new Google Photos album**.
2. **Export Metadata:** Use the toolkit to export the album's metadata as a **CSV file** and save it under `data/csv/`.
3. **Download via Takeout:** Download the photos in that album using **Google Takeout** and extract the folder.
4. **Fix Takeout Metadata:** Run `gp-cleaner process takeout` on the extracted folder to merge companion JSON metadata, restoring the true epoch timestamps into EXIF headers and filesystem dates.
5. **Sync & Compare:** Use the `gp-cleaner sync` commands to compare your metadata CSV against Google Drive and sync/copy files cloud-to-cloud without duplicates.

---

## 🚀 Quick Start Guide

Follow these simple steps to set up and run the tool:

### Step 1: Install prerequisites
1. **Install rclone:** Follow the [rclone installation instructions](https://rclone.org/install/).
2. **Configure your Google Drive remote:** Run `rclone config` to link your Google Drive (e.g. name the remote `gdrive:`).

### Step 2: Install this package
Install directly from PyPI:
```bash
pip install google-photo-meta-fixer

# For macOS (Homebrew managed python) or Linux environments:
pip install google-photo-meta-fixer --break-system-packages
```

### Step 3: Export your Google Photos metadata
1. Install the **Tampermonkey** browser extension.
2. Install the userscript from the official [Google Photos Toolkit](https://github.com/xob0t/Google-Photos-Toolkit) repository.
3. Open [photos.google.com](https://photos.google.com) in your browser.
4. Filter by "Consuming" space / "Original" quality, and click **Export Metadata** to download a CSV file.
5. Save the CSV file locally in `data/csv/`.

### Step 4: Run the synchronization
Compare your metadata CSV file against your Google Drive index to identify original-quality backup files and sync them cloud-to-cloud:
```bash
gp-cleaner sync consuming --csv "data/csv/your_metadata.csv" --remote gdrive:
```

### Step 5: Fix timestamps in Google Drive (Optional)
Align your Google Drive file modification dates with the original photo datetimes without downloading/uploading payloads (only needed if you want to fix timestamps of pre-existing files on Drive):
```bash
gp-cleaner metadata fix-drive --remote gdrive:
```

---

## 📱 React Native Android Companion App

The repository includes a mobile companion app under the `android-app/` directory.

To run it:
1. Ensure **Node.js** (v18+) is installed.
2. Navigate to the directory and install dependencies:
   ```bash
   cd android-app
   npm install
   ```
3. Start Expo:
   ```bash
   npx expo start
   ```
4. Scan the QR code with the **Expo Go** app on your Android device to run the app.

---

## 🔧 CLI Command Reference

All operations are run via the `gp-cleaner` CLI command:

| Command | Action | Description |
|---|---|---|
| `gp-cleaner sync backup` | Cloud sync | Syncs backup photos into year-wise folders on Drive. |
| `gp-cleaner sync consuming` | Cloud copy | Compares CSV metadata and copies storage-consuming files. |
| `gp-cleaner sync upload-local` | Upload | Compares local folder and uploads missing files to Drive. |
| `gp-cleaner metadata fix-drive` | Fix Cloud dates | Updates remote file modification dates on Drive. |
| `gp-cleaner metadata fix-local` | Fix Local dates | Updates EXIF headers and local filesystem timestamps. |
| `gp-cleaner process takeout` | Takeout merge | Walks Google Takeout directories and merges JSON metadata. |

For detailed commands, arguments, and advanced options, see the [CLI Reference Guide](cli_reference_guide.md).

---

## 🛠️ Developers & Contributors

* For system design guidelines, codebase architecture, and coding rules, see [GEMINI.md](GEMINI.md).
* For detailed algorithm explanations of Google Takeout matching logic, see [LEARNING.md](LEARNING.md).
