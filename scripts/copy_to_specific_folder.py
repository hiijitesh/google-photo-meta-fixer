import csv
import json
import os

def main():
    csv_path = "data/csv/trash_metadata_completed.csv"
    drive_index_path = "drive_index.json"
    remote_name = "jiteshece:"
    target_remote = 'jiteshece,root_folder_id="1nK_SdHbpw-yhmR1lbnxILhujpM7Us-5G":'

    # 1. Read CSV
    target_files = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("fileName", "").strip()
            size_bytes = row.get("sizeBytes", "").strip()

            if not filename:
                continue
            
            if size_bytes:
                size_bytes = int(size_bytes)
            else:
                size_bytes = None
            
            target_files.append({
                "name": filename,
                "size": size_bytes
            })

    # 2. Read drive index and group by name and size
    print("Loading drive_index.json...")
    with open(drive_index_path, "r", encoding="utf-8") as f:
        drive_data = json.load(f)

    drive_by_name = {}
    drive_by_size = {}
    
    for item in drive_data:
        if item.get("IsDir", False):
            continue
            
        name = item.get("Name", "")
        if name:
            if name not in drive_by_name:
                drive_by_name[name] = []
            drive_by_name[name].append(item)
            
        size = item.get("Size", 0)
        if size:
            if size not in drive_by_size:
                drive_by_size[size] = []
            drive_by_size[size].append(item)

    # 3. Match
    commands_file = "logs/rclone_copy_to_specific_folder.txt"
    output_script = "scripts/run_copy_to_specific_folder.sh"
    matched_count = 0
    missing_files = []

    with open(commands_file, "w", encoding="utf-8") as cf:
        for entry in target_files:
            filename = entry["name"]
            size = entry["size"]

            # Try by name first
            candidates = drive_by_name.get(filename, [])

            if not candidates:
                # Try case insensitive by name
                for k, v in drive_by_name.items():
                    if k.lower() == filename.lower():
                        candidates = v
                        break
                        
            # If still not found, try by size
            if not candidates and size:
                candidates = drive_by_size.get(size, [])

            if not candidates:
                missing_files.append(filename)
                continue

            best_match = candidates[0]
            source_path = best_match["Path"]
            target_path = filename

            cmd = f'rclone copyto --ignore-existing "{remote_name}{source_path}" "{target_remote}{target_path}"'
            cf.write(cmd + "\n")
            matched_count += 1

    # 4. Write script
    with open(output_script, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write(f"# Auto-generated rclone copy script to specific folder — {matched_count} files, 10 at a time\n\n")
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
        f.write(f'echo "Starting server-side copy of {matched_count} files to target folder (up to 10 parallel)..."\n')
        f.write("echo \"\"\n")
        f.write("run_jobs\n")
        f.write("echo \"\"\n")
        f.write('echo "Done! All files copied."\n')

    os.chmod(output_script, 0o755)

    print(f"Matched: {matched_count}")
    print(f"Missing: {len(missing_files)}")
    if missing_files:
        with open("logs/missing_files_specific_folder.txt", "w", encoding="utf-8") as f:
            for m in missing_files:
                f.write(m + "\n")

if __name__ == "__main__":
    main()
