# Google Photos Takeout Helper (GPTH) Guide

## Overview
When you export your photos from Google Photos using Google Takeout, you usually end up with multiple zip files containing hundreds of messy folders and weird `.json` metadata files. 

[Google Photos Takeout Helper](https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper) (GPTH) is a tool that automatically organizes this mess. It parses the folders, restores the "last modified" dates correctly using the `.json` files, and consolidates everything into a single chronological folder (or divides them by month).

## Step-by-Step Usage

### 1. Download Your Takeout
1. Go to [Google Takeout](https://takeout.google.com/).
2. Click **Deselect All**, then select only **Google Photos**.
3. Download all the resulting `.zip` files.

> [!WARNING]
> Keep your original `.zip` files as a backup. By default, GPTH **moves** files rather than copying them. If something goes wrong, you will need the original zips to start over.

### 2. Extract and Merge
Extract all your downloaded `.zip` files and merge them into a single folder. All "Takeout" folders from the individual zips should be merged into one main folder.

### 3. Download GPTH
Download the latest executable for your operating system (macOS, Windows, or Linux) from the [Releases tab](https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper/releases).

### 4. Run the Script (macOS Example)
Open your terminal and prepare the executable:

```bash
# If you are on an M1/M2 Mac, ensure Rosetta is installed:
softwareupdate --install-rosetta

# Navigate to where you downloaded GPTH
cd ~/Downloads

# Make the file executable
chmod +x gpth-macos

# Remove the macOS Gatekeeper quarantine warning
xattr -r -d com.apple.quarantine gpth-macos

# Run the interactive script
./gpth-macos
```
Follow the interactive prompts in your terminal to select your input folder (the merged Takeout folder) and your output destination.

## Smart Usage Tips & Best Practices

> [!TIP]
> **Use ExifTool to permanently bake dates into metadata**
> GPTH fixes the file's internal OS "Date Modified" timestamp, but it's highly recommended to permanently embed this into the actual photo EXIF data so it's never lost. Install `exiftool` and run:
> ```bash
> exiftool -overwrite_original -r -if 'not defined DateTimeOriginal' -P "-AllDates<FileModifyDate" "/path/to/your/output/folder/"
> ```
> *Note: Make sure to run this immediately after GPTH before any other file modifications occur!*

### CLI Options for Power Users
If you want to automate backups or avoid the interactive UI, you can run GPTH directly via command-line arguments:
- **Organize into Subfolders:** Use the `--divide-to-dates` flag to sort your output into beautifully separated month/year directories instead of one massive 100,000+ photo folder.
- **Handling Albums:** GPTH supports album reconstruction! Run it via CLI: `./gpth-macos --albums "shortcut"`. This will create lightweight shortcuts/symlinks organizing your media into album folders without duplicating file storage.

### Transferring to Android
Moving files via standard USB to an Android phone will often overwrite the creation dates to the current time, breaking your chronological timeline.
- To prevent this, use a tool like **[Syncthing](https://syncthing.net/)** to sync the organized photos wirelessly to your device. It preserves the exact modification dates.
- Using **[Simple Gallery](https://github.com/SimpleMobileTools/Simple-Gallery)** on Android is also recommended, as it reads the timeline properly.
