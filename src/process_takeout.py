import os
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone, timedelta
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


def is_time_different(current_time_str, target_time_str):
    """
    Returns True if current_time_str is missing/invalid or differs from target_time_str
    by more than 26 hours (to account for timezone offsets).
    """
    if not current_time_str:
        return True
    if current_time_str == target_time_str:
        return False

    try:
        # target_time_str is formatted as "%Y:%m:%d %H:%M:%S+00:00"
        target_dt = datetime.strptime(
            target_time_str, "%Y:%m:%d %H:%M:%S+00:00"
        ).replace(tzinfo=timezone.utc)
        target_ts = target_dt.timestamp()
    except Exception:
        return True

    current_time_str = str(current_time_str).strip()
    if current_time_str in ("0000:00:00 00:00:00", ""):
        return True

    # Check for timezone offset in current time (e.g. "+09:00" or "-05:00")
    match = re.search(r"([+-]\d{2}):?(\d{2})$", current_time_str)
    if match:
        try:
            offset_str = match.group(1) + match.group(2)
            date_part = current_time_str[: -len(match.group(0))].strip()
            date_part = date_part[:19]
            dt_naive = datetime.strptime(date_part, "%Y:%m:%d %H:%M:%S")
            hours = int(match.group(1))
            minutes = int(match.group(2))
            sign = -1 if hours < 0 else 1
            tz = timezone(sign * timedelta(hours=abs(hours), minutes=minutes))
            dt = dt_naive.replace(tzinfo=tz)
            current_ts = dt.astimezone(timezone.utc).timestamp()
            return abs(current_ts - target_ts) > 60.0
        except Exception:
            pass

    # Parse as naive datetime (assume local time)
    try:
        clean_date = current_time_str[:19]
        dt_naive = datetime.strptime(clean_date, "%Y:%m:%d %H:%M:%S")
        dt_target_utc = target_dt.replace(tzinfo=None)
        diff = abs((dt_naive - dt_target_utc).total_seconds())
        # Difference <= 26 hours is assumed to be timezone difference
        return diff > 26 * 3600
    except Exception:
        return True


def is_gps_different(current_val, target_val, tolerance=0.0001):
    """
    Returns True if current_val is missing/invalid or differs from target_val
    by more than the tolerance.
    """
    if target_val is None:
        return False
    if current_val is None:
        return True
    try:
        return abs(float(current_val) - float(target_val)) > tolerance
    except Exception:
        return True


def should_keep_update(exif_entry, current):
    """
    Returns True if the file needs to be updated.
    We skip updating if the core date (DateTimeOriginal or CreateDate) is already
    correct (within 26 hours) and GPS / description are already correct.
    """
    # 1. Date/Time checks
    curr_dto = current.get("DateTimeOriginal")
    curr_cd = current.get("CreateDate")

    target_dt_str = exif_entry.get("DateTimeOriginal")

    date_needs_update = True
    if target_dt_str:
        # Check if either DateTimeOriginal or CreateDate in current is close to target
        dto_diff = is_time_different(curr_dto, target_dt_str) if curr_dto else True
        cd_diff = is_time_different(curr_cd, target_dt_str) if curr_cd else True

        # If either is correct, we don't need to update the date
        if (curr_dto and not dto_diff) or (curr_cd and not cd_diff):
            date_needs_update = False

    # 2. GPS checks
    gps_needs_update = False
    if "GPSLatitude" in exif_entry:
        if is_gps_different(current.get("GPSLatitude"), exif_entry["GPSLatitude"]):
            gps_needs_update = True
    if "GPSLongitude" in exif_entry:
        if is_gps_different(current.get("GPSLongitude"), exif_entry["GPSLongitude"]):
            gps_needs_update = True
    if "GPSAltitude" in exif_entry:
        if is_gps_different(
            current.get("GPSAltitude"), exif_entry["GPSAltitude"], tolerance=5.0
        ):
            gps_needs_update = True

    # 3. Description checks
    desc_needs_update = False
    if "Description" in exif_entry:
        if current.get("Description") != exif_entry["Description"]:
            desc_needs_update = True
    if "UserComment" in exif_entry:
        if current.get("UserComment") != exif_entry["UserComment"]:
            desc_needs_update = True

    # We must update if:
    # - The date needs update
    # - OR GPS needs update
    # - OR description needs update
    if date_needs_update or gps_needs_update or desc_needs_update:
        # If the date was already correct, remove date-related fields from exif_entry
        # so we don't overwrite correct local times with UTC times.
        if not date_needs_update:
            exif_entry.pop("DateTimeOriginal", None)
            exif_entry.pop("CreateDate", None)
            exif_entry.pop("ModifyDate", None)
        return True

    return False


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
        log.info("Checking existing EXIF metadata to avoid unnecessary writes...")
        os.makedirs("data/json", exist_ok=True)
        read_files_path = "data/json/takeout_read_files_temp.txt"

        current_meta = {}
        try:
            with open(read_files_path, "w", encoding="utf-8") as f:
                for entry in exif_updates:
                    f.write(entry["SourceFile"] + "\n")

            # Execute exiftool batch read command with numeric flag (-n)
            read_cmd = [
                "exiftool",
                "-j",
                "-n",
                "-DateTimeOriginal",
                "-CreateDate",
                "-ModifyDate",
                "-GPSLatitude",
                "-GPSLongitude",
                "-GPSAltitude",
                "-Description",
                "-UserComment",
                "-@",
                read_files_path,
            ]
            res = subprocess.run(
                read_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            if res.returncode == 0:
                current_meta_list = json.loads(res.stdout)
                for item in current_meta_list:
                    sf = os.path.normpath(os.path.abspath(item["SourceFile"]))
                    current_meta[sf] = item
            else:
                log.warning(f"Error reading existing EXIF: {res.stderr}. Writing all.")
        except Exception as e:
            log.warning(f"Failed to read existing EXIF: {e}. Writing all.")
        finally:
            if os.path.exists(read_files_path):
                os.remove(read_files_path)

        # Filter updates
        filtered_updates = []
        for entry in exif_updates:
            sf_norm = os.path.normpath(os.path.abspath(entry["SourceFile"]))
            current = current_meta.get(sf_norm, {})
            if should_keep_update(entry, current):
                filtered_updates.append(entry)

        skipped_count = len(exif_updates) - len(filtered_updates)
        if skipped_count > 0:
            log.info(f"Skipping {skipped_count} files with up-to-date EXIF data.")

        if filtered_updates:
            log.info(
                f"Batch updating EXIF metadata for {len(filtered_updates)} files using exiftool..."
            )
            temp_json_path = "data/json/takeout_exif_temp.json"
            temp_files_path = "data/json/takeout_files_temp.txt"

            try:
                with open(temp_json_path, "w", encoding="utf-8") as f:
                    json.dump(filtered_updates, f, indent=2)

                with open(temp_files_path, "w", encoding="utf-8") as f:
                    for entry in filtered_updates:
                        f.write(entry["SourceFile"] + "\n")

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
                    log.info("EXIF metadata successfully updated for modified files.")
                else:
                    log.error(f"Error running exiftool: {res.stderr}")
            except Exception as e:
                log.error(f"Failed to execute exiftool batch process: {e}")
            finally:
                if os.path.exists(temp_json_path):
                    os.remove(temp_json_path)
                if os.path.exists(temp_files_path):
                    os.remove(temp_files_path)
        else:
            log.info("All files have correct EXIF data. No writes performed.")

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
        skipped_mtime_count = 0
        for filepath, ts in filesystem_updates:
            try:
                # Avoid touching if current mtime is already correct (within 1 second)
                try:
                    curr_mtime = os.path.getmtime(filepath)
                    if abs(curr_mtime - ts) <= 1.0:
                        skipped_mtime_count += 1
                        continue
                except Exception:
                    pass
                os.utime(filepath, (ts, ts))
                updated_mtime_count += 1
            except Exception as e:
                log.error(f"Failed to update filesystem time for {filepath}: {e}")
        if skipped_mtime_count > 0:
            log.info(
                f"Skipped updating filesystem times for {skipped_mtime_count} files (already accurate)."
            )
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
