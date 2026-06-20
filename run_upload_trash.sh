#!/bin/bash
# Auto-generated rclone upload script — 59 files, 5 at a time

MAX_JOBS=5
PIDS=()

run_jobs() {
  while IFS= read -r cmd; do
    dest=$(echo "$cmd" | grep -oE \'"[^"]+"\' | tail -1 | tr -d \'"\')
    fname=$(basename "$dest")
    echo "[->] Uploading: $fname"
    (eval "$cmd" && echo "[OK] Done:   $fname") &
    PIDS+=("$!")
    if (( ${#PIDS[@]} >= MAX_JOBS )); then
      wait -n
      new_pids=()
      for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then new_pids+=("$pid"); fi
      done
      PIDS=("${new_pids[@]}")
    fi
  done < rclone_upload_trash.txt
  wait
}

echo "Starting upload of 59 files to jiteshece:photos_backUp/Recovered_Trash/ (up to 5 parallel)..."
echo ""
run_jobs
echo ""
echo "Done! All files uploaded."
