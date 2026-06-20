import csv
import json
import os
import datetime
import calendar

def main():
    csv_path = "trash_metadata_completed.csv"
    local_photos_dir = "Photos-3-001"
    drive_index_path = "drive_index.json"

    # 1. Read CSV and prepare expected timestamps
    target_files = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("fileName", "").strip()
            taken_at = row.get("takenAt", "").strip()
            
            if not filename or not taken_at:
                continue

            # Parse '2021-06-25T07:10:38.000Z'
            try:
                dt = datetime.datetime.strptime(taken_at, "%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                try:
                    dt = datetime.datetime.strptime(taken_at, "%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    continue

            expected_ts = calendar.timegm(dt.timetuple())
            target_files[filename] = {
                "taken_at_str": taken_at,
                "expected_ts": expected_ts,
                "dt": dt
            }

    # 2. Read drive index
    print("Loading drive_index.json...")
    try:
        with open(drive_index_path, "r", encoding="utf-8") as f:
            drive_data = json.load(f)
    except FileNotFoundError:
        drive_data = []

    drive_by_name = {}
    for item in drive_data:
        if item.get("IsDir", False):
            continue
        name = item.get("Name", "")
        if name:
            if name not in drive_by_name:
                drive_by_name[name] = []
            drive_by_name[name].append(item)

    # Variables for tracking
    total_files = len(target_files)
    
    local_found = 0
    local_correct_ts = 0
    
    drive_found = 0
    drive_correct_ts = 0

    for filename, info in target_files.items():
        expected_ts = info["expected_ts"]
        
        # --- LOCAL FOLDER CHECK ---
        local_path = os.path.join(local_photos_dir, filename)
        if os.path.exists(local_path):
            local_found += 1
            # Check local mtime
            mtime = int(os.path.getmtime(local_path))
            
            # Allow a small tolerance (e.g. 5 seconds) or check exact
            # We'll check within 60 seconds just to be safe with EXIF rounding
            if abs(mtime - expected_ts) <= 60:
                local_correct_ts += 1

        # --- DRIVE CHECK ---
        candidates = drive_by_name.get(filename, [])
        if not candidates:
            # Try case insensitive
            for k, v in drive_by_name.items():
                if k.lower() == filename.lower():
                    candidates = v
                    break

        if candidates:
            drive_found += 1
            # Check drive ModTime
            # Drive ModTime format: "2026-06-19T22:36:56.574Z"
            is_correct_in_drive = False
            for match in candidates:
                mod_time_str = match.get("ModTime", "")
                if mod_time_str:
                    try:
                        # Attempt to parse
                        # Typical format: 2026-06-19T22:36:56.574Z or 2026-06-19T22:36:56Z
                        if "." in mod_time_str:
                            mod_dt = datetime.datetime.strptime(mod_time_str[:23] + "Z", "%Y-%m-%dT%H:%M:%S.%fZ")
                        else:
                            mod_dt = datetime.datetime.strptime(mod_time_str, "%Y-%m-%dT%H:%M:%SZ")
                        
                        mod_ts = calendar.timegm(mod_dt.timetuple())
                        
                        # Compare with expected
                        if abs(mod_ts - expected_ts) <= 60:
                            is_correct_in_drive = True
                            break
                    except Exception:
                        pass
                        
            if is_correct_in_drive:
                drive_correct_ts += 1


    # Print Results
    print(f"\n--- ANALYSIS RESULTS ---")
    print(f"Total files in CSV: {total_files}")
    print(f"\n[LOCAL FOLDER: {local_photos_dir}]")
    print(f"- Found in folder: {local_found}")
    print(f"- Found with CORRECT timestamps: {local_correct_ts}")
    
    print(f"\n[GOOGLE DRIVE]")
    print(f"- Found in drive (any folder): {drive_found}")
    print(f"- Found with CORRECT timestamps: {drive_correct_ts}")

if __name__ == "__main__":
    main()
