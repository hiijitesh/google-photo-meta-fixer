import argparse
import sys
from src.sync import (
    cmd_sync_backup,
    cmd_sync_consuming,
    cmd_sync_upload_local,
)
from src.metadata import (
    cmd_metadata_fix_drive,
    cmd_metadata_fix_local,
    cmd_metadata_verify_csv,
    cmd_metadata_verify_takeout,
    cmd_metadata_fix_filename,
)


def main():
    parser = argparse.ArgumentParser(
        description="Google Photos Cleaner CLI - Manage Google Photos storage and metadata",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available subcommands and their usage:

1. Sync (Manage cloud-to-cloud sync & uploads)
   - gp-cleaner sync backup [--remote REMOTE]
   - gp-cleaner sync consuming --csv CSV [--remote REMOTE]
   - gp-cleaner sync upload-local --dir DIR --dest DEST [--remote REMOTE]

2. Metadata (Audit & fix timestamps)
   - gp-cleaner metadata fix-drive [--remote REMOTE]
   - gp-cleaner metadata fix-local --csv CSV --dir DIR
   - gp-cleaner metadata verify-csv --csv CSV --dir DIR [--show-missing]
   - gp-cleaner metadata verify-takeout
   - gp-cleaner metadata fix-filename --dir DIR [--flatten]

3. Process (Write metadata & filesystem times)
   - gp-cleaner process backup [--csv [CSV ...]] [--dir [DIR ...]] [--write-exif]
   - gp-cleaner process takeout --dir DIR

Use 'gp-cleaner [command] --help' or 'gp-cleaner [command] [subcommand] --help' for details on specific options.
""",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Sync commands
    sync_parser = subparsers.add_parser("sync", help="Sync files with Google Drive")
    sync_sub = sync_parser.add_subparsers(dest="subcommand", required=True)

    backup_parser = sync_sub.add_parser("backup", help="Sync backup photos")
    backup_parser.add_argument("--remote", default="gdrive:", help="Rclone remote name")

    consuming_parser = sync_sub.add_parser(
        "consuming", help="Sync space-consuming photos from CSV metadata"
    )
    consuming_parser.add_argument(
        "--csv", required=True, help="Path to GPTK consuming metadata CSV file"
    )
    consuming_parser.add_argument(
        "--remote", default="gdrive:", help="Rclone remote name"
    )
    consuming_parser.add_argument(
        "--dest",
        default="",
        help="Destination subfolder name under photos_backUp (e.g. 22v2)",
    )

    upload_local_parser = sync_sub.add_parser(
        "upload-local", help="Upload local files to Drive if missing in index"
    )
    upload_local_parser.add_argument(
        "--dir", required=True, help="Local directory containing files"
    )
    upload_local_parser.add_argument(
        "--remote", default="gdrive:", help="Rclone remote name"
    )
    upload_local_parser.add_argument(
        "--dest",
        required=True,
        help="Destination folder name under photos_backUp (e.g. O Consuming)",
    )

    # Metadata commands
    meta_parser = subparsers.add_parser("metadata", help="Fix timestamps and metadata")
    meta_sub = meta_parser.add_subparsers(dest="subcommand", required=True)

    fix_drive_parser = meta_sub.add_parser(
        "fix-drive", help="Fix mismatched timestamps on Drive"
    )
    fix_drive_parser.add_argument(
        "--remote", default="gdrive:", help="Rclone remote name"
    )

    fix_local_parser = meta_sub.add_parser(
        "fix-local",
        help="Write corrected timestamps from CSV into local photo EXIF headers and filesystem dates",
    )
    fix_local_parser.add_argument(
        "--csv", required=True, help="Path to CSV metadata file"
    )
    fix_local_parser.add_argument(
        "--dir", required=True, help="Directory containing photos"
    )

    verify_csv_parser = meta_sub.add_parser(
        "verify-csv", help="Verify local photo timestamps against a CSV metadata file"
    )
    verify_csv_parser.add_argument(
        "--csv", required=True, help="Path to CSV metadata file"
    )
    verify_csv_parser.add_argument(
        "--dir", required=True, help="Directory containing photos"
    )
    verify_csv_parser.add_argument(
        "--show-missing",
        action="store_true",
        default=False,
        help="Print the full list of files missing from directory and extra files not in CSV",
    )

    meta_sub.add_parser(
        "verify-takeout",
        help="Verify local photo timestamps and EXIF tags against Google Takeout match log index",
    )

    fix_filename_parser = meta_sub.add_parser(
        "fix-filename",
        help="Fix local photo timestamps from filename/path and optionally flatten",
    )
    fix_filename_parser.add_argument(
        "--dir", required=True, help="Directory containing photos"
    )
    fix_filename_parser.add_argument(
        "--flatten",
        action="store_true",
        default=False,
        help="Flatten all subdirectories to the root",
    )

    # Process commands (Placeholder for now)
    process_parser = subparsers.add_parser(
        "process", help="Process local photos based on CSV metadata"
    )
    process_sub = process_parser.add_subparsers(dest="subcommand", required=True)

    backup_parser = process_sub.add_parser("backup", help="Process backup photos")
    backup_parser.add_argument("--csv", nargs="*", help="Optional custom CSV path(s)")
    backup_parser.add_argument(
        "--dir", nargs="*", help="Optional custom directory path(s)"
    )
    backup_parser.add_argument(
        "--write-exif",
        action="store_true",
        default=False,
        help="Also embed corrected timestamps into EXIF headers using exiftool (required for Web UI downloads with manually-edited dates)",
    )

    takeout_parser = process_sub.add_parser(
        "takeout", help="Process Google Takeout directories merging JSON metadata"
    )
    takeout_parser.add_argument(
        "--dir", required=True, help="Path to Google Takeout directory"
    )

    args = parser.parse_args()

    if args.command == "sync":
        if args.subcommand == "backup":
            cmd_sync_backup(args.remote)
        elif args.subcommand == "consuming":
            cmd_sync_consuming(args.csv, args.remote, args.dest)
        elif args.subcommand == "upload-local":
            cmd_sync_upload_local(args.dir, args.remote, args.dest)

    elif args.command == "metadata":
        if args.subcommand == "fix-drive":
            cmd_metadata_fix_drive(args.remote)
        elif args.subcommand == "fix-local":
            cmd_metadata_fix_local(args.csv, args.dir)
        elif args.subcommand == "verify-csv":
            cmd_metadata_verify_csv(args.csv, args.dir, show_missing=args.show_missing)
        elif args.subcommand == "verify-takeout":
            cmd_metadata_verify_takeout()
        elif args.subcommand == "fix-filename":
            cmd_metadata_fix_filename(args.dir, flatten=args.flatten)

    elif args.command == "process":
        if args.subcommand == "backup":
            import src.process_backup as bp

            bp.main(
                csv_paths=args.csv, directories=args.dir, write_exif=args.write_exif
            )
        elif args.subcommand == "takeout":
            import src.process_takeout as pt

            pt.main(args.dir)


if __name__ == "__main__":
    main()
