import csv
import json

csv_path = "og metadata (1).csv"
drive_index_path = "drive_index.json"

target_files = []
with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        filename = row.get("fileName", "").strip()
        if filename:
            target_files.append(filename)

print(f"Found {len(target_files)} files in CSV.")

with open(drive_index_path, "r", encoding="utf-8") as f:
    drive_data = json.load(f)

drive_lookup = set()
for item in drive_data:
    if not item.get("IsDir", False):
        drive_lookup.add(item["Name"])

matched = 0
missing = []
for name in target_files:
    if name in drive_lookup:
        matched += 1
    else:
        missing.append(name)

print(f"Matched: {matched}")
print(f"Missing: {len(missing)}")
if missing:
    print(f"Sample missing: {missing[:5]}")
