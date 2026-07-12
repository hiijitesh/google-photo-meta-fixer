import re
import os
from datetime import datetime, timedelta, timezone

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


def parse_csv_time(iso_str, offset_ms):
    """
    Parses a UTC ISO string (e.g. '2021-11-25T14:18:58.704Z') and converts it
    to a timezone-aware UTC datetime and a naive local datetime using offset_ms.
    """
    if not iso_str:
        return None, None
    try:
        iso_str = iso_str.replace("Z", "+00:00")
        utc_dt = datetime.fromisoformat(iso_str)
        offset_val = float(offset_ms or 0)
        local_dt = utc_dt + timedelta(milliseconds=offset_val)
        return utc_dt, local_dt.replace(tzinfo=None)
    except Exception:
        return None, None


def is_time_different(current_time_str, target_time_str):
    """
    Returns True if current_time_str is missing/invalid or differs from target_time_str
    by more than 26 hours (to account for timezone offsets).
    """
    if not current_time_str:
        return True
    if current_time_str == target_time_str:
        return False

    try:
        # target_time_str is formatted as "%Y:%m:%d %H:%M:%S+00:00"
        target_dt = datetime.strptime(
            target_time_str, "%Y:%m:%d %H:%M:%S+00:00"
        ).replace(tzinfo=timezone.utc)
        target_ts = target_dt.timestamp()
    except Exception:
        return True

    current_time_str = str(current_time_str).strip()
    if current_time_str in ("0000:00:00 00:00:00", ""):
        return True

    # Check for timezone offset in current time (e.g. "+09:00" or "-05:00")
    match = re.search(r"([+-]\d{2}):?(\d{2})$", current_time_str)
    if match:
        try:
            offset_str = match.group(1) + match.group(2)
            date_part = current_time_str[: -len(match.group(0))].strip()
            date_part = date_part[:19]
            dt_naive = datetime.strptime(date_part, "%Y:%m:%d %H:%M:%S")
            hours = int(match.group(1))
            minutes = int(match.group(2))
            sign = -1 if hours < 0 else 1
            tz = timezone(sign * timedelta(hours=abs(hours), minutes=minutes))
            dt = dt_naive.replace(tzinfo=tz)
            current_ts = dt.astimezone(timezone.utc).timestamp()
            return abs(current_ts - target_ts) > 60.0
        except Exception:
            pass

    # Parse as naive datetime (assume local time)
    try:
        clean_date = current_time_str[:19]
        dt_naive = datetime.strptime(clean_date, "%Y:%m:%d %H:%M:%S")
        dt_target_utc = target_dt.replace(tzinfo=None)
        diff = abs((dt_naive - dt_target_utc).total_seconds())
        # Difference <= 26 hours is assumed to be timezone difference
        return diff > 26 * 3600
    except Exception:
        return True


def is_gps_different(current_val, target_val, tolerance=0.0001):
    """
    Returns True if current_val is missing/invalid or differs from target_val
    by more than the tolerance.
    """
    if target_val is None:
        return False
    if current_val is None:
        return True
    try:
        return abs(float(current_val) - float(target_val)) > tolerance
    except Exception:
        return True


def should_keep_update(exif_entry, current):
    """
    Returns True if the file needs to be updated.
    We skip updating if the core date (DateTimeOriginal or CreateDate) is already
    correct (within 26 hours) and GPS / description are already correct.
    """
    # 1. Date/Time checks
    curr_dto = current.get("DateTimeOriginal")
    curr_cd = current.get("CreateDate")

    target_dt_str = exif_entry.get("DateTimeOriginal")

    date_needs_update = True
    if target_dt_str:
        # Check if either DateTimeOriginal or CreateDate in current is close to target
        dto_diff = is_time_different(curr_dto, target_dt_str) if curr_dto else True
        cd_diff = is_time_different(curr_cd, target_dt_str) if curr_cd else True

        # If either is correct, we don't need to update the date
        if (curr_dto and not dto_diff) or (curr_cd and not cd_diff):
            date_needs_update = False

    # 2. GPS checks
    gps_needs_update = False
    if "GPSLatitude" in exif_entry:
        if is_gps_different(current.get("GPSLatitude"), exif_entry["GPSLatitude"]):
            gps_needs_update = True
    if "GPSLongitude" in exif_entry:
        if is_gps_different(current.get("GPSLongitude"), exif_entry["GPSLongitude"]):
            gps_needs_update = True
    if "GPSAltitude" in exif_entry:
        if is_gps_different(
            current.get("GPSAltitude"), exif_entry["GPSAltitude"], tolerance=5.0
        ):
            gps_needs_update = True

    # 3. Description checks
    desc_needs_update = False
    if "Description" in exif_entry:
        if current.get("Description") != exif_entry["Description"]:
            desc_needs_update = True
    if "UserComment" in exif_entry:
        if current.get("UserComment") != exif_entry["UserComment"]:
            desc_needs_update = True

    # We must update if:
    # - The date needs update
    # - OR GPS needs update
    # - OR description needs update
    if date_needs_update or gps_needs_update or desc_needs_update:
        # If the date was already correct, remove date-related fields from exif_entry
        # so we don't overwrite correct local times with UTC times.
        if not date_needs_update:
            exif_entry.pop("DateTimeOriginal", None)
            exif_entry.pop("CreateDate", None)
            exif_entry.pop("ModifyDate", None)
        return True

    return False
