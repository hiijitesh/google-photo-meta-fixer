import re
import os
from datetime import datetime

# Regex patterns for matching date/time from filenames
RE_UNIX_MS = re.compile(r"^(\d{13})")
RE_DATE_TIME = re.compile(
    r"((?:19|20)\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})"
)


def parse_filename_time(filename):
    """Try to parse local time from filename patterns."""
    # 1) Try 13-digit unix timestamp (in ms)
    ms_match = RE_UNIX_MS.search(filename)
    if ms_match:
        ts_ms = int(ms_match.group(1))
        dt = datetime.fromtimestamp(ts_ms / 1000.0)
        return dt

    # 2) Try standard YYYYMMDD_HHMMSS
    dt_match = RE_DATE_TIME.search(filename)
    if dt_match:
        year, month, day, hour, minute, second = map(int, dt_match.groups())
        try:
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            pass

    return None


def names_match(dir_name, csv_name):
    if not dir_name or not csv_name:
        return False
    if dir_name == csv_name:
        return True
    dir_base, _ = os.path.splitext(dir_name)
    csv_base, _ = os.path.splitext(csv_name)
    dir_base = dir_base.replace("-edited", "")
    csv_base = csv_base.replace("-edited", "")
    if dir_base == csv_base:
        return True
    if len(dir_base) >= 20 and len(csv_base) >= 20:
        if dir_base.startswith(csv_base) or csv_base.startswith(dir_base):
            return True
    return False
