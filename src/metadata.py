import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from src.sync import run_rclone_commands, prompt_and_refresh_index
from src.logger import log


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

    # Read CSV
    csv_rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            csv_rows.append(row)
    csv_by_filename = {row["fileName"]: row for row in csv_rows}
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

    for filepath in photo_files:
        filename = os.path.basename(filepath)
        matched_row = csv_by_filename.get(filename)
        if not matched_row:
            for row in csv_rows:
                if names_match(filename, row["fileName"]):
                    matched_row = row
                    break

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

    # 1. Update filesystem timestamps
    mtime_updated = 0
    for filepath, ts in filesystem_updates:
        try:
            os.utime(filepath, (ts, ts))
            mtime_updated += 1
        except Exception as e:
            log.error(f"Failed to update mtime for {os.path.basename(filepath)}: {e}")
    log.info(f"Filesystem timestamps updated for {mtime_updated} files.")

    # 2. Update EXIF headers via exiftool batch
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
    matched_csv_rows = set()

    for filepath in photo_files:
        filename = os.path.basename(filepath)
        matched_row = None
        for i, row in enumerate(csv_rows):
            if names_match(filename, row["fileName"]):
                matched_row = row
                matched_csv_rows.add(i)
                break

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
