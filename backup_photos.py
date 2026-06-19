import csv
import json
import sys
import os

def main():
    print("=== Google Photos -> Google Drive Rclone Matcher ===")

    # 1. Load the metadata CSV from the Toolkit's "Export Metadata" button
    csv_path = "metadata.csv"
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        print("Please use the GPTK 'Export Metadata' button and save the file as metadata.csv")
        sys.exit(1)

    target_files = []  # list of dicts with {name, year}
    skipped = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            takes_space = row.get("takesUpSpace", "").strip().lower() == "true"
            is_original = row.get("isOriginalQuality", "").strip().lower() == "true"
            filename = row.get("fileName", "").strip()

            if not filename:
                skipped += 1
                continue
            if not takes_space:
                skipped += 1
                continue
            if not is_original:
                skipped += 1
                continue

            # Extract year from takenAt (format: "2022-01-06T06:35:47.182Z")
            taken_at = row.get("takenAt", "").strip()
            year = "Unknown_Year"
            if taken_at and len(taken_at) >= 4:
                year = taken_at[:4]

            target_files.append({"name": filename, "year": year})

    if not target_files:
        print("No matching files found in metadata.csv.")
        print(f"Skipped {skipped} rows (no filename, not space-consuming, or not original quality).")
        sys.exit(0)

    print(f"Found {len(target_files)} original-quality, space-consuming files.")
    print(f"Skipped {skipped} rows (storage saver / no filename).")

    # 2. Load the Google Drive index
    drive_index_path = "drive_index.json"
    if not os.path.exists(drive_index_path):
        print(f"\nError: {drive_index_path} not found.")
        print('Please run: rclone lsjson -R "gdrive:" > drive_index.json')
        sys.exit(1)

    with open(drive_index_path, "r", encoding="utf-8") as f:
        drive_data = json.load(f)

    print(f"Loaded {len(drive_data)} entries from Drive index.")

    # Build a lookup: filename -> list of drive entries (handles duplicates)
    drive_lookup = {}
    for item in drive_data:
        if item.get("IsDir", False):
            continue
        name = item["Name"]
        if name not in drive_lookup:
            drive_lookup[name] = []
        drive_lookup[name].append(item)

    # 3. Get user config
    remote_name = input("\nEnter your rclone Google Drive remote name (e.g., 'gdrive:'): ").strip()
    if not remote_name.endswith(":"):
        remote_name += ":"

    # Hardcoded backup folder — all files go under photos_backUp/<year>/
    backup_folder = "photos_backUp"
    print(f"Backup destination: {remote_name}{backup_folder}/<year>/<filename>")

    output_script = "run_backup.sh"
    commands_file = "rclone_commands.txt"
    matched_count = 0
    duplicate_count = 0
    missing_files = []

    print("\nQueuing files:")
    with open(commands_file, "w", encoding="utf-8") as cf:
        for entry in target_files:
            filename = entry["name"]
            year = entry["year"]

            if filename not in drive_lookup:
                missing_files.append(filename)
                continue

            drive_matches = drive_lookup[filename]

            if len(drive_matches) > 1:
                duplicate_count += 1

            source_path = drive_matches[0]["Path"]
            target_path = f"{backup_folder}/{year}/{filename}"
            print(f"  [{matched_count + 1}] {filename}  ->  {backup_folder}/{year}/")
            cmd = f'rclone copyto --ignore-existing "{remote_name}{source_path}" "{remote_name}{target_path}"'
            cf.write(cmd + "\n")
            matched_count += 1

    # 4. Write the parallel runner script
    with open(output_script, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write(f"# Auto-generated rclone copy script — {matched_count} files, 10 at a time\n\n")
        f.write("MAX_JOBS=10\n")
        f.write("PIDS=()\n\n")
        f.write("run_jobs() {\n")
        f.write("  while IFS= read -r cmd; do\n")
        # Extract destination filename for display (last quoted arg)
        f.write('    dest=$(echo "$cmd" | grep -oE \'"[^"]+"\' | tail -1 | tr -d \'"\')\n')
        f.write('    fname=$(basename "$dest")\n')
        f.write('    echo "[->] Copying: $fname"\n')
        f.write('    (eval "$cmd" && echo "[OK] Done:   $fname") &\n')
        f.write('    PIDS+=("$!")\n')
        f.write('    if (( ${#PIDS[@]} >= MAX_JOBS )); then\n')
        f.write('      wait "${PIDS[0]}"\n')
        f.write('      PIDS=("${PIDS[@]:1}")\n')
        f.write("    fi\n")
        f.write("  done < rclone_commands.txt\n")
        f.write("  wait\n")
        f.write("}\n\n")
        f.write(f'echo "Starting copy of {matched_count} files into {backup_folder}/ (up to 10 parallel)..."\n')
        f.write("echo \"\"\n")
        f.write("run_jobs\n")
        f.write("echo \"\"\n")
        f.write('echo "Done! All files copied."\n')

    os.chmod(output_script, 0o755)

    # 5. Summary
    print(f"\n=== Summary ===")
    print(f"  Matched:    {matched_count} files")
    print(f"  Duplicates: {duplicate_count} files found multiple times in Drive (first copy used)")
    print(f"  Missing:    {len(missing_files)} files not found in Drive")
    print(f"\nGenerated: {output_script}")

    if missing_files:
        with open("missing_files.txt", "w", encoding="utf-8") as f:
            for m in missing_files:
                f.write(m + "\n")
        print(f"Missing files saved to: missing_files.txt")

    print(f'\nRun the backup with: bash run_backup.sh')

if __name__ == "__main__":
    main()
