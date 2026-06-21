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
