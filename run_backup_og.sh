#!/bin/bash
# Auto-generated rclone copy script — 26 files, 10 at a time

MAX_JOBS=10
PIDS=()

run_jobs() {
  while IFS= read -r cmd; do
    dest=$(echo "$cmd" | grep -oE \'"[^"]+"\' | tail -1 | tr -d \'"\')
    fname=$(basename "$dest")
    echo "[->] Copying: $fname"
    (eval "$cmd" && echo "[OK] Done:   $fname") &
    PIDS+=("$!")
    if (( ${#PIDS[@]} >= MAX_JOBS )); then
      wait "${PIDS[0]}"
      PIDS=("${PIDS[@]:1}")
    fi
  done < rclone_commands_og.txt
  wait
}

echo "Starting copy of 26 files into photos_backUp/Recovered_Trash/ (up to 10 parallel)..."
echo ""
run_jobs
echo ""
echo "Done! All files copied."
