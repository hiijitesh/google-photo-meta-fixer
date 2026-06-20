#!/bin/bash
# Auto-generated rclone copy script (matched by size) — 4 files, 10 at a time

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
      wait -n
      new_pids=()
      for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then new_pids+=("$pid"); fi
      done
      PIDS=("${new_pids[@]}")
    fi
  done < rclone_copy_trash_matched.txt
  wait
}

echo "Starting server-side copy of 4 files to jiteshece:photos_backUp/Recovered_Trash/ (up to 10 parallel)..."
echo ""
run_jobs
echo ""
echo "Done! All files copied."
