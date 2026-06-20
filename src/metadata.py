import json
import os
from datetime import datetime, timezone
from pathlib import Path
from src.sync import run_rclone_commands
from src.logger import log

def get_local_files(directory):
    local_files = {}
    if not os.path.isdir(directory):
        return local_files
        
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.startswith('.'): continue
            path = os.path.join(root, file)
            mtime = os.path.getmtime(path)
            dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
            local_files[file] = {'path': path, 'mtime': mtime, 'dt': dt}
    return local_files

def cmd_metadata_fix_drive(remote_name):
    log.info("=== Google Drive Metadata Fix ===")
    drive_index_path = 'data/json/drive_index_photo_backUp.json'
    if not os.path.exists(drive_index_path):
        log.error(f"Error: {drive_index_path} not found.")
        return

    local_backup = get_local_files('data/photos/photos_backUp')
    local_trash = get_local_files('data/photos/Trashed Photos-3-001')
    
    local_files = {}
    local_files.update(local_backup)
    local_files.update(local_trash)

    with open(drive_index_path, 'r', encoding='utf-8') as f:
        drive_data = json.load(f)

    if not remote_name.endswith(":"):
        remote_name += ":"

    touch_commands = []
    mismatch_count = 0

    log.info("Comparing timestamps with Drive index...")
    for entry in drive_data:
        path = entry.get('Path') or entry.get('path')
        if not path or entry.get('IsDir'): continue
        
        if path.startswith('photos_backUp/'):
            name = entry.get('Name') or entry.get('name')
            if name in local_files:
                drive_mtime_str = entry.get('ModTime') or entry.get('modTime')
                try:
                    drive_dt = datetime.fromisoformat(drive_mtime_str.replace('Z', '+00:00'))
                    local_dt = local_files[name]['dt']
                    diff_seconds = abs((drive_dt - local_dt).total_seconds())
                    
                    if diff_seconds > 2.0:
                        mismatch_count += 1
                        local_utc_dt = local_dt.astimezone(timezone.utc)
                        timestamp_str = local_utc_dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]
                        touch_commands.append(f'rclone touch --timestamp "{timestamp_str}" "{remote_name}{path}"')
                except Exception as e:
                    log.error(f"Error comparing dates for {name}: {e}")

    log.info(f"Total mismatched files identified: {mismatch_count}")
    
    if touch_commands:
        if input("Run fix via rclone touch now? (y/n): ").strip().lower() == 'y':
            run_rclone_commands(touch_commands)

def cmd_metadata_fix_local():
    log.info("=== Local Files Metadata Fix ===")
    log.info("Migrating logic from fix_local_timestamps.py... (To be fully implemented if needed)")
