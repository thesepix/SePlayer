"""Lesen/Schreiben von Audio-Tags: Metadaten, Sternebewertungen (mehrere Felder), Cover.

Bewertungsfelder (Rating), die gelesen UND geschrieben werden:
  MP3 (ID3):   POPM (= "POPULARIMETER", Traktor / MediaMonkey neu, Skala 0-255)
               TXXX "RATING MM" (MediaMonkey alt, Skala 0-100)
  FLAC/OGG:    RATING (MediaMonkey, 0-100), RATING WMP (Traktor), FMPS_RATING (0-5)
"""
import base64
import os

from mutagen import File as MutagenFile
from mutagen.id3 import (COMM, ID3, POPM, TALB, TCOM, TCON, TDRC, TIT2, TPE1,
                         TPE2, TPOS, TRCK, TXXX)

AUDIO_EXTENSIONS = {
    ".mp3", ".flac", ".ogg", ".oga", ".wav", ".opus",
    ".m4a", ".aac", ".wma", ".aif", ".aiff",
}

STAR_TO_POPM = {0: 0, 1: 51, 2: 102, 3: 153, 4: 204, 5: 255}

# Textfelder: interne Kennung -> (ID3-Frame-Keys, Vorbis-Comment-Key)
TEXT_FIELDS = {
    "title": (["TIT2"], "title"),
    "artist": (["TPE1"], "artist"),
    "album": (["TALB"], "album"),
    "albumartist": (["TPE2"], "albumartist"),
    "composer": (["TCOM"], "composer"),
    "genre": (["TCON"], "genre"),
    "year": (["TDRC", "TYER", "TORY"], "date"),
    "track": (["TRCK"], "tracknumber"),
    "disc": (["TPOS"], "discnumber"),
    "comment": (["COMM"], "comment"),
}

ID3_FRAME_CLASS = {
    "title": TIT2, "artist": TPE1, "album": TALB, "albumartist": TPE2,
    "composer": TCOM, "genre": TCON, "year": TDRC, "track": TRCK, "disc": TPOS,
}

VORBIS_RATING_FIELDS = ["RATING", "RATING WMP", "FMPS_RATING"]


def is_audio_file(path):
    return os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS


def _ceil_div(a, b):
    return -(-a // b)


def _normalize_stars(raw):
    """Rohwert eines Rating-Felds auf 0-5 Sterne normieren (Skalen 0-5, 0-100, 0-255)."""
    try:
        v = float(str(raw).split("/")[0])
    except (TypeError, ValueError):
        return 0
    if v <= 0:
        return 0
    if v > 100:
        return max(1, min(5, _ceil_div(int(v), 51)))
    if v > 5:
        return max(1, min(5, _ceil_div(int(v), 20)))
    return max(1, min(5, int(v)))


def _frame_text(frame):
    text = getattr(frame, "text", None)
    if text:
        return str(text[0]) if isinstance(text, (list, tuple)) else str(text)
    return ""


def _read_text(tags, field):
    id3_keys, vorbis_key = TEXT_FIELDS[field]
    if hasattr(tags, "getall"):
        for key in id3_keys:
            frames = tags.getall(key)
            if frames:
                return _frame_text(frames[0])
        return ""
    values = tags.get(vorbis_key)
    return str(values[0]) if values else ""


def read_rating_fields(path):
    """Alle erkannten Rating-Felder der Datei als {Anzeigename: Sterne 0-5}."""
    result = {}
    try:
        audio = MutagenFile(path)
    except Exception:
        return result
    if audio is None or audio.tags is None:
        return result
    tags = audio.tags
    if hasattr(tags, "getall"):
        for popm in tags.getall("POPM"):
            result["POPM (POPULARIMETER)"] = _normalize_stars(popm.rating)
            break
        for txxx in tags.getall("TXXX"):
            if txxx.desc.upper().replace("_", " ") == "RATING MM":
                result["RATING MM"] = _normalize_stars(txxx.text[0] if txxx.text else "")
    else:
        for key in VORBIS_RATING_FIELDS:
            values = tags.get(key)
            if values:
                result[key] = _normalize_stars(values[0])
    return result


def read_rating(path):
    """Bewertung 0-5: erstes gesetzte Feld gemäß Priorität (MP3: POPM, RATING MM; FLAC/OGG: RATING, RATING WMP, FMPS_RATING)."""
    fields = read_rating_fields(path)
    if path.lower().endswith(".mp3"):
        keys = ["POPM (POPULARIMETER)", "RATING MM"]
    else:
        keys = VORBIS_RATING_FIELDS
    for key in keys:
        if fields.get(key):
            return fields[key]
    return 0


def write_rating(path, stars):
    """Bewertung 0-5 in ALLE bekannten Rating-Felder des Formats schreiben. True bei Erfolg."""
    stars = max(0, min(5, int(stars)))
    try:
        if path.lower().endswith(".mp3"):
            try:
                tag = ID3(path)
            except Exception:
                tag = ID3()
            tag.delall("POPM")
            tag.delall("TXXX:RATING MM")
            if stars > 0:
                tag.add(POPM(email="", rating=STAR_TO_POPM[stars], playcount=0))
                tag.add(TXXX(encoding=3, desc="RATING MM", text=[str(stars * 20)]))
            tag.save(path)
            return True
        audio = MutagenFile(path)
        if audio is None or audio.tags is None:
            return False
        if hasattr(audio.tags, "getall"):
            return False
        for key in VORBIS_RATING_FIELDS:
            if key in audio.tags:
                del audio.tags[key]
        if stars > 0:
            audio.tags["RATING"] = str(stars * 20)
            audio.tags["RATING WMP"] = str(stars * 20)
            audio.tags["FMPS_RATING"] = str(stars)
        audio.save()
        return True
    except Exception:
        return False


def read_metadata(path):
    """Liest alle Tags einer Audiodatei (inkl. technischer Infos)."""
    meta = {key: "" for key in TEXT_FIELDS}
    meta.update({
        "duration": 0.0, "bitrate": 0, "sample_rate": 0, "channels": 0,
        "size": 0, "rating": 0,
        "filename": os.path.basename(path),
        "ext": os.path.splitext(path)[1].lstrip(".").lower(),
        "path": path,
    })
    meta["title"] = os.path.splitext(meta["filename"])[0]
    try:
        meta["size"] = os.path.getsize(path)
    except OSError:
        pass
    try:
        audio = MutagenFile(path)
    except Exception:
        audio = None
    if audio is not None:
        info = getattr(audio, "info", None)
        if info is not None:
            meta["duration"] = float(getattr(info, "length", 0.0) or 0.0)
            meta["bitrate"] = int(getattr(info, "bitrate", 0) or 0) // 1000
            meta["sample_rate"] = int(getattr(info, "sample_rate", 0) or 0)
            meta["channels"] = int(getattr(info, "channels", 0) or 0)
        tags = getattr(audio, "tags", None)
        if tags is not None:
            for field in TEXT_FIELDS:
                meta[field] = _read_text(tags, field)
            if not meta["title"]:
                meta["title"] = os.path.splitext(meta["filename"])[0]
            meta["year"] = meta["year"][:4]
            meta["track"] = meta["track"].split("/")[0]
            meta["disc"] = meta["disc"].split("/")[0]
    meta["rating"] = read_rating(path)
    return meta


def _write_id3(tag, fields):
    for key, frame_cls in ID3_FRAME_CLASS.items():
        if key in fields:
            tag.delall(frame_cls.__name__)
            if fields[key]:
                tag.add(frame_cls(encoding=3, text=[fields[key]]))
    if "comment" in fields:
        tag.delall("COMM")
        if fields["comment"]:
            tag.add(COMM(encoding=3, lang="eng", desc="", text=[fields["comment"]]))


def _write_vorbis(tags, fields):
    for key, (_id3_keys, vorbis_key) in TEXT_FIELDS.items():
        if key in fields:
            if fields[key]:
                tags[vorbis_key] = [fields[key]]
            elif vorbis_key in tags:
                del tags[vorbis_key]


def write_metadata(path, fields):
    """Text-Tags schreiben (leerer Wert löscht das Feld). True bei Erfolg."""
    try:
        audio = MutagenFile(path)
        if audio is None:
            return False
        if audio.tags is not None and hasattr(audio.tags, "getall"):
            _write_id3(audio.tags, fields)
            audio.save()
            return True
        if path.lower().endswith(".mp3"):
            tag = ID3()
            _write_id3(tag, fields)
            audio.add_tags(tag)
            audio.save()
            return True
        if audio.tags is None:
            return False
        _write_vorbis(audio.tags, fields)
        audio.save()
        return True
    except Exception:
        return False


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
