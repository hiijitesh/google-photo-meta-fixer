import csv
import os
import datetime
import calendar

def main():
    csv_path = "trash_metadata_completed.csv"
    local_photos_dir = "Photos-3-001"

    count = 0
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("fileName", "").strip()
            taken_at = row.get("takenAt", "").strip()

            if not filename or not taken_at:
                continue

            local_path = os.path.join(local_photos_dir, filename)
            if not os.path.exists(local_path):
                continue

            # Parse '2021-06-25T07:10:38.000Z' to timestamp
            # We treat it as UTC time and get the Unix timestamp
            dt = datetime.datetime.strptime(taken_at, "%Y-%m-%dT%H:%M:%S.%fZ")
            timestamp = calendar.timegm(dt.timetuple())

            # Update the modified and accessed time of the local file
            os.utime(local_path, (timestamp, timestamp))
            count += 1
            print(f"Fixed timestamp for: {filename} -> {dt}")

    print(f"\nSuccessfully fixed modified timestamps for {count} files!")
    print("Now you can safely upload them without losing their chronological order.")

if __name__ == "__main__":
    main()
