#!/bin/bash

PRIMARY_ID="1CICf-Tj91tDKsTFSGzhkc_mx7ocyzGnu"

DUPLICATES=(
  "1VHiAWKm6GzflOfW9FqBKinuUjsOIxAQv"
  "1Q_y7BpZo_vBYsH3_xM0k_gUru3lEj_i1"
  "1f5JEtqwPyt7TmgIKnZm4i4tcp_TxhcNu"
  "1j-OBERd2OiU2QJ2BCizob8HvGxH5fO7F"
  "1dEOxs8TlQKB6nSnCHWAxeX_W3rgfv9me"
  "1WJL5iCaVc8_TWVGNPsOzByYVRX7Sq6iy"
  "1IQF4qq2p4vMhIG57rathijd12x7l7qZW"
  "1mFkvfNE3SaoIcIprPZu7DLo40fwv6M3T"
)

echo "Starting merge of 8 duplicate Recovered_Trash folders into Primary ID: $PRIMARY_ID"

for DUP_ID in "${DUPLICATES[@]}"; do
  echo "----------------------------------------"
  echo "Processing duplicate folder ID: $DUP_ID"
  
  # Move contents to primary
  echo "[1/2] Moving contents..."
  rclone move "jiteshece,root_folder_id=$DUP_ID:" "jiteshece,root_folder_id=$PRIMARY_ID:" --verbose
  
  if [ $? -eq 0 ]; then
    echo "[2/2] Move successful. Removing empty duplicate folder..."
    rclone rmdir "jiteshece,root_folder_id=$DUP_ID:"
    if [ $? -eq 0 ]; then
      echo "✅ Successfully removed $DUP_ID"
    else
      echo "❌ Error removing $DUP_ID (maybe not empty?)"
    fi
  else
    echo "❌ Error moving contents from $DUP_ID. Skipping removal."
  fi
done

echo "----------------------------------------"
echo "Merge complete!"
