import os
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from src.logger import log
from src.utils import parse_filename_time


def find_matching_media(json_path, media_lower_map):
    """
    Matches a companion JSON file to its corresponding media file in the same directory.
    Uses precomputed dictionaries for O(1) exact matches and optimized fuzzy matching.
    """
    json_name = json_path.name
    json_name = re.sub(r"\.+json$", ".json", json_name, flags=re.IGNORECASE)
    json_name = re.sub(
        r"\.(sup[a-z-]*)\.json$", ".json", json_name, flags=re.IGNORECASE
    )

    json_base = json_name[:-5]
    json_base_lower = json_base.lower()

    # 1. Exact Match (Case-sensitive & insensitive)
    if json_base_lower in media_lower_map:
        return media_lower_map[json_base_lower]

    # 3. Suffix shifting / Duplicate brackets
    match = re.match(r"^(.+)\.([a-zA-Z0-9]+)\((\d+)\)\.json$", json_name, re.IGNORECASE)
    if match:
        base_part, ext_part, num_part = match.groups()
        cand_lower = f"{base_part}({num_part}).{ext_part}".lower()
        if cand_lower in media_lower_map:
            return media_lower_map[cand_lower]

    # 4. Truncated file names
    if "." in json_base:
        json_base_no_ext, json_ext = json_base.rsplit(".", 1)
        known_exts = {
            "jpg",
            "jpeg",
            "png",
            "heic",
            "webp",
            "mp4",
            "mov",
            "gif",
            "3gp",
            "m4v",
            "avi",
            "mp",
            "jp",
        }
        if json_ext.lower() in known_exts:
            for f in media_lower_map.values():
                if "." in f:
                    f_base_no_ext, f_ext = f.rsplit(".", 1)
                    if f_ext.lower().startswith(
                        json_ext.lower()
                    ) or json_ext.lower().startswith(f_ext.lower()):
                        min_len = min(len(json_base_no_ext), len(f_base_no_ext))
                        if (
                            min_len >= 15
                            and json_base_no_ext[:min_len] == f_base_no_ext[:min_len]
                        ):
                            return f
        else:
            for f in media_lower_map.values():
                if "." in f:
                    f_base, _ = f.rsplit(".", 1)
                    f_base_lower = f_base.lower()
                    if f_base_lower == json_base_lower:
                        return f
                    if len(json_base_lower) >= 15 and f_base_lower.startswith(
                        json_base_lower
                    ):
                        return f
    else:
        for f in media_lower_map.values():
            if "." in f:
                f_base, _ = f.rsplit(".", 1)
                f_base_lower = f_base.lower()
                if f_base_lower == json_base_lower:
                    return f
                if len(json_base_lower) >= 15 and f_base_lower.startswith(
                    json_base_lower
                ):
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
        log.info(
            "Exiftool detected. Full EXIF/GPS metadata will be embedded into media."
        )
    else:
        log.warning(
            "Warning: exiftool is not installed. Filesystem modification dates will be updated, but EXIF metadata/GPS tags will be skipped."
        )
        log.warning("To fix this, install exiftool: 'brew install exiftool'")

    matched_count = 0
    unmatched_count = 0
    skipped_json_count = 0

    matched_records = []
    unmatched_records = []
    exif_updates = []
    filesystem_updates = []  # Tuple of (filepath, timestamp)

    # Cache directories files to optimize traversal
    log.info("Crawling directory structure...")
    for root, dirs, files in os.walk(takeout_path):
        # Separate JSON files and media files
        json_files = []
        media_files = []
        media_lower_map = {}
        for f in files:
            if f.startswith("."):
                continue
            if f.endswith(".json"):
                json_files.append(f)
            else:
                media_files.append(f)
                media_lower_map[f.lower()] = f

        if not json_files:
            continue

        root_path = Path(root)

        for json_file in json_files:
            json_path = root_path / json_file

            # Skip root configuration JSONs (e.g. metadata.json at Takeout root)
            if json_file == "metadata.json":
                continue

            # Load JSON content to check if it's a media companion
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                log.debug(f"Skipping unreadable JSON {json_path}: {e}")
                continue

            # Check if it has photoTakenTime signature
            if "photoTakenTime" not in data and "creationTime" not in data:
                skipped_json_count += 1
                continue

            # Try to match with media file
            matched_media_name = find_matching_media(json_path, media_lower_map)
            if not matched_media_name:
                unmatched_count += 1
                unmatched_records.append(
                    {
                        "json_path": str(json_path),
                        "reason": "No matching media file found in same folder",
                    }
                )
                continue

            # Identify companion motion photo / live photo video files
            media_names_to_update = [matched_media_name]
            lower_name = matched_media_name.lower()
            photo_exts = (".jpg", ".jpeg", ".heic", ".png", ".webp")
            if lower_name.endswith(photo_exts):
                stem_lower = Path(matched_media_name).stem.lower()
                # Check for companion video formats case-insensitively
                video_exts = (".mp4", ".mov", ".3gp", ".m4v", ".avi")
                for f in media_files:
                    if f != matched_media_name:
                        f_path = Path(f)
                        if f_path.stem.lower() == stem_lower:
                            if f_path.suffix.lower() in video_exts:
                                media_names_to_update.append(f)

            # Extract timestamp
            time_section = data.get("photoTakenTime") or data.get("creationTime") or {}
            ts_str = time_section.get("timestamp", "0")
            try:
                ts = float(ts_str)
            except ValueError:
                ts = 0.0

            if ts <= 0:
                # Fallback to current time if missing/invalid
                ts = datetime.now(timezone.utc).timestamp()

            # Convert to UTC string for EXIF format
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            formatted_time = dt.strftime("%Y:%m:%d %H:%M:%S+00:00")

            # Extract description
            description = data.get("description", "").strip()

            # Extract GPS coordinates
            geo = data.get("geoData") or data.get("geoDataExif") or {}
            lat = float(geo.get("latitude", 0.0))
            lon = float(geo.get("longitude", 0.0))
            alt = float(geo.get("altitude", 0.0))

            for m_name in media_names_to_update:
                media_path = root_path / m_name
                matched_count += 1

                # Store filesystem update details
                filesystem_updates.append((media_path, ts))

                # Build EXIF update payload
                exif_entry: dict[str, str | float] = {
                    "SourceFile": str(media_path.absolute()),
                    "DateTimeOriginal": formatted_time,
                    "CreateDate": formatted_time,
                    "ModifyDate": formatted_time,
                }
                if lat != 0.0 or lon != 0.0:
                    exif_entry["GPSLatitude"] = lat
                    exif_entry["GPSLongitude"] = lon
                    exif_entry["GPSAltitude"] = alt
                if description:
                    exif_entry["Description"] = description
                    exif_entry["UserComment"] = description

                exif_updates.append(exif_entry)
                matched_records.append(
                    {
                        "media_path": str(media_path),
                        "json_path": str(json_path),
                        "timestamp": ts,
                        "date": dt.isoformat(),
                        "gps": (
                            {"lat": lat, "lon": lon}
                            if (lat != 0.0 or lon != 0.0)
                            else None
                        ),
                    }
                )

    log.info(
        f"Scan complete. Found {matched_count} matched files, {unmatched_count} unmatched JSONs."
    )

    # 1. Update EXIF tags via exiftool batch command
    if exiftool_installed and exif_updates:
        log.info("Batch updating EXIF metadata using exiftool...")

        # Save temp payloads under data/json/ (create dir if not exists)
        os.makedirs("data/json", exist_ok=True)
        temp_json_path = "data/json/takeout_exif_temp.json"
        temp_files_path = "data/json/takeout_files_temp.txt"

        try:
            with open(temp_json_path, "w", encoding="utf-8") as f:
                json.dump(exif_updates, f, indent=2)

            with open(temp_files_path, "w", encoding="utf-8") as f:
                for entry in exif_updates:
                    f.write(entry["SourceFile"] + "\n")

            # Execute exiftool batch command
            cmd = [
                "exiftool",
                "-overwrite_original",
                "-m",
                f"-json={temp_json_path}",
                "-@",
                temp_files_path,
            ]
            res = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
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

    # Clean up any _original backup files left behind by exiftool on error
    cleanup_count = 0
    for root, dirs, files in os.walk(takeout_path):
        for f in files:
            if f.endswith("_original"):
                try:
                    os.remove(os.path.join(root, f))
                    cleanup_count += 1
                except Exception as e:
                    log.warning(f"Could not delete backup file {f}: {e}")
    if cleanup_count:
        log.info(f"Cleaned up {cleanup_count} exiftool _original backup file(s).")

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

    with open(match_log_path, "w", encoding="utf-8") as f:
        json.dump(matched_records, f, indent=2)

    with open(unmatched_log_path, "w", encoding="utf-8") as f:
        json.dump(unmatched_records, f, indent=2)

    log.info(f"Operation summary logged:")
    log.info(f"  Matched index saved to {match_log_path}")
    log.info(f"  Unmatched index saved to {unmatched_log_path}")
    log.info("Done!")
