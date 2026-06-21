import os
import json
import csv
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Config
DRIVE_INDEX_PATH = "data/json/drive_index.json"
CSV_PATHS = ["data/csv/og metadata (1).csv", "data/csv/metadata.csv"]
DIRECTORIES = ["data/photos/photos_backUp"]

MATCHED_OUTPUT = "data/json/photos_backUp_match.json"
UNMATCHED_OUTPUT = "data/json/photos_backUp_unmatched.json"

# Regex patterns
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
        # This is UTC timestamp, so we create a local datetime from it for comparison
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


def parse_csv_time(iso_str, offset_ms):
    """Parse UTC ISO string and convert to local time and UTC time."""
    try:
        # e.g., "2021-11-25T14:18:58.704Z"
        iso_str = iso_str.replace("Z", "+00:00")
        utc_dt = datetime.fromisoformat(iso_str)
        # offset_ms is usually milliseconds (e.g. 19800000 for +05:30)
        local_dt = utc_dt + timedelta(milliseconds=int(offset_ms))
        # strip tzinfo for naive comparison
        return utc_dt, local_dt.replace(tzinfo=None)
    except Exception as e:
        return None, None


def main():
    # 1. Load drive index to check if files exist in drive
    print("Loading drive_index.json...")
    drive_files = set()
    if os.path.exists(DRIVE_INDEX_PATH):
        with open(DRIVE_INDEX_PATH, "r", encoding="utf-8") as f:
            drive_data = json.load(f)
            for entry in drive_data:
                name = entry.get("Name") or entry.get("name")
                if name:
                    drive_files.add(name)
        print(f"Loaded {len(drive_files)} files from drive index.")
    else:
        print("drive_index.json not found! Will assume nothing is in Drive.")

    # 2. Parse all CSVs
    csv_entries = []
    for path in CSV_PATHS:
        print(f"Loading {path}...")
        if not os.path.exists(path):
            print(f"Warning: {path} not found.")
            continue
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                taken_at = row.get("takenAt")
                offset = row.get("timezoneOffsetMs", "0")
                if taken_at:
                    utc_dt, local_dt = parse_csv_time(taken_at, offset)
                    if local_dt:
                        csv_entries.append(
                            {"utc_dt": utc_dt, "local_dt": local_dt, "row": row}
                        )
    print(f"Loaded {len(csv_entries)} valid timestamp entries from all CSVs.")

    # 3. Process local files
    matched_files = []
    unmatched_files = []
    files_processed = 0
    updated_timestamps = 0

    for directory in DIRECTORIES:
        if not os.path.isdir(directory):
            print(f"Warning: Directory {directory} not found.")
            continue

        for filepath in Path(directory).rglob("*"):
            if not filepath.is_file():
                continue

            # skip hidden files
            if filepath.name.startswith("."):
                continue

            files_processed += 1
            filename = filepath.name
            filesize = filepath.stat().st_size

            # Match to CSV timestamp
            local_time_from_name = parse_filename_time(filename)
            best_csv_match = None

            if local_time_from_name and csv_entries:
                # Find closest CSV entry checking both local and UTC times
                closest_entry = None
                min_diff = float("inf")

                for entry in csv_entries:
                    diff_local = abs(
                        (entry["local_dt"] - local_time_from_name).total_seconds()
                    )
                    diff_utc = abs(
                        (
                            entry["utc_dt"].replace(tzinfo=None) - local_time_from_name
                        ).total_seconds()
                    )

                    best_diff = min(diff_local, diff_utc)
                    if best_diff < min_diff:
                        min_diff = best_diff
                        closest_entry = entry

                # If it's within a reasonable threshold (e.g. 2 hours) we consider it a match
                if min_diff < 7200:
                    best_csv_match = closest_entry

            if best_csv_match:
                # Get the true UTC timestamp from the CSV
                target_utc = best_csv_match["utc_dt"].timestamp()
                try:
                    os.utime(filepath, (target_utc, target_utc))
                    updated_timestamps += 1
                except Exception as e:
                    print(f"Failed to update timestamp for {filename}: {e}")

                in_drive = filename in drive_files

                matched_files.append(
                    {
                        "Name": filename,
                        "Size": filesize,
                        "LocalPath": str(filepath),
                        "InDrive": in_drive,
                    }
                )
            else:
                if not local_time_from_name:
                    print(f"Could not parse time from filename: {filename}")
                else:
                    print(
                        f"No close CSV match found for {filename} (parsed time: {local_time_from_name})"
                    )

                in_drive = filename in drive_files
                unmatched_files.append(
                    {
                        "Name": filename,
                        "Size": filesize,
                        "LocalPath": str(filepath),
                        "MatchedCSV": False,
                        "InDrive": in_drive,
                    }
                )

    print(f"Processed {files_processed} local files.")
    print(f"Updated timestamps for {updated_timestamps} files using CSV metadata.")

    # 4. Save outputs
    with open(MATCHED_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(matched_files, f, indent=2)

    with open(UNMATCHED_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(unmatched_files, f, indent=2)

    in_drive_count = sum(1 for x in matched_files if x["InDrive"])
    not_in_drive_count = len(matched_files) - in_drive_count

    unmatched_in_drive = sum(1 for x in unmatched_files if x["InDrive"])
    unmatched_not_in_drive = len(unmatched_files) - unmatched_in_drive

    print(
        f"Matched & Updated: {len(matched_files)} (In Drive: {in_drive_count}, Not In Drive: {not_in_drive_count})"
    )
    print(
        f"Unmatched: {len(unmatched_files)} (In Drive: {unmatched_in_drive}, Not In Drive: {unmatched_not_in_drive})"
    )
    print("Done!")


if __name__ == "__main__":
    main()
