"""Lesen und Schreiben von Audio-Tags: Metadaten, Sternebewertungen (POPM/RATING) und Cover."""
import base64
import os

from mutagen import File as MutagenFile
from mutagen.id3 import ID3, POPM

AUDIO_EXTENSIONS = {
    ".mp3", ".flac", ".ogg", ".oga", ".wav", ".opus",
    ".m4a", ".aac", ".wma", ".aif", ".aiff",
}

# Sterne -> POPM-Rating-Byte (5 Sterne = 255)
STAR_TO_POPM = {0: 0, 1: 51, 2: 102, 3: 153, 4: 204, 5: 255}


def is_audio_file(path):
    return os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS


def _ceil_div(a, b):
    return -(-a // b)


def _popm_to_stars(value):
    if not value:
        return 0
    return max(1, min(5, _ceil_div(value, 51)))


def read_rating(path):
    """Sternebewertung (0-5) auslesen: POPM-Frame bei MP3, RATING/FMPS_RATING bei FLAC/OGG."""
    try:
        audio = MutagenFile(path)
    except Exception:
        return 0
    if audio is None or audio.tags is None:
        return 0
    tags = audio.tags
    if hasattr(tags, "getall"):
        popms = tags.getall("POPM")
        if popms:
            return _popm_to_stars(popms[0].rating)
        return 0
    for key, scale in (("FMPS_RATING", 1), ("RATING", 20)):
        values = tags.get(key)
        if values:
            try:
                raw = float(str(values[0]).split("/")[0])
            except ValueError:
                continue
            if raw <= 0:
                return 0
            return max(1, min(5, _ceil_div(int(raw), scale)))
    return 0


def write_rating(path, stars):
    """Sternebewertung (0-5) in die Datei schreiben (POPM bei MP3, RATING bei FLAC/OGG).

    Rückgabe: True bei Erfolg, sonst False.
    """
    stars = max(0, min(5, int(stars)))
    try:
        if path.lower().endswith(".mp3"):
            try:
                tag = ID3(path)
            except Exception:
                tag = ID3()
            tag.delall("POPM")
            if stars > 0:
                tag.add(POPM(email="", rating=STAR_TO_POPM[stars], playcount=0))
            tag.save(path)
            return True
        audio = MutagenFile(path)
        if audio is None or audio.tags is None:
            return False
        if hasattr(audio.tags, "getall"):
            return False
        if stars == 0:
            for key in ("RATING", "FMPS_RATING"):
                if key in audio.tags:
                    del audio.tags[key]
        else:
            audio.tags["RATING"] = str(stars * 20)
            audio.tags["FMPS_RATING"] = str(stars)
        audio.save()
        return True
    except Exception:
        return False


def read_metadata(path):
    """Liest die wichtigsten Tags einer Audiodatei.

    Rückgabe: dict mit title, artist, album, track, year, duration, bitrate, rating.
    """
    meta = {
        "title": os.path.splitext(os.path.basename(path))[0],
        "artist": "",
        "album": "",
        "track": "",
        "year": "",
        "duration": 0.0,
        "bitrate": 0,
        "rating": 0,
    }
    try:
        audio = MutagenFile(path, easy=True)
    except Exception:
        audio = None
    if audio is not None:
        info = getattr(audio, "info", None)
        if info is not None:
            meta["duration"] = float(getattr(info, "length", 0.0) or 0.0)
            meta["bitrate"] = int(getattr(info, "bitrate", 0) or 0) // 1000
        audio_tags = getattr(audio, "tags", None)
        if audio_tags is not None:
            def first(key):
                values = audio_tags.get(key)
                return str(values[0]) if values else ""
            meta["title"] = first("title") or meta["title"]
            meta["artist"] = first("artist")
            meta["album"] = first("album")
            meta["track"] = first("tracknumber").split("/")[0]
            meta["year"] = first("date")[:4]
    meta["rating"] = read_rating(path)
    return meta


def read_cover(path):
    """Cover-Bilddaten (bytes) aus den Tags lesen, oder None wenn keines vorhanden."""
    try:
        audio = MutagenFile(path)
    except Exception:
        return None
    if audio is None or audio.tags is None:
        return None
    tags = audio.tags
    if hasattr(tags, "getall"):
        apic = tags.getall("APIC")
        if apic:
            return apic[0].data
        return None
    pictures = getattr(audio, "pictures", None)
    if pictures:
        return pictures[0].data
    block = tags.get("METADATA_BLOCK_PICTURE")
    if block:
        try:
            return base64.b64decode(block[0])
        except Exception:
            return None
    return None
