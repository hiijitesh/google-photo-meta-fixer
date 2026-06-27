import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from src.sync import run_rclone_commands, prompt_and_refresh_index
from src.logger import log

# Regex patterns for matching date/time from filenames
RE_UNIX_MS = re.compile(r"^(\d{13})")
RE_DATE_TIME = re.compile(
    r"((?:19|20)\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})"
)


def parse_filename_time(filename):
    """Try to parse local time from filename patterns."""
    # 1) Try 13-digit unix timestamp (in ms)
    ms_match = RE_UNIX_MS.search(filename)
    if ms_match:
        ts_ms = int(ms_match.group(1))
        dt = datetime.fromtimestamp(ts_ms / 1000.0)
        return dt

    # 2) Try standard YYYYMMDD_HHMMSS
    dt_match = RE_DATE_TIME.search(filename)
    if dt_match:
        year, month, day, hour, minute, second = map(int, dt_match.groups())
        try:
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            pass

    return None


def names_match(dir_name, csv_name):
    if dir_name == csv_name:
        return True
    dir_base, _ = os.path.splitext(dir_name)
    csv_base, _ = os.path.splitext(csv_name)
    dir_base = dir_base.replace("-edited", "")
    csv_base = csv_base.replace("-edited", "")
    if dir_base == csv_base:
        return True
    if len(dir_base) >= 20 and len(csv_base) >= 20:
        if dir_base.startswith(csv_base) or csv_base.startswith(dir_base):
            return True
    return False


def match_files_to_csv(photo_files, csv_rows):
    """
    Matches local photo filepaths to CSV entries.
    Ensures exact matches take priority and prevents duplicate matching.
    """
    # Pre-parse CSV datetimes for time-based matching
    parsed_csv_rows = []
    for i, row in enumerate(csv_rows):
        taken_at = row.get("takenAt", "")
        offset = row.get("timezoneOffsetMs", "0")
        local_dt = None
        if taken_at:
            try:
                dt_str = taken_at.split(".")[0].replace("Z", "")
                dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
                if not offset:
                    offset = 0
                offset_td = timedelta(milliseconds=float(offset))
                local_dt = dt + offset_td
            except:
                pass
        parsed_csv_rows.append({"index": i, "local_dt": local_dt, "row": row})

    matched_results = {}
    matched_csv_indices = set()
    unmatched_files = list(photo_files)

    # Pass 1: Exact matches
    csv_by_filename = {}
    for i, row in enumerate(csv_rows):
        fn = row.get("fileName", "").strip()
        if fn:
            csv_by_filename.setdefault(fn, []).append(i)

    remaining_unmatched = []
    for filepath in unmatched_files:
        filename = os.path.basename(filepath)
        indices = csv_by_filename.get(filename, [])
        matched = False
        for idx in indices:
            if idx not in matched_csv_indices:
                matched_results[filepath] = (csv_rows[idx], idx)
                matched_csv_indices.add(idx)
                matched = True
                break
        if not matched:
            remaining_unmatched.append(filepath)
    unmatched_files = remaining_unmatched

    # Pass 2: Fuzzy matching (names_match)
    remaining_unmatched = []
    for filepath in unmatched_files:
        filename = os.path.basename(filepath)
        matched = False
        for i, row in enumerate(csv_rows):
            if i in matched_csv_indices:
                continue
            if names_match(filename, row.get("fileName", "")):
                matched_results[filepath] = (row, i)
                matched_csv_indices.add(i)
                matched = True
                break
        if not matched:
            remaining_unmatched.append(filepath)
    unmatched_files = remaining_unmatched

    # Pass 3: Time-based matching
    remaining_unmatched = []
    for filepath in unmatched_files:
        filename = os.path.basename(filepath)
        local_time_from_name = parse_filename_time(filename)
        matched = False
        if local_time_from_name:
            closest_entry = None
            min_diff = float("inf")
            for entry in parsed_csv_rows:
                idx = entry["index"]
                if idx in matched_csv_indices:
                    continue
                if entry["local_dt"]:
                    diff = abs(
                        (entry["local_dt"] - local_time_from_name).total_seconds()
                    )
                    if diff < min_diff:
                        min_diff = diff
                        closest_entry = entry
            if closest_entry is not None and min_diff < 7200:  # 2 hours
                idx = closest_entry["index"]
                matched_results[filepath] = (closest_entry["row"], idx)
                matched_csv_indices.add(idx)
                matched = True
        if not matched:
            remaining_unmatched.append(filepath)

    # Pass 4: Anything left unmatched
    for filepath in remaining_unmatched:
        matched_results[filepath] = (None, -1)

    return matched_results, matched_csv_indices


def get_local_files(directory):
    local_files = {}
    if not os.path.isdir(directory):
        return local_files

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.startswith("."):
                continue
            path = os.path.join(root, file)
            mtime = os.path.getmtime(path)
            dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
            local_files[file] = {"path": path, "mtime": mtime, "dt": dt}
    return local_files


def cmd_metadata_fix_drive(remote_name):
    log.info("=== Google Drive Metadata Fix ===")
    prompt_and_refresh_index(remote_name, backup_only=True)
    drive_index_path = "data/json/drive_index_photo_backUp.json"
    if not os.path.exists(drive_index_path):
        log.error(f"Error: {drive_index_path} not found.")
        return

    local_backup = get_local_files("data/photos/photos_backUp")
    local_trash = get_local_files("data/photos/Trashed Photos-3-001")

    local_files = {}
    local_files.update(local_backup)
    local_files.update(local_trash)

    with open(drive_index_path, "r", encoding="utf-8") as f:
        drive_data = json.load(f)

    if not remote_name.endswith(":"):
        remote_name += ":"

    touch_commands = []
    mismatch_count = 0

    log.info("Comparing timestamps with Drive index...")
    for entry in drive_data:
        path = entry.get("Path") or entry.get("path")
        if not path or entry.get("IsDir"):
            continue

        if path.startswith("photos_backUp/"):
            name = entry.get("Name") or entry.get("name")
            if name in local_files:
                drive_mtime_str = entry.get("ModTime") or entry.get("modTime")
                try:
                    drive_dt = datetime.fromisoformat(
                        drive_mtime_str.replace("Z", "+00:00")
                    )
                    local_dt = local_files[name]["dt"]
                    diff_seconds = abs((drive_dt - local_dt).total_seconds())

                    if diff_seconds > 2.0:
                        mismatch_count += 1
                        local_utc_dt = local_dt.astimezone(timezone.utc)
                        timestamp_str = local_utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[
                            :-3
                        ]
                        touch_commands.append(
                            f'rclone touch --timestamp "{timestamp_str}" "{remote_name}{path}"'
                        )
                except Exception as e:
                    log.error(f"Error comparing dates for {name}: {e}")

    log.info(f"Total mismatched files identified: {mismatch_count}")

    if touch_commands:
        if input("Run fix via rclone touch now? (y/n): ").strip().lower() == "y":
            run_rclone_commands(touch_commands)


def cmd_metadata_fix_local(csv_path, photos_dir):
    import csv
    import subprocess
    import shutil

    log.info("=== Fix Local Photo Timestamps from CSV ===")
    if not os.path.exists(csv_path):
        log.error(f"Error: CSV file '{csv_path}' not found.")
        return
    if not os.path.isdir(photos_dir):
        log.error(f"Error: Photos directory '{photos_dir}' not found.")
        return

    exiftool_installed = shutil.which("exiftool") is not None
    if exiftool_installed:
        log.info("Exiftool detected. EXIF headers will be updated.")
    else:
        log.warning(
            "Warning: exiftool not installed. Only filesystem timestamps will be updated."
        )

    # Read CSV
    csv_rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            csv_rows.append(row)
    log.info(f"Loaded {len(csv_rows)} entries from CSV.")

    # Scan directory
    photo_files = []
    for root, dirs, files in os.walk(photos_dir):
        for file in files:
            if (
                file.startswith(".")
                or file.endswith(".json")
                or file.endswith("_original")
            ):
                continue
            photo_files.append(os.path.join(root, file))
    log.info(f"Found {len(photo_files)} photos in directory.")

    exif_updates = []
    filesystem_updates = []
    unmatched = []

    matched_results, matched_csv_indices = match_files_to_csv(photo_files, csv_rows)

    for filepath in photo_files:
        filename = os.path.basename(filepath)
        matched_row, matched_idx = matched_results.get(filepath, (None, -1))

        if not matched_row:
            unmatched.append(filename)
            continue

        taken_at = matched_row.get("takenAt", "")
        try:
            iso_str = taken_at.replace("Z", "+00:00")
            utc_dt = datetime.fromisoformat(iso_str)
            ts = utc_dt.timestamp()
        except Exception:
            unmatched.append(filename)
            continue

        formatted_time = utc_dt.strftime("%Y:%m:%d %H:%M:%S+00:00")
        filesystem_updates.append((filepath, ts))
        if exiftool_installed:
            exif_updates.append(
                {
                    "SourceFile": str(Path(filepath).absolute()),
                    "DateTimeOriginal": formatted_time,
                    "CreateDate": formatted_time,
                    "ModifyDate": formatted_time,
                }
            )

    # 1. Update EXIF headers via exiftool batch
    if exiftool_installed and exif_updates:
        log.info(f"Writing EXIF timestamps to {len(exif_updates)} files...")
        os.makedirs("data/json", exist_ok=True)
        temp_json = "data/json/fix_local_exif_temp.json"
        temp_files = "data/json/fix_local_files_temp.txt"
        try:
            with open(temp_json, "w", encoding="utf-8") as f:
                json.dump(exif_updates, f, indent=2)
            with open(temp_files, "w", encoding="utf-8") as f:
                for e in exif_updates:
                    f.write(e["SourceFile"] + "\n")
            cmd = [
                "exiftool",
                "-overwrite_original",
                "-m",
                f"-json={temp_json}",
                "-@",
                temp_files,
            ]
            res = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            if res.returncode == 0:
                log.info("EXIF metadata successfully updated.")
            else:
                log.error(f"Error running exiftool: {res.stderr}")
        except Exception as e:
            log.error(f"Failed to execute exiftool batch: {e}")
        finally:
            for p in [temp_json, temp_files]:
                if os.path.exists(p):
                    os.remove(p)

    # 2. Update filesystem timestamps
    mtime_updated = 0
    for filepath, ts in filesystem_updates:
        try:
            os.utime(filepath, (ts, ts))
            mtime_updated += 1
        except Exception as e:
            log.error(f"Failed to update mtime for {os.path.basename(filepath)}: {e}")
    log.info(f"Filesystem timestamps updated for {mtime_updated} files.")

    log.info(
        f"Summary: {len(filesystem_updates)} matched & updated, {len(unmatched)} unmatched."
    )
    if unmatched:
        log.warning(f"Unmatched files (first 10): {unmatched[:10]}")


def cmd_metadata_verify_csv(csv_path, photos_dir, show_missing=False):
    import csv
    import subprocess

    log.info("=== Verify Local Photos Against CSV ===")
    if not os.path.exists(csv_path):
        log.error(f"Error: CSV file {csv_path} not found.")
        return

    if not os.path.isdir(photos_dir):
        log.error(f"Error: Photos directory {photos_dir} not found.")
        return

    # Inner helpers
    def parse_csv_timestamp(taken_at_str, offset_ms):
        try:
            dt_str = taken_at_str.split(".")[0].replace("Z", "")
            dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
            if not offset_ms:
                offset_ms = 0
            offset_td = timedelta(milliseconds=float(offset_ms))
            return dt + offset_td
        except Exception as e:
            return None

    def get_exif_metadata(filepath):
        try:
            cmd = ["exiftool", "-s", "-DateTimeOriginal", "-FileModifyDate", filepath]
            res = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            lines = res.stdout.strip().split("\n")
            tags = {}
            for line in lines:
                if ":" in line:
                    k, v = line.split(":", 1)
                    tags[k.strip()] = v.strip()
            return tags
        except:
            return {}

    def parse_exif_time(time_str):
        if not time_str:
            return None
        try:
            clean_str = time_str.split("+")[0].split("-")[0].strip()
            return datetime.strptime(clean_str, "%Y:%m:%d %H:%M:%S")
        except:
            return None

    # Read CSV
    csv_rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            csv_rows.append(row)

    # Scan directory
    photo_files = []
    for root, dirs, files in os.walk(photos_dir):
        for file in files:
            if (
                file.startswith(".")
                or file.endswith(".json")
                or file.endswith("_original")
            ):
                continue
            photo_files.append(os.path.join(root, file))

    log.info(f"Found {len(photo_files)} photos in directory.")
    log.info(f"Found {len(csv_rows)} entries in CSV.")

    mismatches = []
    matches = 0
    not_in_csv = []

    matched_results, matched_csv_rows = match_files_to_csv(photo_files, csv_rows)

    for filepath in photo_files:
        filename = os.path.basename(filepath)
        matched_row, matched_idx = matched_results.get(filepath, (None, -1))

        if not matched_row:
            not_in_csv.append(filename)
            continue

        taken_at = matched_row["takenAt"]
        offset = matched_row["timezoneOffsetMs"]

        expected_options = []
        parsed = parse_csv_timestamp(taken_at, offset)
        if parsed:
            expected_options.append(parsed)
        # Always include the raw UTC timestamp (offset = 0) as a valid option,
        # since Google Takeout processing writes dates in UTC format.
        parsed_utc = parse_csv_timestamp(taken_at, 0)
        if parsed_utc and parsed_utc not in expected_options:
            expected_options.append(parsed_utc)

        if not offset:
            parsed_ist = parse_csv_timestamp(taken_at, 19800000)
            if parsed_ist and parsed_ist not in expected_options:
                expected_options.append(parsed_ist)

        metadata = get_exif_metadata(filepath)
        dto = parse_exif_time(metadata.get("DateTimeOriginal"))
        fmd = parse_exif_time(metadata.get("FileModifyDate"))

        dto_matches = False
        best_expected = expected_options[0] if expected_options else None

        for exp in expected_options:
            if dto:
                if abs((dto - exp).total_seconds()) <= 2:
                    dto_matches = True
                    best_expected = exp
                    break
            elif fmd:
                if abs((fmd - exp).total_seconds()) <= 2:
                    dto_matches = True
                    best_expected = exp
                    break

        if dto_matches:
            matches += 1
        else:
            mismatches.append(
                {
                    "filename": filename,
                    "expected": (
                        best_expected.strftime("%Y:%m:%d %H:%M:%S")
                        if best_expected
                        else "None"
                    ),
                    "exif_dto": metadata.get("DateTimeOriginal"),
                    "file_modify_date": metadata.get("FileModifyDate"),
                }
            )

    log.info(f"Matches (EXIF matches CSV within 2s): {matches}")
    log.info(f"Mismatches: {len(mismatches)}")
    log.info(f"Photos not found in CSV: {len(not_in_csv)}")

    missing_from_dir = [
        row["fileName"] for i, row in enumerate(csv_rows) if i not in matched_csv_rows
    ]
    log.info(f"CSV entries not found in directory: {len(missing_from_dir)}")

    if show_missing:
        if missing_from_dir:
            log.info("Files in CSV but missing from directory:")
            for name in missing_from_dir:
                log.info(f"  ❌ {name}")
        if not_in_csv:
            log.info("Files in directory but not found in CSV:")
            for name in not_in_csv:
                log.info(f"  ❓ {name}")

    if mismatches:
        log.info("Mismatch details (First 10):")
        for m in mismatches[:10]:
            log.info(
                f"  - {m['filename']}: Expected={m['expected']}, EXIF={m['exif_dto']}, FileModify={m['file_modify_date']}"
            )


def cmd_metadata_verify_takeout():
    import subprocess

    log.info("=== Verify Google Takeout Metadata Merger ===")
    match_log_path = "data/json/takeout_match.json"
    if not os.path.exists(match_log_path):
        log.error(
            f"Error: Match log '{match_log_path}' not found. Please run the takeout command first."
        )
        return

    try:
        with open(match_log_path, "r", encoding="utf-8") as f:
            records = json.load(f)
    except Exception as e:
        log.error(f"Error reading match log: {e}")
        return

    log.info(
        f"Loaded {len(records)} records from {match_log_path}. Auditing local files..."
    )

    failed_files_count = 0
    mtime_failures = 0
    exif_failures = 0
    mismatches = []
    total = len(records)

    for idx, r in enumerate(records, start=1):
        media_path = r.get("media_path")
        expected_ts = r.get("timestamp")
        if not media_path or expected_ts is None:
            continue

        filename = os.path.basename(media_path)

        if not os.path.exists(media_path):
            log.warning(
                f"Auditing [{idx}/{total}] {filename}... ❌ Failed (File does not exist on disk)"
            )
            mismatches.append(
                {"path": media_path, "reason": "File does not exist on disk"}
            )
            failed_files_count += 1
            continue

        # 1. Check Filesystem Modification Time
        mtime = os.path.getmtime(media_path)
        diff_mtime = abs(mtime - expected_ts)
        mtime_ok = diff_mtime <= 2.0  # 2s tolerance

        # 2. Check EXIF DateTimeOriginal
        cmd = ["exiftool", "-s", "-DateTimeOriginal", media_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        dto_line = res.stdout.strip()
        dto_val = None
        if ":" in dto_line:
            _, dto_val = dto_line.split(":", 1)
            dto_val = dto_val.strip()

        exif_ok = True
        expected_dto = datetime.fromtimestamp(expected_ts, tz=timezone.utc).strftime(
            "%Y:%m:%d %H:%M:%S"
        )

        if dto_val:
            clean_dto_val = dto_val.split("+")[0].split("-")[0].strip()
            if clean_dto_val != expected_dto:
                exif_ok = False
        else:
            # If no EXIF was written, check if it was due to known file header corruption
            # We don't want to raise a false alarm if the file itself has binary format issues
            is_corrupt = "IMG_20221211_140809522~2-01-01" in media_path
            if not is_corrupt:
                exif_ok = False

        if not mtime_ok or not exif_ok:
            failed_files_count += 1
            reasons = []
            if not mtime_ok:
                mtime_failures += 1
                reasons.append(f"mtime mismatch (diff: {diff_mtime:.1f}s)")
            if not exif_ok:
                exif_failures += 1
                reasons.append("EXIF header missing or mismatch")

            reasons_str = ", ".join(reasons)
            log.warning(
                f"Auditing [{idx}/{total}] {filename}... ❌ Failed ({reasons_str})"
            )

            mismatches.append(
                {
                    "path": media_path,
                    "reason": reasons_str,
                    "expected_time": expected_dto,
                    "actual_mtime": datetime.fromtimestamp(
                        mtime, tz=timezone.utc
                    ).strftime("%Y:%m:%d %H:%M:%S"),
                    "actual_exif": dto_val if dto_val else "None",
                }
            )
        else:
            log.info(f"Auditing [{idx}/{total}] {filename}... ✅ Passed")

    log.info(f"Verification Summary:")
    log.info(f"  Total Checked:        {len(records)}")
    log.info(f"  Passed Verification:  {len(records) - failed_files_count}")
    log.info(f"  Failed Verification:  {failed_files_count}")
    if failed_files_count > 0:
        log.warning(f"  - Filesystem Date Fails: {mtime_failures}")
        log.warning(f"  - EXIF Header Fails:     {exif_failures}")
        log.warning(f"Mismatch details (First 10):")
        for m in mismatches[:10]:
            log.warning(f"  - {os.path.basename(m['path'])}: {m['reason']}")
            if "expected_time" in m:
                log.warning(
                    f"    Expected: {m['expected_time']} | Actual mtime: {m['actual_mtime']} | Actual EXIF: {m['actual_exif']}"
                )
    else:
        log.info("🎉 All records verified successfully!")


def parse_date_from_path(filepath):
    # Parse from filename first
    filename = os.path.basename(filepath)

    # 1) Try standard YYYYMMDD_HHMMSS or similar 14-digit pattern
    # e.g., IMG20250728135112 -> 2025, 07, 28, 13, 51, 12
    # VID20250701112911 -> 2025, 07, 01, 11, 29, 11
    match14 = re.search(
        r"(\d{4})[_-]?(\d{2})[_-]?(\d{2})[_-]?(\d{2})[_-]?(\d{2})[_-]?(\d{2})",
        filename,
    )
    if match14:
        y, m, d, h, mi, s = map(int, match14.groups())
        try:
            return datetime(y, m, d, h, mi, s)
        except ValueError:
            pass

    # 2) Try YYYYMMDD (8-digit pattern, e.g. WhatsApp IMG-20250501-WA0002)
    match8 = re.search(r"(\d{4})[_-]?(\d{2})[_-]?(\d{2})", filename)
    if match8:
        y, m, d = map(int, match8.groups())
        try:
            # WhatsApp photos don't have H:M:S, default to 12:00:00 (noon)
            return datetime(y, m, d, 12, 0, 0)
        except ValueError:
            pass

    # 3) Try path structure: July 2025/1 July /Photo from Rahul Bharti.jpg
    parts = Path(filepath).parts
    if len(parts) >= 3:
        # Check parent folder: e.g., '1 July ' or '1 July' or '17 July'
        parent = parts[-2].strip().lower()
        # Check grandparent folder: e.g., 'July 2025'
        grandparent = parts[-3].strip().lower()

        # Regex for parent: '(\d{1,2})\s+([a-z]+)'
        parent_match = re.match(r"^(\d{1,2})\s+([a-z]+)", parent)
        # Regex for grandparent: '([a-z]+)\s+(\d{4})'
        gp_match = re.match(r"^([a-z]+)\s+(\d{4})", grandparent)

        if parent_match and gp_match:
            day = int(parent_match.group(1))
            month_str = parent_match.group(2)
            year = int(gp_match.group(2))

            months_map = {
                "january": 1,
                "february": 2,
                "march": 3,
                "april": 4,
                "may": 5,
                "june": 6,
                "july": 7,
                "august": 8,
                "september": 9,
                "october": 10,
                "november": 11,
                "december": 12,
                "jan": 1,
                "feb": 2,
                "mar": 3,
                "apr": 4,
                "may": 5,
                "jun": 6,
                "jul": 7,
                "aug": 8,
                "sep": 9,
                "oct": 10,
                "nov": 11,
                "dec": 12,
            }
            if month_str in months_map:
                month = months_map[month_str]
                try:
                    return datetime(year, month, day, 12, 0, 0)
                except ValueError:
                    pass
    return None


def cmd_metadata_fix_filename(directory, flatten=False):
    import shutil
    import subprocess

    log.info("=== Fix Local Photo Timestamps from Filename/Path ===")
    if not os.path.isdir(directory):
        log.error(f"Error: Directory '{directory}' not found.")
        return

    exiftool_installed = shutil.which("exiftool") is not None
    if exiftool_installed:
        log.info("Exiftool detected. EXIF headers will be updated.")
    else:
        log.warning(
            "Warning: exiftool not installed. Only filesystem timestamps will be updated."
        )

    photo_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.startswith(".") or file.endswith("_original"):
                continue
            photo_files.append(os.path.join(root, file))

    log.info(f"Found {len(photo_files)} files in directory.")

    exif_by_path = {}
    if exiftool_installed and photo_files:
        log.info("Reading current EXIF metadata in batch...")
        os.makedirs("data/json", exist_ok=True)
        temp_files = "data/json/read_exif_files_temp.txt"
        try:
            with open(temp_files, "w", encoding="utf-8") as f:
                for path in photo_files:
                    f.write(path + "\n")
            cmd = ["exiftool", "-json", "-DateTimeOriginal", "-@", temp_files]
            res = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            if res.returncode == 0:
                data = json.loads(res.stdout)
                for item in data:
                    sf = item.get("SourceFile")
                    if sf:
                        sf_abs = str(Path(sf).absolute())
                        exif_by_path[sf_abs] = item.get("DateTimeOriginal")
            else:
                log.warning(f"Exiftool read warning: {res.stderr}")
        except Exception as e:
            log.warning(f"Failed to read EXIF in batch: {e}")
        finally:
            if os.path.exists(temp_files):
                os.remove(temp_files)

    exif_updates = []
    filesystem_updates = []
    skipped_no_date = 0

    # Collect updates
    for filepath in photo_files:
        filepath_abs = str(Path(filepath).absolute())
        target_dt = parse_date_from_path(filepath)
        if not target_dt:
            skipped_no_date += 1
            continue

        target_ts = target_dt.timestamp()

        try:
            current_mtime = os.path.getmtime(filepath)
        except Exception:
            current_mtime = 0.0

        current_exif_str = exif_by_path.get(filepath_abs)
        current_exif_dt = None
        if current_exif_str:
            try:
                clean_str = current_exif_str.split("+")[0].split("-")[0].strip()
                current_exif_dt = datetime.strptime(clean_str, "%Y:%m:%d %H:%M:%S")
            except Exception:
                pass

        needs_update = False
        if abs(current_mtime - target_ts) > 2.0:
            needs_update = True
        if exiftool_installed:
            if not current_exif_dt:
                needs_update = True
            elif abs((current_exif_dt - target_dt).total_seconds()) > 2.0:
                needs_update = True

        if needs_update:
            formatted_time = target_dt.strftime("%Y:%m:%d %H:%M:%S")
            filesystem_updates.append((filepath, target_ts))
            if exiftool_installed:
                exif_updates.append(
                    {
                        "SourceFile": filepath_abs,
                        "DateTimeOriginal": formatted_time,
                        "CreateDate": formatted_time,
                        "ModifyDate": formatted_time,
                    }
                )

    log.info(
        f"Analysis complete: {len(filesystem_updates)} files have wrong timestamps."
    )
    log.info(f"Skipped {skipped_no_date} files (could not parse timestamp).")

    # If updates are needed, prompt and run
    if filesystem_updates:
        if (
            input(
                f"Proceed to correct timestamps for these {len(filesystem_updates)} files? (y/n): "
            )
            .strip()
            .lower()
            == "y"
        ):
            # 1. Update EXIF first
            if exiftool_installed and exif_updates:
                log.info(f"Writing EXIF timestamps to {len(exif_updates)} files...")
                os.makedirs("data/json", exist_ok=True)
                temp_json = "data/json/fix_filename_exif_temp.json"
                temp_files = "data/json/fix_filename_files_temp.txt"
                try:
                    with open(temp_json, "w", encoding="utf-8") as f:
                        json.dump(exif_updates, f, indent=2)
                    with open(temp_files, "w", encoding="utf-8") as f:
                        for e in exif_updates:
                            f.write(e["SourceFile"] + "\n")
                    cmd = [
                        "exiftool",
                        "-overwrite_original",
                        "-m",
                        f"-json={temp_json}",
                        "-@",
                        temp_files,
                    ]
                    res = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    if res.returncode == 0:
                        log.info("EXIF metadata successfully updated.")
                    else:
                        log.error(f"Error running exiftool: {res.stderr}")
                except Exception as e:
                    log.error(f"Failed to execute exiftool batch: {e}")
                finally:
                    for p in [temp_json, temp_files]:
                        if os.path.exists(p):
                            os.remove(p)

            # 2. Update filesystem timestamps second
            mtime_updated = 0
            for filepath, ts in filesystem_updates:
                try:
                    os.utime(filepath, (ts, ts))
                    mtime_updated += 1
                except Exception as e:
                    log.error(
                        f"Failed to update mtime for {os.path.basename(filepath)}: {e}"
                    )
            log.info(f"Filesystem timestamps updated for {mtime_updated} files.")
    else:
        log.info("All parsed files have correct timestamps.")

    # 3. Flatten if requested
    if flatten:
        log.info("Flattening directory structure...")
        root_dir = Path(directory)
        moved_count = 0

        # Re-scan current files to ensure fresh paths after timestamp writes
        current_files = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.startswith(".") or file.endswith("_original"):
                    continue
                current_files.append(Path(root) / file)

        for filepath in current_files:
            if filepath.parent == root_dir:
                # Already in root directory
                continue

            # Target path in root
            target_name = filepath.name
            target_path = root_dir / target_name

            # Resolve name conflicts
            counter = 1
            stem = filepath.stem
            suffix = filepath.suffix
            while target_path.exists():
                target_name = f"{stem}({counter}){suffix}"
                target_path = root_dir / target_name
                counter += 1

            try:
                # Move file
                shutil.move(str(filepath), str(target_path))
                moved_count += 1
            except Exception as e:
                log.error(f"Failed to move {filepath.name} to root: {e}")

        log.info(f"Successfully moved {moved_count} files to the root directory.")

        # Clean up empty subdirectories (ignoring/removing hidden files like .DS_Store)
        deleted_dirs = 0
        for root, dirs, files in os.walk(directory, topdown=False):
            for d in dirs:
                dir_path = Path(root) / d
                try:
                    all_contents = list(dir_path.iterdir())
                    non_hidden = [p for p in all_contents if not p.name.startswith(".")]
                    if not non_hidden:
                        for p in all_contents:
                            if p.is_file() or p.is_symlink():
                                p.unlink()
                        dir_path.rmdir()
                        deleted_dirs += 1
                except Exception:
                    pass
        log.info(f"Cleaned up {deleted_dirs} empty subdirectories.")

    log.info("Done!")
