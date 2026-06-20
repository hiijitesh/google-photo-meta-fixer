import os
import json
import re
from datetime import datetime

UNMATCHED_JSON = 'trashed_v3_unmatched.json'

# Standard datetime from Google Photos names
RE_DATE_TIME = re.compile(r'((?:19|20)\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})')
# Screen Recording 2024-12-24 at 12.59.06 AM.mov
RE_SCREEN_REC = re.compile(r'Screen Recording ((?:19|20)\d{2})-(\d{2})-(\d{2}) at (\d{1,2})\.(\d{2})\.(\d{2})\s*(AM|PM)')

def parse_fallback_time(filename):
    # Try Screen Recording
    sr_match = RE_SCREEN_REC.search(filename)
    if sr_match:
        year, month, day, hour, minute, second, ampm = sr_match.groups()
        hour = int(hour)
        if ampm == 'PM' and hour != 12:
            hour += 12
        if ampm == 'AM' and hour == 12:
            hour = 0
        try:
            return datetime(int(year), int(month), int(day), hour, int(minute), int(second))
        except ValueError:
            pass

    # Try standard YYYYMMDD_HHMMSS
    dt_match = RE_DATE_TIME.search(filename)
    if dt_match:
        year, month, day, hour, minute, second = map(int, dt_match.groups())
        try:
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            pass

    return None

def main():
    if not os.path.exists(UNMATCHED_JSON):
        print("No unmatched JSON found.")
        return

    with open(UNMATCHED_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fixed_count = 0
    failed_files = []

    for item in data:
        if item.get("MatchedCSV") == False:
            filename = item["Name"]
            local_path = item.get("LocalPath")

            if not local_path or not os.path.exists(local_path):
                print(f"File not found on disk: {local_path}")
                continue

            parsed_time = parse_fallback_time(filename)
            if parsed_time:
                # Update filesystem timestamps
                target_timestamp = parsed_time.timestamp()
                try:
                    os.utime(local_path, (target_timestamp, target_timestamp))
                    # Mark it as fixed in our JSON for record keeping
                    item["MatchedCSV"] = "FixedFromFilename"
                    fixed_count += 1
                    print(f"Fixed {filename} -> {parsed_time}")
                except Exception as e:
                    print(f"Failed to update {filename}: {e}")
            else:
                failed_files.append(filename)

    # Save the updated JSON
    with open(UNMATCHED_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print(f"\nSuccessfully fixed {fixed_count} timestamps directly from filenames!")
    if failed_files:
        print(f"Still could not extract time for {len(failed_files)} files:")
        for ff in failed_files:
            print("  " + ff)

if __name__ == '__main__':
    main()
