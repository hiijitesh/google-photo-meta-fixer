# 📸 Google Photo Meta Fixer (GPMF)

> A unified CLI toolkit and React Native companion app to audit, restore, and sync Google Photos metadata — without re-uploading a single byte.

[![PyPI](https://img.shields.io/pypi/v/google-photo-meta-fixer)](https://pypi.org/project/google-photo-meta-fixer/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![rclone](https://img.shields.io/badge/requires-rclone-orange)](https://rclone.org/)

---

## 📖 Overview

The official Google Photos API hides storage quota details, strips GPS metadata, and provides no access to raw file locations. **Google Photo Meta Fixer** (GPMF) bypasses these limitations by providing:

| Capability | Description |
|---|---|
| 🔍 **Metadata Audit** | Identify original-quality files consuming storage quota |
| 🕐 **Timestamp Restoration** | Write correct EXIF dates from Takeout JSON or GPTK CSV |
| ☁️ **Cloud-to-Cloud Sync** | Copy files across Google Drive without downloading/uploading payloads |
| ✅ **Verification** | Audit local files against CSV or Takeout match logs |

---

## 🔄 High-Level Workflow

To identify, fix, and optionally back up your original-quality Google Photos:

1. **Filter & Group:** Use the [Google Photos Toolkit](https://github.com/xob0t/Google-Photos-Toolkit) userscript in your browser  with [Tampermonkey](https://www.tampermonkey.net/)to find original-quality / storage-consuming photos, and **add them to a new Google Photos album**.
2. **Export Metadata:** Use the toolkit to export the album's metadata as a **CSV file** and save it under `data/csv/`.
3. **Download Files:** Choose one of two ways to download your photos:
   - **Direct Browser Download** — Downloads photos directly from the Google Photos browser page.
   - **Google Takeout** — Downloads the album with companion JSON sidecar files containing GPS, descriptions, and timestamps.
4. **Fix Local Metadata:**
   - **For Browser Downloads:** `gp-cleaner metadata fix-local --csv <csv_path> --dir <photos_dir>`
   - **For Takeout Downloads:** `gp-cleaner process takeout --dir <takeout_dir>`
5. **Sync to Drive (Optional):** Use `gp-cleaner sync` commands to compare your CSV against Google Drive and copy files cloud-to-cloud without duplicates.

---

## 🚀 Quick Start Guide

### Step 1: Install prerequisites

1. **Install rclone:** Follow the [rclone installation instructions](https://rclone.org/install/).
2. **Configure your Google Drive remote:** Run `rclone config` to link your Google Drive (e.g. name the remote `gdrive:`).
3. **Install exiftool** (required for EXIF writes):
   ```bash
   brew install exiftool        # macOS
   sudo apt install libimage-exiftool-perl  # Debian/Ubuntu
   ```

### Step 2: Install this package

```bash
pip install google-photo-meta-fixer

# For macOS (Homebrew managed Python) or Linux:
pip install google-photo-meta-fixer --break-system-packages
```

### Step 3: Export your Google Photos metadata

1. Install the [**Tampermonkey**](https://www.tampermonkey.net/) browser extension.
2. Install the userscript from the official [Google Photos Toolkit](https://github.com/xob0t/Google-Photos-Toolkit) repository.
3. Open [photos.google.com](https://photos.google.com) in your browser.
4. Filter by **"Consuming"** space / **"Original"** quality, and click **Export Metadata** to download a CSV file.
5. Save the CSV file locally in `data/csv/`.

### Step 4: Fix local metadata

**Option A — Browser-downloaded photos:** Write correct timestamps from CSV into EXIF headers and filesystem dates:
```bash
gp-cleaner metadata fix-local --csv "data/csv/your_metadata.csv" --dir "path/to/photos"
```

**Option B — Google Takeout photos:** Merge sidecar JSON metadata files back into your photos:
```bash
gp-cleaner process takeout --dir "path/to/takeout_folder"
```

> **Tip:** Optionally verify that all timestamps were written correctly:
> ```bash
> gp-cleaner metadata verify-csv --csv "data/csv/your_metadata.csv" --dir "path/to/photos"
> ```

### Step 5: Run the synchronization (Optional)

Compare your metadata CSV against your Google Drive index and sync storage-consuming files cloud-to-cloud:
```bash
gp-cleaner sync consuming --csv "data/csv/your_metadata.csv" --remote gdrive:
```

### Step 6: Fix timestamps in Google Drive (Optional)

Align remote file modification dates with original photo datetimes via `rclone touch` — no payload re-upload:
```bash
gp-cleaner metadata fix-drive --remote gdrive:
```

---

## 🔧 CLI Command Reference

All operations are triggered via the `gp-cleaner` CLI:

| Command | Action | Description |
|---|---|---|
| `gp-cleaner sync backup` | Cloud sync | Syncs backup photos into year-wise folders on Drive. |
| `gp-cleaner sync consuming` | Cloud copy | Compares CSV metadata and copies storage-consuming files. |
| `gp-cleaner sync upload-local` | Upload | Compares local folder and uploads missing files to Drive. |
| `gp-cleaner metadata fix-local` | Fix local dates | Writes EXIF headers and filesystem timestamps from CSV. |
| `gp-cleaner metadata fix-drive` | Fix cloud dates | Updates remote file modification dates on Drive. |
| `gp-cleaner metadata verify-csv` | Audit CSV | Audits local EXIF timestamps against a GPTK CSV export. |
| `gp-cleaner metadata verify-takeout` | Audit Takeout | Audits local files against the Takeout match log. |
| `gp-cleaner process takeout` | Takeout merge | Walks Google Takeout directories and merges JSON metadata. |
| `gp-cleaner process recover-timezone` | Recover timezone | Force shifts timestamps on already modified local photos to a specific timezone. |

For full argument details and advanced options, see the [CLI Reference Guide](cli_reference_guide.md).

---

## 🛠️ Developers & Contributors

- For system design guidelines, codebase architecture, and AI coding rules, see [GEMINI.md](GEMINI.md).
- For deep dives into the Google Takeout fuzzy matching algorithm, see [LEARNING.md](LEARNING.md).
- For the Takeout metadata merger guide, see [JSON_MERGER.md](JSON_MERGER.md).

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
4. Scan the QR code with the **Expo Go** app on your Android device.
