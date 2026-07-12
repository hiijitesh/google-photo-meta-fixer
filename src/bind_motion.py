import struct
from pathlib import Path
from src.logger import log

# JPEG binary constants
XMP_NAMESPACE = b"http://ns.adobe.com/xap/1.0/\x00"
JPEG_SOI = b"\xff\xd8"
JPEG_APP1 = b"\xff\xe1"
JPEG_SOS = b"\xff\xda"
JPEG_EOI = b"\xff\xd9"

PHOTO_EXTENSIONS = {".jpg", ".jpeg"}
VIDEO_EXTENSIONS = {".mp4", ".MP4", ".mov", ".MOV", ".3gp", ".m4v"}


def is_video_file(path: Path) -> bool:
    """Detect if a file is a video by checking its MP4/MOV magic bytes."""
    try:
        with open(path, "rb") as f:
            header = f.read(12)
        # MP4/MOV containers: bytes 4-7 are 'ftyp', 'moov', or 'mdat' box type
        if len(header) >= 8 and header[4:8] in (b"ftyp", b"moov", b"mdat", b"wide"):
            return True
        return False
    except Exception:
        return False


def build_motion_xmp(video_size: int) -> bytes:
    """Build the XMP payload for Google Motion Photo v1 / MicroVideo format."""
    xmp = (
        '<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="GPC-MotionBinder">\n'
        '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '    <rdf:Description rdf:about=""\n'
        '        xmlns:GCamera="http://ns.google.com/photos/1.0/camera/">\n'
        "      <GCamera:MotionPhoto>1</GCamera:MotionPhoto>\n"
        "      <GCamera:MotionPhotoVersion>1</GCamera:MotionPhotoVersion>\n"
        "      <GCamera:MotionPhotoPresentationTimestampUs>-1"
        "</GCamera:MotionPhotoPresentationTimestampUs>\n"
        "      <GCamera:MicroVideo>1</GCamera:MicroVideo>\n"
        "      <GCamera:MicroVideoVersion>1</GCamera:MicroVideoVersion>\n"
        f"      <GCamera:MicroVideoOffset>{video_size}</GCamera:MicroVideoOffset>\n"
        "      <GCamera:MicroVideoPresentationTimestampUs>-1"
        "</GCamera:MicroVideoPresentationTimestampUs>\n"
        "    </rdf:Description>\n"
        "  </rdf:RDF>\n"
        "</x:xmpmeta>\n"
        '<?xpacket end="w"?>'
    )
    return xmp.encode("utf-8")


def inject_xmp_into_jpeg(jpeg_bytes: bytes, xmp_payload: bytes) -> bytes:
    """
    Inject or replace the XMP APP1 segment in JPEG bytes.
    The new XMP segment is inserted at the earliest APP slot (after SOI),
    replacing any pre-existing XMP APP1 segment.
    """
    if not jpeg_bytes.startswith(JPEG_SOI):
        raise ValueError("Not a valid JPEG file (missing SOI marker)")

    # Build the complete APP1 XMP segment
    seg_body = XMP_NAMESPACE + xmp_payload
    seg_length = len(seg_body) + 2  # +2 for the 2-byte length field itself
    if seg_length > 0xFFFF:
        raise ValueError("XMP payload is too large for a single JPEG APP1 segment")
    xmp_segment = JPEG_APP1 + struct.pack(">H", seg_length) + seg_body

    result = bytearray(jpeg_bytes[:2])  # Start with SOI
    pos = 2
    xmp_inserted = False

    while pos < len(jpeg_bytes):
        if pos + 1 >= len(jpeg_bytes):
            result.extend(jpeg_bytes[pos:])
            break

        if jpeg_bytes[pos] != 0xFF:
            # We've wandered into raw scan data — insert XMP if not yet done, copy rest
            if not xmp_inserted:
                result.extend(xmp_segment)
            result.extend(jpeg_bytes[pos:])
            break

        marker = jpeg_bytes[pos : pos + 2]

        # SOS: start of compressed scan — insert XMP here and copy rest verbatim
        if marker == JPEG_SOS:
            if not xmp_inserted:
                result.extend(xmp_segment)
                xmp_inserted = True
            result.extend(jpeg_bytes[pos:])
            break

        # EOI: graceful end
        if marker == JPEG_EOI:
            if not xmp_inserted:
                result.extend(xmp_segment)
                xmp_inserted = True
            result.extend(jpeg_bytes[pos:])
            break

        # Standard length-prefixed segment
        if pos + 4 > len(jpeg_bytes):
            result.extend(jpeg_bytes[pos:])
            break

        seg_len = struct.unpack(">H", jpeg_bytes[pos + 2 : pos + 4])[0]
        seg_end = pos + 2 + seg_len

        # Detect an existing XMP APP1 and replace it with our new one
        is_existing_xmp = (
            marker == JPEG_APP1
            and jpeg_bytes[pos + 4 : pos + 4 + len(XMP_NAMESPACE)] == XMP_NAMESPACE
        )

        if is_existing_xmp:
            if not xmp_inserted:
                result.extend(xmp_segment)
                xmp_inserted = True
            # Skip old XMP segment (don't copy it)
        else:
            result.extend(jpeg_bytes[pos:seg_end])

        pos = seg_end

    return bytes(result)


def already_bound(jpeg_path: Path) -> bool:
    """
    Quick check whether a JPEG is already a Google Motion Photo
    by scanning the first 64KB for known XMP marker strings.
    """
    try:
        with open(jpeg_path, "rb") as f:
            header = f.read(65536)
        return b"GCamera:MotionPhoto" in header or b"MicroVideoOffset" in header
    except Exception:
        return False


def find_companion_video(jpeg_path: Path, all_filenames: set) -> Path | None:
    """
    Find the companion video file for a motion photo JPEG.
    Tries known video extensions first, then falls back to extensionless files
    that pass the MP4 magic-byte check.
    """
    stem = jpeg_path.stem  # e.g. "IMG_20240906_200648854_MP"

    for ext in VIDEO_EXTENSIONS:
        candidate = jpeg_path.parent / (stem + ext)
        if candidate.name in all_filenames:
            return candidate

    # Extensionless fallback (e.g. "IMG_20240906_200648854_MP" with no .MP4)
    candidate = jpeg_path.parent / stem
    if candidate.name in all_filenames and is_video_file(candidate):
        return candidate

    return None


def main(directory: str):
    """
    Bind companion motion video files into their paired JPEG photos,
    producing Google Motion Photo v1 (MicroVideo) format.

    Args:
        directory:  Path to the folder containing _MP.jpg + _MP.MP4 pairs.
    """
    log.info("=== Google Motion Photo Binder ===")

    dir_path = Path(directory)
    if not dir_path.is_dir():
        log.error(f"Directory not found: {directory}")
        return

    # Index all files for O(1) companion lookup
    all_filenames = {f.name for f in dir_path.iterdir() if not f.name.startswith(".")}

    # Find all _MP photos (motion photo stills)
    mp_photos = sorted(
        f
        for f in dir_path.iterdir()
        if f.suffix.lower() in PHOTO_EXTENSIONS
        and "_mp" in f.stem.lower()
        and not f.name.startswith(".")
    )

    log.info(f"Found {len(mp_photos)} _MP photo(s) to scan.")

    bound_count = 0
    skipped_already_bound = 0
    skipped_no_video = 0
    failed_count = 0

    for photo_path in mp_photos:
        video_path = find_companion_video(photo_path, all_filenames)

        if video_path is None:
            log.debug(f"  No companion video for {photo_path.name} — skipping.")
            skipped_no_video += 1
            continue

        if already_bound(photo_path):
            log.debug(f"  Already a Motion Photo: {photo_path.name} — skipping.")
            skipped_already_bound += 1
            continue

        video_size = video_path.stat().st_size
        log.info(
            f"  Binding: {photo_path.name}"
            f" + {video_path.name} ({video_size:,} B video)"
        )

        try:
            with open(photo_path, "rb") as f:
                jpeg_bytes = f.read()
            with open(video_path, "rb") as f:
                video_bytes = f.read()

            # Inject XMP and append video data
            xmp_payload = build_motion_xmp(len(video_bytes))
            modified_jpeg = inject_xmp_into_jpeg(jpeg_bytes, xmp_payload)

            with open(photo_path, "wb") as f:
                f.write(modified_jpeg)
                f.write(video_bytes)

            video_path.unlink()
            log.debug(f"    Removed standalone video: {video_path.name}")

            bound_count += 1

        except Exception as e:
            log.error(f"  Failed to bind {photo_path.name}: {e}")
            failed_count += 1

    # Summary
    log.info("=== Bind Summary ===")
    log.info(f"  Bound:                {bound_count}")
    log.info(f"  Skipped (no video):   {skipped_no_video}")
    log.info(f"  Skipped (pre-bound):  {skipped_already_bound}")
    log.info(f"  Failed:               {failed_count}")
