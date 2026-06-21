import os
import json
import csv
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Directories and files
DRIVE_INDEX_PATH = "data/json/drive_index.json"
CSV_PATH = "data/csv/Trash_v3_metadata (2).csv"
DIRECTORIES = ["data/photos/Photos-3-001 (3)", "data/photos/Photos-3-001 (4)"]

MATCHED_OUTPUT = "data/json/trashed_v3_match.json"
UNMATCHED_OUTPUT = "data/json/trashed_v3_unmatched.json"

# Regex patterns
RE_UNIX_MS = re.compile(r"^(\d{13})")
RE_DATE_TIME = re.compile(
    r"((?:19|20)\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})"
)


def parse_filename_time(filename):
    """Try to extract a naive local datetime from the filename."""
    # Try Unix MS first
    ms_match = RE_UNIX_MS.search(filename)
    if ms_match:
        ts_ms = int(ms_match.group(1))
        # This will give the local datetime
        return datetime.fromtimestamp(ts_ms / 1000.0)

    # Try typical YYYYMMDD_HHMMSS
    dt_match = RE_DATE_TIME.search(filename)
    if dt_match:
        year, month, day, hour, minute, second = map(int, dt_match.groups())
        try:
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            pass  # Invalid date

    return None


def main():
    # 1. Load drive_index.json
    print(f"Loading {DRIVE_INDEX_PATH}...")
    drive_lookup = {}
    with open(DRIVE_INDEX_PATH, "r", encoding="utf-8") as f:
        drive_data = json.load(f)
        for entry in drive_data:
            if not entry.get("IsDir", False):
                key = (entry.get("Name"), entry.get("Size"))
                drive_lookup[key] = entry
    print(f"Loaded {len(drive_lookup)} files from drive index.")

    # 2. Load CSV and build a list of (utc_dt, local_dt, raw_row)
    print(f"Loading {CSV_PATH}...")
    csv_entries = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            taken_at_str = row.get("takenAt", "")
            if not taken_at_str:
                continue

            # Parse takenAt e.g. 2021-07-28T06:54:29.891Z
            try:
                # Remove Z and parse
                taken_at_str = taken_at_str.replace("Z", "+00:00")
                utc_dt = datetime.fromisoformat(taken_at_str)

                # Get offset
                offset_ms = row.get("timezoneOffsetMs", "")
                offset_ms = int(offset_ms) if offset_ms else 0

                # Compute naive local datetime
                local_dt = (utc_dt + timedelta(milliseconds=offset_ms)).replace(
                    tzinfo=None
                )

                csv_entries.append({"utc_dt": utc_dt, "local_dt": local_dt, "row": row})
            except Exception as e:
                print(f"Error parsing date {taken_at_str}: {e}")

    print(f"Loaded {len(csv_entries)} valid timestamp entries from CSV.")

    # 3. Process local files
    matched_drive = []
    unmatched_drive = []

    files_processed = 0
    timestamps_updated = 0

    for dir_name in DIRECTORIES:
        dir_path = Path(dir_name)
        if not dir_path.exists() or not dir_path.is_dir():
            print(f"Directory {dir_name} not found, skipping...")
            continue

        for filepath in dir_path.iterdir():
            if not filepath.is_file():
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
                # Update local file timestamp
                # os.utime expects timestamp in seconds since epoch.
                # utc_dt.timestamp() provides exactly this because it's aware it's UTC.
                target_timestamp = best_csv_match["utc_dt"].timestamp()
                try:
                    os.utime(filepath, (target_timestamp, target_timestamp))
                    timestamps_updated += 1
                except Exception as e:
                    print(f"Failed to update timestamp for {filename}: {e}")
            else:
                if local_time_from_name:
                    print(
                        f"No close CSV match found for {filename} (parsed time: {local_time_from_name})"
                    )
                else:
                    print(f"Could not parse time from filename: {filename}")

            # Check drive index
            drive_key = (filename, filesize)
            if drive_key in drive_lookup:
                matched_drive.append(drive_lookup[drive_key])
            else:
                unmatched_drive.append(
                    {
                        "Name": filename,
                        "Size": filesize,
                        "LocalPath": str(filepath),
                        "MatchedCSV": best_csv_match is not None,
                    }
                )

    print(f"Processed {files_processed} local files.")
    print(f"Updated timestamps for {timestamps_updated} files.")

    # 4. Save JSONs
    print(f"Matched in Drive: {len(matched_drive)}")
    print(f"Unmatched in Drive: {len(unmatched_drive)}")

    with open(MATCHED_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(matched_drive, f, indent=2)

    with open(UNMATCHED_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(unmatched_drive, f, indent=2)

    print("Done!")


if __name__ == "__main__":
    main()
