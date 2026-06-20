import csv
import json
import os

def main():
    csv_path = "data/csv/trash_metadata_completed.csv"
    drive_index_path = "drive_index.json"
    remote_name = "jiteshece:"
    base_backup_folder = "photos_backUp/Recovered_Trash"

    target_files = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("fileName", "").strip()
            if not filename:
                continue

            taken_at = row.get("takenAt", "").strip()
            year = "Unknown_Year"
            if taken_at and len(taken_at) >= 4:
                year = taken_at[:4]

            duration_ms = row.get("durationMs", "").strip()
            # If duration is present, or extension is mp4/mov, it's a Video
            ext = filename.lower().split('.')[-1]
            if duration_ms or ext in ['mp4', 'mov', 'avi']:
                media_type = "Videos"
            else:
                media_type = "Photos"

            target_files.append({
                "name": filename,
                "year": year,
                "media_type": media_type
            })

    with open(drive_index_path, "r", encoding="utf-8") as f:
        drive_data = json.load(f)

    drive_lookup = {}
    for item in drive_data:
        if item.get("IsDir", False):
            continue
        name = item["Name"]
        if name not in drive_lookup:
            drive_lookup[name] = []
        drive_lookup[name].append(item)

    commands_file = "logs/rclone_commands_trash.txt"
    output_script = "scripts/run_backup_trash.sh"
    matched_count = 0
    missing_files = []

    with open(commands_file, "w", encoding="utf-8") as cf:
        for entry in target_files:
            filename = entry["name"]
            year = entry["year"]
            media_type = entry["media_type"]

            if filename not in drive_lookup:
                missing_files.append(filename)
                continue

            # Pick the first match
            drive_matches = drive_lookup[filename]
            source_path = drive_matches[0]["Path"]
            target_path = f"{base_backup_folder}/{media_type}/{year}/{filename}"

            cmd = f'rclone copyto --ignore-existing "{remote_name}{source_path}" "{remote_name}{target_path}"'
            cf.write(cmd + "\n")
            matched_count += 1

    with open(output_script, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write(f"# Auto-generated rclone copy script — {matched_count} files, 10 at a time\n\n")
        f.write("MAX_JOBS=10\n")
        f.write("PIDS=()\n\n")
        f.write("run_jobs() {\n")
        f.write("  while IFS= read -r cmd; do\n")
        f.write('    dest=$(echo "$cmd" | grep -oE \\\'"[^"]+"\\\' | tail -1 | tr -d \\\'"\\\')\n')
        f.write('    fname=$(basename "$dest")\n')
        f.write('    echo "[->] Copying: $fname"\n')
        f.write('    (eval "$cmd" && echo "[OK] Done:   $fname") &\n')
        f.write('    PIDS+=("$!")\n')
        f.write('    if (( ${#PIDS[@]} >= MAX_JOBS )); then\n')
        f.write('      wait -n\n')
        f.write('      new_pids=()\n')
        f.write('      for pid in "${PIDS[@]}"; do\n')
        f.write('        if kill -0 "$pid" 2>/dev/null; then new_pids+=("$pid"); fi\n')
        f.write('      done\n')
        f.write('      PIDS=("${new_pids[@]}")\n')
        f.write("    fi\n")
        f.write("  done < " + commands_file + "\n")
        f.write("  wait\n")
        f.write("}\n\n")
        f.write(f'echo "Starting copy of {matched_count} files into {base_backup_folder}/ (up to 10 parallel)..."\n')
        f.write("echo \"\"\n")
        f.write("run_jobs\n")
        f.write("echo \"\"\n")
        f.write('echo "Done! All files copied."\n')

    os.chmod(output_script, 0o755)

    print(f"Matched: {matched_count}")
    print(f"Missing: {len(missing_files)}")
    if missing_files:
        with open("logs/missing_files_trash.txt", "w", encoding="utf-8") as f:
            for m in missing_files:
                f.write(m + "\n")

if __name__ == "__main__":
    main()
