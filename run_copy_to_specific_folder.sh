#!/bin/bash
# Auto-generated rclone copy script to specific folder — serial execution

echo "Starting server-side copy of matched files to target folder..."
echo ""

while IFS= read -r cmd; do
  dest=$(echo "$cmd" | grep -oE '"[^"]+"' | tail -1 | tr -d '"')
  fname=$(basename "$dest")
  echo "[->] Copying: $fname"

  # Run command
  eval "$cmd"

  if [ $? -eq 0 ]; then
    echo "[OK] Done:   $fname"
  else
    echo "[ERROR] Failed: $fname"
  fi
done < rclone_copy_to_specific_folder.txt

echo ""
echo "Done! All files processed."
