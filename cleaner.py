import argparse
import sys
from src.sync import cmd_sync_backup, cmd_sync_trash, cmd_sync_consuming
from src.metadata import cmd_metadata_fix_drive, cmd_metadata_fix_local

def main():
    parser = argparse.ArgumentParser(description="Google Photos Cleaner CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Sync commands
    sync_parser = subparsers.add_parser("sync", help="Sync files with Google Drive")
    sync_sub = sync_parser.add_subparsers(dest="subcommand", required=True)
    
    backup_parser = sync_sub.add_parser("backup", help="Sync backup photos")
    backup_parser.add_argument("--remote", default="jiteshece:", help="Rclone remote name")
    
    trash_parser = sync_sub.add_parser("trash", help="Sync trashed photos")
    trash_parser.add_argument("--remote", default="jiteshece:", help="Rclone remote name")
    
    consuming_parser = sync_sub.add_parser("consuming", help="Sync space-consuming photos from CSV metadata")
    consuming_parser.add_argument("--csv", required=True, help="Path to GPTK consuming metadata CSV file")
    consuming_parser.add_argument("--remote", default="jiteshece:", help="Rclone remote name")

    # Metadata commands
    meta_parser = subparsers.add_parser("metadata", help="Fix timestamps and metadata")
    meta_sub = meta_parser.add_subparsers(dest="subcommand", required=True)
    
    fix_drive_parser = meta_sub.add_parser("fix-drive", help="Fix mismatched timestamps on Drive")
    fix_drive_parser.add_argument("--remote", default="jiteshece:", help="Rclone remote name")
    
    meta_sub.add_parser("fix-local", help="Fix local timestamps")

    # Process commands (Placeholder for now)
    process_parser = subparsers.add_parser("process", help="Process local photos based on CSV metadata")
    process_sub = process_parser.add_subparsers(dest="subcommand", required=True)
    process_sub.add_parser("backup", help="Process backup photos")
    process_sub.add_parser("trash", help="Process trashed photos")

    args = parser.parse_args()

    if args.command == "sync":
        if args.subcommand == "backup":
            cmd_sync_backup(args.remote)
        elif args.subcommand == "trash":
            cmd_sync_trash(args.remote)
        elif args.subcommand == "consuming":
            cmd_sync_consuming(args.csv, args.remote)
            
    elif args.command == "metadata":
        if args.subcommand == "fix-drive":
            cmd_metadata_fix_drive(args.remote)
        elif args.subcommand == "fix-local":
            cmd_metadata_fix_local()
            
    elif args.command == "process":
        if args.subcommand == "backup":
            import src.process_backup as bp
            bp.main()
        elif args.subcommand == "trash":
            import src.process_trash as tp
            tp.main()

if __name__ == "__main__":
    main()
