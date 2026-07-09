# Google Takeout Metadata Merger Guide

> Part of **Google Photo Meta Fixer** — `gp-cleaner process takeout`

This guide covers how the Takeout metadata merger works, what it handles automatically, how to verify results, and where output logs are stored.

---

## Overview

When you export photos via **Google Takeout**, each media file is accompanied by a companion `.json` sidecar file containing the true creation timestamp, GPS coordinates, and description from the Google Photos database.

The `process takeout` command:
1. **Recursively walks** the Takeout export directory.
2. **Fuzzy-matches** each sidecar JSON to its corresponding photo or video.
3. **Writes metadata** back into the file: EXIF tags (`DateTimeOriginal`, GPS), filesystem `mtime`, and descriptions.

---

## Quick Start

### 1. Install exiftool (required for EXIF/GPS writes)

```bash
brew install exiftool             # macOS
sudo apt install libimage-exiftool-perl  # Debian/Ubuntu
```

> **Note:** If `exiftool` is not installed, the tool falls back to updating only filesystem modification dates — GPS and description tags will not be embedded.

### 2. Run the command

```bash
gp-cleaner process takeout --dir "/path/to/Takeout/Google Photos"
```

### 3. Verify results

```bash
gp-cleaner metadata verify-takeout
```

This audits all processed files against `data/json/takeout_match.json` and confirms that both EXIF headers and filesystem timestamps match the expected values from the Takeout database.

---

## What is Handled Automatically

You do not need to rename or pre-process any files. The matcher resolves all of the following Google Takeout quirks automatically:

| Quirk | Example (JSON → Media) |
|:---|:---|
| **Truncated names** | `very_long_photo_name_tr.jpg.json` → `very_long_photo_name_truncated.jpg` |
| **Bracket-shift duplicates** | `photo.jpg(1).json` → `photo(1).jpg` |
| **Supplemental metadata suffixes** | `photo.jpg.supp.json` → `photo.jpg` |
| **Double dots** | `photo.jpg..json` → `photo.jpg` |
| **Android screenshot formats** | `com.miui.gallery_20230401.jpg.json` → `com.miui.gallery_20230401.jpg` |
| **UTC to local offset** | JSON UTC timestamps are correctly converted to local timezone for EXIF tags |

---

## Output Logs

After execution, two index files are written to `data/json/`:

| File | Contents |
|:---|:---|
| `data/json/takeout_match.json` | All successfully matched files, with applied timestamps and locations. |
| `data/json/takeout_unmatched.json` | JSON files that could not be matched (empty `[]` on a perfect run). |

---

## How Verification Works

When you run `gp-cleaner metadata verify-takeout`, it compares:

- **Expected Time** — Ground-truth timestamp from the Google Photos Takeout JSON (stored in `takeout_match.json` during processing).
- **Actual Time** — Current filesystem `mtime` and EXIF `DateTimeOriginal` on the file on disk.

### Why filenames are not used for timestamp verification

Many exported files have no date embedded in their filename (e.g., `Snapchat-1969078348.jpg`). The filename is used solely to **locate and match** the correct JSON; the timestamp source of truth is always the **JSON database record** — not the filename.

---

## Further Reading

- [LEARNING.md](LEARNING.md) — Deep dive into the fuzzy matching algorithms, exiftool batch processing, and filesystem time update patterns with code examples.
- [cli_reference_guide.md](cli_reference_guide.md) — Full CLI subcommand reference and workflow tables.
