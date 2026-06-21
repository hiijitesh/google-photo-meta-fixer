import os
import subprocess
import json
import csv
from pathlib import Path
from src.logger import log

def run_rclone_commands(commands, max_jobs=10):
    log.info(f"Executing {len(commands)} rclone commands ({max_jobs} parallel)...")
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
    log_file_path = "logs/rclone_execution.log"
    with open(log_file_path, "a", encoding="utf-8") as log_file:
        subprocess.run(["bash", script_path], stdout=log_file, stderr=log_file, check=True)
    log.info("Execution complete. (Logs saved to logs/rclone_execution.log)")

def cmd_sync_backup(remote_name):
    log.info("=== Google Photos -> Google Drive Backup Matcher ===")
    csv_path = "data/csv/metadata.csv"
    if not os.path.exists(csv_path):
        log.error(f"Error: {csv_path} not found.")
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
        log.warning("No matching files found.")
        return

    drive_index_path = "data/json/drive_index.json"
    if not os.path.exists(drive_index_path):
        log.error("Error: drive_index.json not found.")
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

    log.info(f"Matched: {len(commands)}, Missing: {len(missing_files)}")
    if commands:
        if input("Run backup now? (y/n): ").strip().lower() == 'y':
            run_rclone_commands(commands)

def cmd_sync_trash(remote_name):
    log.info("=== Google Photos -> Trash Sync ===")
    csv_path = "data/csv/trash_metadata_completed.csv"
    if not os.path.exists(csv_path):
        log.error(f"Error: {csv_path} not found.")
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

    drive_index_path = "data/json/drive_index.json"
    if not os.path.exists(drive_index_path):
        log.error("Error: drive_index.json not found.")
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

    log.info(f"Matched: {len(commands)}, Missing: {len(missing_files)}")
    if commands:
        if input("Run sync now? (y/n): ").strip().lower() == 'y':
            run_rclone_commands(commands)

def cmd_sync_consuming(csv_path, remote_name):
    log.info("=== Google Drive Consuming Album Sync ===")
    if not os.path.exists(csv_path):
        log.error(f"Error: CSV file {csv_path} not found.")
        return

    target_files = set()
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            filename = row.get("fileName", "").strip()
            if filename:
                target_files.add(filename)

    if not target_files:
        log.warning("No filenames found in CSV.")
        return

    drive_index_path = "data/json/drive_index.json"
    if not os.path.exists(drive_index_path):
        log.error("Error: drive_index.json not found.")
        return

    with open(drive_index_path, "r", encoding="utf-8") as f:
        drive_lookup_lower = {}
        for item in json.load(f):
            if not item.get("IsDir", False):
                name = item.get("Name") or item.get("name")
                if name:
                    drive_lookup_lower.setdefault(name.lower(), []).append(item)

    if not remote_name.endswith(":"):
        remote_name += ":"

    commands = []
    already_backed_up = []
    missing_files = []
    other_places = []

    for filename in sorted(target_files):
        filename_lower = filename.lower()
        if filename_lower not in drive_lookup_lower:
            missing_files.append(filename)
            continue

        # Check if already in photos_backUp
        in_backup = False
        exact_entry = None
        for entry in drive_lookup_lower[filename_lower]:
            path = entry.get("Path") or entry.get("path")
            if path.startswith("photos_backUp/"):
                in_backup = True
            # Prefer exact name match if available
            if entry.get("Name") == filename or exact_entry is None:
                exact_entry = entry

        if in_backup:
            already_backed_up.append(filename)
        else:
            other_places.append((filename, exact_entry))
            # Destination path: directly inside photos_backUp (don't create subfolders)
            drive_filename = exact_entry.get("Name") or exact_entry.get("name")
            source_path = exact_entry["Path"]
            target_path = f"photos_backUp/{drive_filename}"
            commands.append(f'rclone copyto --ignore-existing "{remote_name}{source_path}" "{remote_name}{target_path}"')

    log.info("Summary:")
    log.info(f"  Total unique files in CSV: {len(target_files)}")
    log.info(f"  Already in photos_backUp: {len(already_backed_up)}")
    log.info(f"  Missing from Google Drive: {len(missing_files)}")
    log.info(f"  Found in Drive but not in photos_backUp: {len(other_places)}")

    if other_places:
        log.info("Files to be added to photos_backUp:")
        for name, entry in other_places:
            log.info(f"  - {name} (currently at: {entry['Path']})")

    if commands:
        if input("Run copy commands now? (y/n): ").strip().lower() == 'y':
            run_rclone_commands(commands)
    else:
        log.info("No files need to be copied.")

