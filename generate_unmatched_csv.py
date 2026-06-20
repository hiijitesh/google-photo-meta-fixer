import csv

def main():
    original_csv = "og metadata (1).csv"
    missing_txt = "missing_files_og.txt"
    unmatched_csv = "unmatched_metadata.csv"

    # Load missing filenames
    missing_files = set()
    try:
        with open(missing_txt, "r", encoding="utf-8") as f:
            for line in f:
                missing_files.add(line.strip())
    except FileNotFoundError:
        print(f"Error: {missing_txt} not found.")
        return

    # Process original CSV and write to unmatched CSV
    with open(original_csv, "r", encoding="utf-8") as fin:
        reader = csv.reader(fin)
        header = next(reader)

        # Get index of fileName column
        try:
            filename_idx = header.index("fileName")
        except ValueError:
            print("Error: 'fileName' column not found in original CSV.")
            return

        with open(unmatched_csv, "w", encoding="utf-8", newline="") as fout:
            writer = csv.writer(fout)
            writer.writerow(header)

            count = 0
            for row in reader:
                # Make sure the row has enough columns
                if len(row) > filename_idx:
                    filename = row[filename_idx].strip()
                    if filename in missing_files:
                        writer.writerow(row)
                        count += 1

    print(f"Successfully wrote {count} missing records to {unmatched_csv}")

if __name__ == "__main__":
    main()
