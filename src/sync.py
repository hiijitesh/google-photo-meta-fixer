import os
import subprocess
import json
import csv
from pathlib import Path
from src.logger import log


def prompt_and_refresh_index(remote_name, backup_only=False):
    if not remote_name.endswith(":"):
        remote_name += ":"

    target_path = "drive_index_photo_backUp.json" if backup_only else "drive_index.json"
    cache_path = f"data/json/{target_path}"

    prompt_msg = f"Do you want to refresh the Google Drive index cache ({target_path})? (y/n) [y]: "
    user_input = input(prompt_msg).strip().lower()

    if user_input in ["", "y", "yes"]:
        os.makedirs("data/json", exist_ok=True)
        log.info(f"Refreshing index cache from Google Drive remote '{remote_name}'...")

        source = f"{remote_name}photos_backUp" if backup_only else remote_name
        cmd = ["rclone", "lsjson", "-R", source]

        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(res.stdout)
            log.info("Index cache refreshed successfully.")
        except subprocess.CalledProcessError as e:
            log.error(f"Error running rclone lsjson: {e.stderr}")
            if not os.path.exists(cache_path):
                log.error("No cached index file exists. Cannot proceed.")
                raise e
            else:
                log.warning("Failed to refresh. Proceeding with existing cache.")
    else:
        log.info("Skipping index cache refresh. Using existing local cache.")


def run_rclone_commands(commands, max_jobs=10):
    log.info(f"Executing {len(commands)} rclone commands ({max_jobs} parallel)...")
    # Write to a temporary file
    script_path = "logs/rclone_commands_auto.sh"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write(f"MAX_JOBS={max_jobs}\n")
        f.write("PIDS=()\n")
        for cmd in commands:
            f.write(f"({cmd}) &\n")
            f.write('PIDS+=("$!")\n')
            f.write("if (( ${#PIDS[@]} >= MAX_JOBS )); then\n")
            f.write('  wait "${PIDS[0]}"\n')
            f.write('  PIDS=("${PIDS[@]:1}")\n')
            f.write("fi\n")
        f.write("wait\n")

    os.chmod(script_path, 0o755)
    log_file_path = "logs/rclone_execution.log"
    with open(log_file_path, "a", encoding="utf-8") as log_file:
        subprocess.run(
            ["bash", script_path], stdout=log_file, stderr=log_file, check=True
        )
    log.info("Execution complete. (Logs saved to logs/rclone_execution.log)")


def cmd_sync_backup(remote_name):
    log.info("=== Google Photos -> Google Drive Backup Matcher ===")
    prompt_and_refresh_index(remote_name, backup_only=False)
    csv_path = "data/csv/metadata.csv"
    if not os.path.exists(csv_path):
        log.error(f"Error: {csv_path} not found.")
        return

    target_files = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("takesUpSpace", "").lower() != "true":
                continue
            if row.get("isOriginalQuality", "").lower() != "true":
                continue

            filename = row.get("fileName", "").strip()
            if not filename:
                continue

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
        commands.append(
            f'rclone copyto --ignore-existing "{remote_name}{source_path}" "{remote_name}{target_path}"'
        )

    log.info(f"Matched: {len(commands)}, Missing: {len(missing_files)}")
    if commands:
        if input("Run backup now? (y/n): ").strip().lower() == "y":
            run_rclone_commands(commands)


def cmd_sync_consuming(csv_path, remote_name, dest_subfolder=""):
    log.info("=== Google Drive Consuming Album Sync ===")
    if dest_subfolder:
        log.info(f"Target subfolder: photos_backUp/{dest_subfolder}")
    prompt_and_refresh_index(remote_name, backup_only=False)
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

    # Check if already in the target photos_backUp (or specific subfolder)
    target_prefix = (
        f"photos_backUp/{dest_subfolder}/" if dest_subfolder else "photos_backUp/"
    )

    for filename in sorted(target_files):
        filename_lower = filename.lower()
        if filename_lower not in drive_lookup_lower:
            missing_files.append(filename)
            continue

        # Check if already in photos_backUp under target prefix
        in_backup = False
        exact_entry = None
        for entry in drive_lookup_lower[filename_lower]:
            path = entry.get("Path") or entry.get("path")
            if path.startswith(target_prefix):
                in_backup = True
            # Prefer exact name match if available
            if entry.get("Name") == filename or exact_entry is None:
                exact_entry = entry

        if in_backup:
            already_backed_up.append(filename)
        else:
            if exact_entry is not None:
                other_places.append((filename, exact_entry))
                drive_filename = exact_entry.get("Name") or exact_entry.get("name")
                source_path = exact_entry.get("Path") or exact_entry.get("path")
                if drive_filename and source_path:
                    if dest_subfolder:
                        target_path = f"photos_backUp/{dest_subfolder}/{drive_filename}"
                    else:
                        target_path = f"photos_backUp/{drive_filename}"
                    commands.append(
                        f'rclone copyto --ignore-existing "{remote_name}{source_path}" "{remote_name}{target_path}"'
                    )
            else:
                missing_files.append(filename)

    log.info("Summary:")
    log.info(f"  Total unique files in CSV: {len(target_files)}")
    log.info(f"  Already in target backup: {len(already_backed_up)}")
    log.info(f"  Missing from Google Drive: {len(missing_files)}")
    log.info(f"  Found in Drive but not in target backup: {len(other_places)}")

    if other_places:
        log.info("Files to be added to backup:")
        for name, entry in other_places:
            log.info(f"  - {name} (currently at: {entry['Path']})")

    if commands:
        if input("Run copy commands now? (y/n): ").strip().lower() == "y":
            run_rclone_commands(commands)
    else:
        log.info("No files need to be copied.")


def cmd_sync_upload_local(local_dir, remote_name, dest_subfolder):
    log.info("=== Google Drive Local Upload Sync ===")
    prompt_and_refresh_index(remote_name, backup_only=True)
    if not os.path.isdir(local_dir):
        log.error(f"Error: Local directory {local_dir} not found.")
        return

    drive_index_path = "data/json/drive_index_photo_backUp.json"
    if not os.path.exists(drive_index_path):
        log.error("Error: drive_index_photo_backUp.json not found.")
        return

    # 1. Scan local files and compute relative paths
    local_files = {}
    local_path_obj = Path(local_dir)
    for root, dirs, files in os.walk(local_dir):
        for file in files:
            if file == ".DS_Store":
                continue
            full_path = os.path.join(root, file)
            # Compute relative path from local_dir
            rel_path = str(Path(full_path).relative_to(local_path_obj))
            local_files[file.lower()] = {
                "name": file,
                "rel_path": rel_path,
                "full_path": full_path,
            }

    log.info(f"Found {len(local_files)} local files to check.")

    # 2. Load drive index
    with open(drive_index_path, "r", encoding="utf-8") as f:
        drive_data = json.load(f)

    drive_files = set()
    for item in drive_data:
        if not item.get("IsDir", False):
            name = item.get("Name") or item.get("name")
            if name:
                drive_files.add(name.lower())

    log.info(f"Found {len(drive_files)} files in Google Drive photos_backUp index.")

    # 3. Filter missing files
    missing_rel_paths = []
    for filename_lower, info in local_files.items():
        if filename_lower not in drive_files:
            missing_rel_paths.append(info["rel_path"])

    log.info(f"Missing files from Google Drive: {len(missing_rel_paths)}")
    if missing_rel_paths:
        log.info("First 10 missing files:")
        for rel_path in missing_rel_paths[:10]:
            log.info(f"  - {rel_path}")

    if missing_rel_paths:
        # Write files manifest
        manifest_path = "logs/upload_manifest.txt"
        os.makedirs("logs", exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            for rel_path in sorted(missing_rel_paths):
                f.write(f"{rel_path}\n")

        # Build destination and single optimized rclone command
        if not remote_name.endswith(":"):
            remote_name += ":"
        target_dir = f"{remote_name}photos_backUp/{dest_subfolder}"

        # We use --transfers 10 for parallel thread uploads and --drive-chunk-size 64M for Google Drive performance
        rclone_cmd = [
            "rclone",
            "copy",
            "--files-from",
            manifest_path,
            "--transfers",
            "10",
            "--checkers",
            "16",
            "--drive-chunk-size",
            "64M",
            local_dir,
            target_dir,
        ]

        log.info(
            f"Prepared manifest with {len(missing_rel_paths)} entries at {manifest_path}"
        )
        log.info(f"Running rclone copy with 10 transfer threads...")

        if input("Run multi-threaded upload now? (y/n): ").strip().lower() == "y":
            log_file_path = "logs/rclone_execution.log"
            with open(log_file_path, "a", encoding="utf-8") as log_file:
                # Run rclone directly in a single process
                subprocess.run(rclone_cmd, stdout=log_file, stderr=log_file, check=True)
            log.info("Upload complete! (Logs saved to logs/rclone_execution.log)")
    else:
        log.info("All files are already present on Google Drive.")
