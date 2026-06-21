import os
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from src.logger import log

def parse_filename_time(filename):
    """
    Optional helper to parse a time signature from filename.
    Useful for verification/logging.
    """
    # Look for typical YYYYMMDD_HHMMSS
    pattern = re.compile(r'((?:19|20)\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})')
    match = pattern.search(filename)
    if match:
        year, month, day, hour, minute, second = map(int, match.groups())
        try:
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            pass
    return None

def find_matching_media(json_path, media_files):
    """
    Matches a companion JSON file to its corresponding media file in the same directory.
    Handles Google Takeout quirks including exact matches, duplicate brackets, and truncated names.
    """
    json_name = json_path.name
    # Strip '.json' to get the base media candidate name
    json_base = json_name[:-5]
    json_base_lower = json_base.lower()

    # 1. Exact Match (Case-sensitive)
    if json_base in media_files:
        return json_base

    # 2. Exact Match (Case-insensitive)
    for f in media_files:
        if f.lower() == json_base_lower:
            return f

    # 3. Suffix shifting / Duplicate brackets
    # e.g., JSON: "photo.jpg(1).json" -> Media: "photo(1).jpg"
    match = re.match(r'^(.+)\.([a-zA-Z0-9]+)\((\d+)\)\.json$', json_name, re.IGNORECASE)
    if match:
        base_part, ext_part, num_part = match.groups()
        cand = f"{base_part}({num_part}).{ext_part}"
        for f in media_files:
            if f.lower() == cand.lower():
                return f

    # 4. Truncated file names
    # Google truncates long filenames in the JSON name (usually at ~47-51 chars total).
    # e.g. JSON: "really_long_name_truncated_to_somethin.jpg.json"
    # Media: "really_long_name_truncated_to_something.jpg"
    if '.' in json_base:
        json_base_no_ext, json_ext = json_base.rsplit('.', 1)
        for f in media_files:
            if '.' in f:
                f_base_no_ext, f_ext = f.rsplit('.', 1)
                # Check if extensions match or are truncated/started extensions (e.g. .mp -> .mp4)
                if f_ext.lower().startswith(json_ext.lower()) or json_ext.lower().startswith(f_ext.lower()):
                    # Match base prefix. Check if shorter base is a prefix of longer base.
                    min_len = min(len(json_base_no_ext), len(f_base_no_ext))
                    if min_len >= 15: # Safeguard against matching generic short names
                        if json_base_no_ext[:min_len] == f_base_no_ext[:min_len]:
                            return f
    else:
        # No extension in json_base (e.g. "photo.json" matching "photo.jpg")
        for f in media_files:
            if '.' in f:
                f_base, _ = f.rsplit('.', 1)
                if f_base.lower() == json_base_lower:
                    return f

    return None

def main(takeout_dir):
    log.info("=== Starting Google Takeout Metadata Merger ===")
    takeout_path = Path(takeout_dir)
    if not takeout_path.is_dir():
        log.error(f"Error: Specified path '{takeout_dir}' is not a directory.")
        return

    # Check for exiftool dependency
    exiftool_installed = shutil.which("exiftool") is not None
    if exiftool_installed:
        log.info("Exiftool detected. Full EXIF/GPS metadata will be embedded into media.")
    else:
        log.warning("Warning: exiftool is not installed. Filesystem modification dates will be updated, but EXIF metadata/GPS tags will be skipped.")
        log.warning("To fix this, install exiftool: 'brew install exiftool'")

    matched_count = 0
    unmatched_count = 0
    skipped_json_count = 0

    matched_records = []
    unmatched_records = []
    exif_updates = []
    filesystem_updates = [] # Tuple of (filepath, timestamp)

    # Cache directories files to optimize traversal
    log.info("Crawling directory structure...")
    for root, dirs, files in os.walk(takeout_path):
        # Separate JSON files and media files
        json_files = []
        media_files = []
        for f in files:
            if f.startswith('.'):
                continue
            if f.endswith('.json'):
                json_files.append(f)
            else:
                media_files.append(f)

        if not json_files:
            continue

        root_path = Path(root)

        for json_file in json_files:
            json_path = root_path / json_file
            
            # Skip root configuration JSONs (e.g. metadata.json at Takeout root)
            if json_file == 'metadata.json':
                continue

            # Load JSON content to check if it's a media companion
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                log.debug(f"Skipping unreadable JSON {json_path}: {e}")
                continue

            # Check if it has photoTakenTime signature
            if 'photoTakenTime' not in data and 'creationTime' not in data:
                skipped_json_count += 1
                continue

            # Try to match with media file
            matched_media_name = find_matching_media(json_path, media_files)
            if not matched_media_name:
                unmatched_count += 1
                unmatched_records.append({
                    "json_path": str(json_path),
                    "reason": "No matching media file found in same folder"
                })
                continue

            media_path = root_path / matched_media_name
            matched_count += 1

            # Extract timestamp
            time_section = data.get('photoTakenTime') or data.get('creationTime') or {}
            ts_str = time_section.get('timestamp', '0')
            try:
                ts = float(ts_str)
            except ValueError:
                ts = 0.0

            if ts <= 0:
                # Fallback to current time if missing/invalid
                ts = datetime.now(timezone.utc).timestamp()

            # Convert to UTC string for EXIF format
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            formatted_time = dt.strftime('%Y:%m:%d %H:%M:%S+00:00')

            # Extract description
            description = data.get('description', '').strip()

            # Extract GPS coordinates
            geo = data.get('geoData') or data.get('geoDataExif') or {}
            lat = float(geo.get('latitude', 0.0))
            lon = float(geo.get('longitude', 0.0))
            alt = float(geo.get('altitude', 0.0))

            # Store filesystem update details
            filesystem_updates.append((media_path, ts))

            # Build EXIF update payload
            exif_entry = {
                "SourceFile": str(media_path.absolute()),
                "DateTimeOriginal": formatted_time,
                "CreateDate": formatted_time,
                "ModifyDate": formatted_time
            }
            if lat != 0.0 or lon != 0.0:
                exif_entry["GPSLatitude"] = lat
                exif_entry["GPSLongitude"] = lon
                exif_entry["GPSAltitude"] = alt
            if description:
                exif_entry["Description"] = description
                exif_entry["UserComment"] = description

            exif_updates.append(exif_entry)
            matched_records.append({
                "media_path": str(media_path),
                "json_path": str(json_path),
                "timestamp": ts,
                "date": dt.isoformat(),
                "gps": {"lat": lat, "lon": lon} if (lat != 0.0 or lon != 0.0) else None
            })

    log.info(f"Scan complete. Found {matched_count} matched files, {unmatched_count} unmatched JSONs.")

    # 1. Update EXIF tags via exiftool batch command
    if exiftool_installed and exif_updates:
        log.info("Batch updating EXIF metadata using exiftool...")
        
        # Save temp payloads under data/json/ (create dir if not exists)
        os.makedirs("data/json", exist_ok=True)
        temp_json_path = "data/json/takeout_exif_temp.json"
        temp_files_path = "data/json/takeout_files_temp.txt"

        try:
            with open(temp_json_path, 'w', encoding='utf-8') as f:
                json.dump(exif_updates, f, indent=2)

            with open(temp_files_path, 'w', encoding='utf-8') as f:
                for entry in exif_updates:
                    f.write(entry["SourceFile"] + "\n")

            # Execute exiftool batch command
            cmd = [
                "exiftool",
                "-overwrite_original",
                f"-json={temp_json_path}",
                "-@", temp_files_path
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                log.info("EXIF metadata successfully updated for matched files.")
            else:
                log.error(f"Error running exiftool: {res.stderr}")
        except Exception as e:
            log.error(f"Failed to execute exiftool batch process: {e}")
        finally:
            # Clean up temp files
            if os.path.exists(temp_json_path):
                os.remove(temp_json_path)
            if os.path.exists(temp_files_path):
                os.remove(temp_files_path)

    # 2. Update filesystem modification timestamps (mtime)
    if filesystem_updates:
        log.info("Updating local filesystem modification times (os.utime)...")
        updated_mtime_count = 0
        for filepath, ts in filesystem_updates:
            try:
                os.utime(filepath, (ts, ts))
                updated_mtime_count += 1
            except Exception as e:
                log.error(f"Failed to update filesystem time for {filepath}: {e}")
        log.info(f"Filesystem timestamps updated for {updated_mtime_count} files.")

    # 3. Save matching indexing logs
    os.makedirs("data/json", exist_ok=True)
    match_log_path = "data/json/takeout_match.json"
    unmatched_log_path = "data/json/takeout_unmatched.json"

    with open(match_log_path, 'w', encoding='utf-8') as f:
        json.dump(matched_records, f, indent=2)

    with open(unmatched_log_path, 'w', encoding='utf-8') as f:
        json.dump(unmatched_records, f, indent=2)

    log.info(f"Operation summary logged:")
    log.info(f"  Matched index saved to {match_log_path}")
    log.info(f"  Unmatched index saved to {unmatched_log_path}")
    log.info("Done!")
