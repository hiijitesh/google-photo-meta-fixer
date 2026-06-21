# Learning Guide: Google Photos Takeout Metadata Merger Concepts & Logic

This document explains the core software engineering concepts, matching algorithms, and execution optimization strategies used to build the **Google Takeout Metadata Merger** in this repository. Use this to understand the "why" and "how" behind the code!

---

## 🎯 Core Challenge: What is the Problem?
When you download Google Photos via Google Takeout, Google exports two separate files for each photo or video:
1. **The Media File:** E.g., `IMG_0001.jpg` (often stripped of its original GPS coordinates, description, and creation time, or with its filesystem modified time reset to the download date).
2. **The JSON Companion:** E.g., `IMG_0001.jpg.json` (contains the true creation date, GPS coordinates, and description from the Google Photos database).

To merge these back together, a script must:
1. **Locate** the correct photo for every JSON file (handling Google's filename quirks).
2. **Parse** the metadata from the JSON.
3. **Embed** the metadata back inside the image's headers (EXIF) and update the local filesystem date (`mtime`).

---

## 🧩 Concept 1: Robust Fuzzy Filename Matching
Google Takeout filenames have severe inconsistencies. A simple exact-match script will miss up to **90%** of your library due to four distinct quirks. Here is how we solved each of them:

### Quirk A: Suffix Shifting for Duplicates
When you have duplicate filenames, Google appends numbers, but positions them differently:
* **JSON File:** `photo.jpg(1).json`
* **Media File:** `photo(1).jpg`

#### 💡 The Logic & Code:
We use a Regular Expression (Regex) to extract the file name, extension, and duplicate index, then rearrange them to look for the media file:
```python
import re

# Match pattern: <base>.<ext>(<num>).json
match = re.match(r'^(.+)\.([a-zA-Z0-9]+)\((\d+)\)\.json$', json_name, re.IGNORECASE)
if match:
    base_part, ext_part, num_part = match.groups()
    matching_media_name = f"{base_part}({num_part}).{ext_part}"
```
* **Example:** `IMG_1024.jpg(2).json` matches group 1=`IMG_1024`, group 2=`jpg`, group 3=`2`. It constructs and successfully finds `IMG_1024(2).jpg`.

---

### Quirk B: Long Filename Truncation
Google truncates long filenames in the JSON file name (typically limiting them to ~47-51 characters total), leaving the original media file longer:
* **JSON File:** `extremely_long_name_truncated_to_somethin.jpg.json`
* **Media File:** `extremely_long_name_truncated_to_something.jpg`

#### 💡 The Logic & Code:
If an exact match fails, we perform **Prefix Substring Matching** on the base names (excluding extensions) of all files in the directory. To prevent false positives on short names (e.g. matching `IMG_1` to `IMG_10`), we enforce a **minimum match threshold of 15 characters**:
```python
# Strip extensions and compare prefixes
min_len = min(len(json_base_no_ext), len(media_base_no_ext))
if min_len >= 15:
    if json_base_no_ext[:min_len] == media_base_no_ext[:min_len]:
        return media_file
```
* **Example:** `my_trip_to_paris_2023_day_one_group_sho` (length 38) matches `my_trip_to_paris_2023_day_one_group_shot` (length 39) because the first 38 characters are identical.

---

### Quirk C: Supplemental Suffixes and Multiple Dots
Google appends `.supplemental-metadata.json` or truncated versions like `.supp.json` or `.supplemental-`. It also generates double dots (e.g., `photo.jpg..json`).

#### 💡 The Logic & Code:
We run two cleanup regexes on the JSON name *before* performing any matching steps. This normalizes all bizarre JSON extensions back to `.jpg.json` or `.png.json`:
```python
# 1. Clean up multiple dots: "photo.jpg..json" -> "photo.jpg.json"
json_name = re.sub(r'\.+json$', '.json', json_name, flags=re.IGNORECASE)

# 2. Clean up supplemental suffixes: "photo.jpg.supplemental-metadata.json" -> "photo.jpg.json"
json_name = re.sub(r'\.(sup[a-z-]*)\.json$', '.json', json_name, flags=re.IGNORECASE)
```
* **Example:** `trip.jpeg.supplementa.json` $\rightarrow$ `trip.jpeg.json` $\rightarrow$ exact match with `trip.jpeg`.

---

### Quirk D: Package Names with Dots (e.g. Android Screenshots)
Android screenshot filenames include dots inside the package name, e.g. `Screenshot_2023-04-17-20-32-23-278_com.miui.gallery.jpg`. Google truncates this to:
* **JSON File:** `Screenshot_2023-04-17-20-32-23-278_com.miui.ga.json`
* **Media File:** `Screenshot_2023-04-17-20-32-23-278_com.miui.gallery.jpg`

If we splits at the last dot in the JSON name, we get `ga` as the extension, which doesn't match the media file's extension `jpg`.

#### 💡 The Logic & Code:
We maintain a list of known media extensions (`KNOWN_EXTENSIONS`). We only split the filename at the dot if the trailing text is actually a known media extension. If it isn't (like `.ga`), we treat the entire string as the base name and apply prefix matching:
```python
known_exts = {'jpg', 'jpeg', 'png', 'heic', 'webp', 'mp4', 'mov', 'gif', 'mp', 'jp'}
if json_ext.lower() in known_exts:
    # Handle standard extension matching
else:
    # Treat the dot as part of the filename (e.g., com.miui.ga is prefix of com.miui.gallery)
    # Apply prefix matching rules...
```

---

## ⚡ Concept 2: High-Performance Exiftool Batch Updates
Exiftool is written in Perl. Spawning a new command-line process for every single file inside Python is extremely slow because of startup overhead:
* 1000 files $\times$ 0.15 seconds startup = **150 seconds (2.5 minutes)**.

### 💡 The Solution: Exiftool `-json` Import Mode
Exiftool allows you to feed all metadata changes for multiple files using a single temporary JSON file and run it **exactly once**:

1. **Write the Metadata Payload File:** We save a list of objects containing the target file (`SourceFile`) and its tags to `takeout_exif_temp.json`:
   ```json
   [
     {
       "SourceFile": "/absolute/path/to/photo1.jpg",
       "DateTimeOriginal": "2023:04:09 15:05:31+00:00",
       "GPSLatitude": 37.7749,
       "GPSLongitude": -122.4194
     }
   ]
   ```
2. **Write the Target Files List:** To bypass command-line length limits (if updating thousands of files), we write the list of files to `takeout_files_temp.txt` (one per line).
3. **Execute Exiftool Once:** We instruct Exiftool to read from the files list (`-@`) and import the JSON:
   ```bash
   exiftool -overwrite_original -m -json=takeout_exif_temp.json -@ takeout_files_temp.txt
   ```
* **Performance Improvement:** Re-writing 1,000 files goes from **2.5 minutes** to **under 5 seconds**!

---

## 🕒 Concept 3: Filesystem Date Modification (`mtime`)
Updating EXIF metadata only changes the headers *inside* the file. If you open Finder (Mac) or File Explorer (Windows), the files may still show up sorted by their "Date Modified" or "Date Created" which got reset when you downloaded the zip.

### 💡 The Logic & Code:
We use Python's built-in `os.utime()` to update the filesystem's access time (`atime`) and modification time (`mtime`). This uses epoch timestamps (seconds since January 1, 1970) which are timezone-independent and parsed directly from the JSON:
```python
# data['photoTakenTime']['timestamp'] = "1681052286"
ts = float(data['photoTakenTime']['timestamp'])

# Set both access time (atime) and modification time (mtime)
os.utime(filepath, (ts, ts))
```
Finder and Explorer will immediately read the correct date and organize your photos in the correct chronological order on your computer.

---

## 🛡️ Concept 4: Resilient Error Handling
A good utility script should never crash halfway through processing if it encounters a single corrupted file.

### 💡 The Logic & Code:
We implemented two main safeguards:
1. **The `-m` (Ignore Minor Errors) Flag:** In Exiftool, `-m` tells it to write tags even if the file contains minor EXIF specification violations (common in mobile uploads).
2. **Corrupted File Detection in Verification:** If an image is binary-corrupted (e.g. `Bad format (0) for ExifIFD entry 0`), Exiftool is physically unable to write headers. The script catches this, updates the filesystem date via `os.utime` (which still works on corrupted files), logs it, and continues processing the remaining files.
