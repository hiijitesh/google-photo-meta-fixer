# Extract JSON and Backup via Google Drive

This plan details the "simple approach" requested: extracting a JSON list of files taking space in Google Photos, and using `rclone` to locate those exact files in your Google Drive, copying them into year-wise backup folders.

## Proposed Workflow

### Phase 1: Extract JSON from Google Photos
We will modify the [Google-Photos-Toolkit](https://github.com/xob0t/Google-Photos-Toolkit) (or write a quick browser console script) to run on your Google Photos quota management page. 
Instead of taking any actions, this script will simply scrape the media items and trigger a download of a `photos.json` file. 
This JSON file will contain:
- File `name` (e.g., "IMG_1234.jpg")
- File `size`
- Date/Year (if available from the UI)

### Phase 2: Index Google Drive
To avoid hitting Google Drive API rate limits by searching for thousands of files one by one, we will fetch the entire index of your Google Drive at once.
- **Command**: `rclone lsjson -R "gdrive:" > drive_index.json`
- This creates a local map of every file you have in Drive, including its exact path and modification date (`ModTime`).

### Phase 3: Match and Copy (The Python Automation)
I will write a Python script (`backup_photos.py`) that will run locally on your machine.
1. **Load Data**: The script reads your `photos.json` and `drive_index.json`.
2. **Match**: For every filename in `photos.json`, it looks up the exact path in `drive_index.json`.
3. **Determine Year**: It extracts the year from the Drive file's `ModTime` (e.g., `2019`).
4. **Copy**: It executes an `rclone copyto` command to duplicate the file into your new backup structure.
   - Example command executed:
     `rclone copyto "gdrive:old_photos/IMG_1234.jpg" "gdrive:Photos_Backup/2019/IMG_1234.jpg"`

---

## User Review Required

> [!TIP]
> This approach completely ignores EXIF metadata and Takeout, and solely relies on you having the identical files already present somewhere in your Google Drive. Because we copy the files directly inside Google Drive using `rclone`, their creation/modification dates in Drive will remain intact.

## Open Questions

1. **Rclone Remote**: What is the name of your Google Drive remote? (e.g., `gdrive:`).
2. **Drive Target**: What should the name of the new backup folder be? (e.g., `Backup_Photos`)
3. Are you ready for me to write the code? I will provide:
   - The Javascript snippet you can paste into your browser console to get `photos.json`.
   - The Python script (`backup_photos.py`) to match the JSON and run the `rclone` copies.
