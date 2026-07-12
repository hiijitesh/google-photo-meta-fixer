import os
import subprocess
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


# Removing inject_xmp_into_jpeg. Exiftool will handle injection.


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

    import shutil

    if shutil.which("exiftool") is None:
        log.error(
            "Error: exiftool is not installed. Motion photo binding requires exiftool."
        )
        log.error("To fix this, install exiftool: 'brew install exiftool'")
        return

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
            with open(video_path, "rb") as f:
                video_bytes = f.read()

            # Build XMP payload
            xmp_payload = build_motion_xmp(len(video_bytes))

            # Write XMP payload to temp file
            os.makedirs("data/json", exist_ok=True)
            temp_xmp_path = "data/json/motion_photo_temp.xmp"
            with open(temp_xmp_path, "wb") as f:
                f.write(xmp_payload)

            # Call exiftool to inject XMP
            cmd = [
                "exiftool",
                "-overwrite_original",
                "-m",
                f"-xmp<={temp_xmp_path}",
                str(photo_path),
            ]
            res = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            if os.path.exists(temp_xmp_path):
                os.remove(temp_xmp_path)

            if res.returncode == 0:
                # Append video bytes to the end of the JPEG
                with open(photo_path, "ab") as f:
                    f.write(video_bytes)

                video_path.unlink()
                log.debug(f"    Removed standalone video: {video_path.name}")
                bound_count += 1
            else:
                log.error(
                    f"  Failed to run exiftool for {photo_path.name}: {res.stderr}"
                )
                failed_count += 1

        except Exception as e:
            log.error(f"  Failed to bind {photo_path.name}: {e}")
            failed_count += 1

    # Summary
    log.info("=== Bind Summary ===")
    log.info(f"  Bound:                {bound_count}")
    log.info(f"  Skipped (no video):   {skipped_no_video}")
    log.info(f"  Skipped (pre-bound):  {skipped_already_bound}")
    log.info(f"  Failed:               {failed_count}")
