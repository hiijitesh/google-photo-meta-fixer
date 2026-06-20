#!/bin/bash
# Upload script — 59 files

MAX_JOBS=5
count=0

echo "Starting upload of 59 files to jiteshece,root_folder_id=1zROCSHekoCeW5QiBZSN8g9fZjB7A0AVe:/ (up to 5 parallel)..."
echo ""

while IFS= read -r cmd; do
  # Extract the last part of the command (the destination path) and get its basename
  fname=$(echo "$cmd" | awk -F'"' '{print $4}' | awk -F'/' '{print $NF}')
  
  if [ -n "$fname" ]; then
    echo "[->] Uploading: $fname"
  else
    echo "[->] Uploading..."
  fi
  
  # Run the command in background
  (eval "$cmd" && echo "[OK] Done:   $fname") &
  
  count=$((count + 1))
  
  # Wait for batch of jobs to finish
  if [ "$count" -ge "$MAX_JOBS" ]; then
    wait
    count=0
  fi
done < logs/rclone_upload_trash.txt

# Wait for the remaining background jobs to finish
wait

echo ""
echo "Done! All files uploaded."
