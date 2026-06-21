# Guide: Google Takeout Metadata Merger

This subcommand recursively crawls a Google Takeout export directory, matches companion JSON metadata files to their respective photos/videos, and writes the photo taken times, descriptions, and GPS tags back into the files.

---

## ⚡ Quick Start

### 1. Install Exiftool (Required for EXIF/GPS tags)
To write metadata directly inside photo and video files, make sure `exiftool` is installed on your machine:
```bash
brew install exiftool
```
*(If `exiftool` is not installed, the tool will fall back to correcting only the filesystem modified dates).*

### 2. Run the Command
Run the command on your unzipped Google Takeout folder. Remember to **wrap the directory path in double quotes** if it contains spaces:
```bash
python3 cleaner.py process takeout --dir "/Users/hiijitesh/Downloads/Takeout/Google Photos"
```

### 3. Verify the Merger
You can run the built-in verification tool at any time to audit the updated files against the match log and confirm that everything matches perfectly (both in filesystem timestamps and EXIF headers):
```bash
python3 cleaner.py metadata verify-takeout
```

---

## 🛠️ Features & Quirks Handled Automatically
You don't need to rename or clean up anything beforehand. The script automatically handles:
1. **Google Name Truncation:** Resolves cases where Google shortened a JSON name (e.g. matching `very_long_name_trun.jpg.json` with `very_long_name_truncated.jpg`).
2. **Supplemental Metadata:** Matches `.supp.json` and `.supplemental-metadata.json` suffixes back to their original images.
3. **Bracket Shift Duplicates:** Matches shifted numbers (e.g. matching `photo.jpg(1).json` with `photo(1).jpg`).
4. **Double Dots:** Cleans up duplicate dots (e.g. matching `photo.jpg..json` with `photo.jpg`).
5. **Android Package Formats:** Safely matches Android screenshots containing dots (e.g. `com.miui.gallery`).
6. **UTC to Offset Handling:** Reads UTC timestamps from the JSON and properly translates them into Exif tags.

---

## 📋 Log Locations
After execution, the script generates two index summaries in the `data/json/` directory:
* **[takeout_match.json](file:///Users/hiijitesh/Documents/google-photos-cleaner/data/json/takeout_match.json):** A detailed list of all matched files, timestamps, and locations that were updated.
* **[takeout_unmatched.json](file:///Users/hiijitesh/Documents/google-photos-cleaner/data/json/takeout_unmatched.json):** Any JSON files that could not be matched (will be empty `[]` on a perfect run).

---

## 🔍 How Verification Works (JSON vs. Filename Timestamps)

When you run `verify-takeout`, it audits the files using the following logic:

### 1. Expected Time vs. Actual Time
* **Expected Time:** The ground-truth timestamp extracted from the Google Photos Takeout JSON.
* **Actual Time:** The timestamp currently on the photo file (filesystem modified time and internal EXIF headers).
* The script confirms that the **Actual Time** on disk matches the **Expected Time** from the database log.

### 2. Why we don't verify against the Filename Timestamp
* **Missing Filename Timestamps:** Many exported photos (such as Snapchat images or custom-named files, e.g., `Snapchat-1969078348.jpg`) have no dates or times in their filenames.
* **Database Ground Truth:** Google Photos' internal database timestamp (found in the JSON) is the ultimate source of truth for where the photo sits on your timeline, even if the filename differs slightly due to upload delays or timezone shifts.
* **Association by Name:** Filenames are strictly used to *match* the `.json` file to the correct photo, but the metadata inside the JSON is what is written and verified.

---

## 🧠 Core System Design & Concepts Reference
For a complete guide to the matching algorithms, Exiftool batch processing, and filesystem time updates with code examples, check out **[LEARNING.md](file:///Users/hiijitesh/Documents/google-photos-cleaner/LEARNING.md)**.
