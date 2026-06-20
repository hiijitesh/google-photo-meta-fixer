import os
import subprocess
import json
import csv
from pathlib import Path

def run_rclone_commands(commands, max_jobs=10):
    print(f"Executing {len(commands)} rclone commands ({max_jobs} parallel)...")
    # Write to a temporary file
    script_path = "logs/rclone_commands_auto.sh"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write(f"MAX_JOBS={max_jobs}\n")
        f.write("PIDS=()\n")
        for cmd in commands:
            f.write(f'({cmd}) &\n')
            f.write('PIDS+=("$!")\n')
            f.write('if (( ${#PIDS[@]} >= MAX_JOBS )); then\n')
            f.write('  wait "${PIDS[0]}"\n')
            f.write('  PIDS=("${PIDS[@]:1}")\n')
            f.write('fi\n')
        f.write("wait\n")

    os.chmod(script_path, 0o755)
    subprocess.run(["bash", script_path], check=True)
    print("Execution complete.")

def cmd_sync_backup(remote_name):
    print("=== Google Photos -> Google Drive Backup Matcher ===")
    csv_path = "data/csv/metadata.csv"
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    target_files = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("takesUpSpace", "").lower() != "true": continue
            if row.get("isOriginalQuality", "").lower() != "true": continue

            filename = row.get("fileName", "").strip()
            if not filename: continue

            taken_at = row.get("takenAt", "").strip()
            year = taken_at[:4] if len(taken_at) >= 4 else "Unknown_Year"
            target_files.append({"name": filename, "year": year})

    if not target_files:
        print("No matching files found.")
        return

    drive_index_path = "drive_index.json"
    if not os.path.exists(drive_index_path):
        print("Error: drive_index.json not found.")
        return

    with open(drive_index_path, "r", encoding="utf-8") as f:
        drive_lookup = {}
        for item in json.load(f):
            if not item.get("IsDir", False):
                drive_lookup.setdefault(item["Name"], []).append(item)

    if not remote_name.endswith(":"):
        remote_name += ":"

    commands = []
    missing_files = []
    for entry in target_files:
        filename = entry["name"]
        if filename not in drive_lookup:
            missing_files.append(filename)
            continue
        source_path = drive_lookup[filename][0]["Path"]
        target_path = f"photos_backUp/{entry['year']}/{filename}"
        commands.append(f'rclone copyto --ignore-existing "{remote_name}{source_path}" "{remote_name}{target_path}"')

    print(f"Matched: {len(commands)}, Missing: {len(missing_files)}")
    if commands:
        if input("Run backup now? (y/n): ").strip().lower() == 'y':
            run_rclone_commands(commands)

def cmd_sync_trash(remote_name):
    print("=== Google Photos -> Trash Sync ===")
    csv_path = "data/csv/trash_metadata_completed.csv"
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    target_files = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            filename = row.get("fileName", "").strip()
            if not filename: continue

            taken_at = row.get("takenAt", "").strip()
            year = taken_at[:4] if len(taken_at) >= 4 else "Unknown_Year"

            duration_ms = row.get("durationMs", "").strip()
            ext = filename.lower().split('.')[-1]
            media_type = "Videos" if duration_ms or ext in ['mp4', 'mov', 'avi'] else "Photos"

            target_files.append({"name": filename, "year": year, "media_type": media_type})

    drive_index_path = "drive_index.json"
    if not os.path.exists(drive_index_path):
        print("Error: drive_index.json not found.")
        return

    with open(drive_index_path, "r", encoding="utf-8") as f:
        drive_lookup = {}
        for item in json.load(f):
            if not item.get("IsDir", False):
                drive_lookup.setdefault(item["Name"], []).append(item)

    if not remote_name.endswith(":"):
        remote_name += ":"

    base_backup_folder = "photos_backUp/Recovered_Trash"
    commands = []
    missing_files = []

    for entry in target_files:
        filename = entry["name"]
        if filename not in drive_lookup:
            missing_files.append(filename)
            continue

        source_path = drive_lookup[filename][0]["Path"]
        target_path = f"{base_backup_folder}/{entry['media_type']}/{entry['year']}/{filename}"
        commands.append(f'rclone copyto --ignore-existing "{remote_name}{source_path}" "{remote_name}{target_path}"')

    print(f"Matched: {len(commands)}, Missing: {len(missing_files)}")
    if commands:
        if input("Run sync now? (y/n): ").strip().lower() == 'y':
            run_rclone_commands(commands)

