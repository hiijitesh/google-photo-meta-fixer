import csv
import json
import os

def main():
    csv_path = "trash_metadata_completed.csv"
    drive_index_path = "drive_index.json"
    remote_name = "jiteshece:"
    base_backup_folder = "photos_backUp/Recovered_Trash"

    # 1. Read CSV
    target_files = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("fileName", "").strip()
            size_bytes = row.get("sizeBytes", "").strip()

            if not filename or not size_bytes:
                continue

            size_bytes = int(size_bytes)
            taken_at = row.get("takenAt", "").strip()
            year = "Unknown_Year"
            if taken_at and len(taken_at) >= 4:
                year = taken_at[:4]

            duration_ms = row.get("durationMs", "").strip()
            ext = filename.lower().split('.')[-1]
            if duration_ms or ext in ['mp4', 'mov', 'avi']:
                media_type = "Videos"
            else:
                media_type = "Photos"

            target_files.append({
                "name": filename,
                "size": size_bytes,
                "year": year,
                "media_type": media_type
            })

    # 2. Read drive index and group by size
    print("Loading drive_index.json...")
    with open(drive_index_path, "r", encoding="utf-8") as f:
        drive_data = json.load(f)

    drive_by_size = {}
    for item in drive_data:
        if item.get("IsDir", False):
            continue
        size = item.get("Size", 0)
        if size not in drive_by_size:
            drive_by_size[size] = []
        drive_by_size[size].append(item)

    # 3. Match
    commands_file = "rclone_copy_trash_matched.txt"
    output_script = "run_copy_trash.sh"
    matched_count = 0
    missing_files = []

    with open(commands_file, "w", encoding="utf-8") as cf:
        for entry in target_files:
            size = entry["size"]
            filename = entry["name"]

            candidates = drive_by_size.get(size, [])

            best_match = None
            if len(candidates) == 1:
                best_match = candidates[0]
            elif len(candidates) > 1:
                # Try to match by exact name
                for c in candidates:
                    if c["Name"] == filename:
                        best_match = c
                        break
                # Or case-insensitive
                if not best_match:
                    for c in candidates:
                        if c["Name"].lower() == filename.lower():
                            best_match = c
                            break
                # Or just pick the first one if same size
                if not best_match:
                    best_match = candidates[0]

            if not best_match:
                missing_files.append(filename)
                continue

            source_path = best_match["Path"]
            year = entry["year"]
            media_type = entry["media_type"]
            target_path = f"{base_backup_folder}/{media_type}/{year}/{filename}"

            cmd = f'rclone copyto --ignore-existing "{remote_name}{source_path}" "{remote_name}{target_path}"'
            cf.write(cmd + "\n")
            matched_count += 1

    # 4. Write script
    with open(output_script, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write(f"# Auto-generated rclone copy script (matched by size) — {matched_count} files, 10 at a time\n\n")
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
        f.write(f'echo "Starting server-side copy of {matched_count} files to {remote_name}{base_backup_folder}/ (up to 10 parallel)..."\n')
        f.write("echo \"\"\n")
        f.write("run_jobs\n")
        f.write("echo \"\"\n")
        f.write('echo "Done! All files copied."\n')

    os.chmod(output_script, 0o755)

    print(f"Matched by size: {matched_count}")
    print(f"Missing: {len(missing_files)}")
    if missing_files:
        with open("missing_files_trash_size_match.txt", "w", encoding="utf-8") as f:
            for m in missing_files:
                f.write(m + "\n")

if __name__ == "__main__":
    main()
