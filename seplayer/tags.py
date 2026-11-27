"""Lesen/Schreiben von Audio-Tags: Metadaten, Sternebewertungen (mehrere Felder), Cover.

Bewertungsfelder (Rating), die gelesen UND geschrieben werden:
  MP3 (ID3):   POPM (= "POPULARIMETER", Traktor / MediaMonkey neu, Skala 0-255)
               TXXX "RATING MM" (MediaMonkey alt, Skala 0-100)
  FLAC/OGG:    RATING (MediaMonkey, 0-100), RATING WMP (Traktor), FMPS_RATING (0-5)

Robustheit: letzter Fehler landet in `last_error`; Windows-Pfade > 259 Zeichen bekommen
automatisch den \\\\?\\-Präfix; read-only-Dateien werden einmalig schreibbar gemacht.
"""
import base64
import os
import stat
import time

from mutagen import File as MutagenFile
from mutagen.id3 import (APIC, COMM, ID3, POPM, TALB, TCOM, TCON, TDRC, TIT2,
                         TPE1, TPE2, TPOS, TRCK, TXXX)

AUDIO_EXTENSIONS = {
    ".mp3", ".flac", ".ogg", ".oga", ".wav", ".opus",
    ".m4a", ".aac", ".wma", ".aif", ".aiff",
}

STAR_TO_POPM = {0: 0, 1: 51, 2: 102, 3: 153, 4: 204, 5: 255}

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

last_error = None


def _err(exc):
    global last_error
    last_error = f"{type(exc).__name__}: {exc}"
    return False


def _open_path(path):
    """Windows: Pfade > 259 Zeichen brauchen den \\\\?\\-Präfix."""
    if os.name == "nt" and len(path) > 259:
        return "\\\\?\\" + os.path.abspath(path)
    return path


def _ensure_tags(audio):
    """Stellt sicher, dass audio.tags existiert (FLAC ohne VORBIS_COMMENT usw.)."""
    if audio.tags is None:
        if not hasattr(audio, "add_tags"):
            raise RuntimeError("Datei hat keine Tag-Struktur")
        audio.add_tags()
    return audio.tags


def _save_audio(audio, path):
    """audio.save() mit Retry bei Windows-Sperre (WinError 32) und read-only-Attribut."""
    last_exc = None
    for attempt in range(3):
        try:
            audio.save()
            return True
        except PermissionError as exc:
            last_exc = exc
            try:
                os.chmod(path, stat.S_IWRITE)
            except OSError:
                pass
            time.sleep(0.3)
        except Exception as exc:
            return _err(exc)
    return _err(last_exc)


def _save_tag(tag, path):
    """ID3-Tag speichern, mit Retry bei Sperre."""
    last_exc = None
    for attempt in range(3):
        try:
            return _save_tag(tag, path)
        except PermissionError as exc:
            last_exc = exc
            try:
                os.chmod(path, stat.S_IWRITE)
            except OSError:
                pass
            time.sleep(0.3)
        except Exception as exc:
            return _err(exc)
    return _err(last_exc)


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
        audio = MutagenFile(_open_path(path))
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
    """Bewertung 0-5: erstes gesetzte Feld gemäß Priorität (ID3: POPM, RATING MM; Vorbis: RATING, RATING WMP, FMPS_RATING)."""
    fields = read_rating_fields(path)
    for key in ("POPM (POPULARIMETER)", "RATING MM") + tuple(VORBIS_RATING_FIELDS):
        if fields.get(key):
            return fields[key]
    return 0


def write_rating(path, stars):
    """Bewertung 0-5 in ALLE bekannten Rating-Felder des Formats schreiben. True bei Erfolg.

    MP3: ID3 (POPM + TXXX RATING MM) — direkt via ID3, damit auch tag-lose MP3s gehen.
    WAV/AIFF (ID3-in-RIFF, z. B. von MediaMonkey beschrieben): ebenfalls POPM + RATING MM.
    FLAC/OGG: Vorbis-Comments RATING, RATING WMP, FMPS_RATING.
    """
    global last_error
    last_error = None
    stars = max(0, min(5, int(stars)))
    try:
        if path.lower().endswith(".mp3"):
            try:
                tag = ID3(_open_path(path))
            except Exception:
                tag = ID3()
            try:
                tag.delall("POPM")
            except KeyError:
                pass
            try:
                tag.delall("TXXX:RATING MM")
            except KeyError:
                pass
            if stars > 0:
                tag.add(POPM(email="", rating=STAR_TO_POPM[stars], playcount=0))
                tag.add(TXXX(encoding=3, desc="RATING MM", text=[str(stars * 20)]))
            tag.save(_open_path(path))
            return True
        audio = MutagenFile(_open_path(path))
        if audio is None:
            return _err(RuntimeError("Datei nicht lesbar"))
        tags = _ensure_tags(audio)
        if hasattr(tags, "getall"):
            # WAV/AIFF mit ID3
            try:
                tags.delall("POPM")
            except KeyError:
                pass
            try:
                tags.delall("TXXX:RATING MM")
            except KeyError:
                pass
            if stars > 0:
                tags.add(POPM(email="", rating=STAR_TO_POPM[stars], playcount=0))
                tags.add(TXXX(encoding=3, desc="RATING MM", text=[str(stars * 20)]))
            return _save_audio(audio, path)
        for key in VORBIS_RATING_FIELDS:
            if key in tags:
                del tags[key]
        if stars > 0:
            tags["RATING"] = str(stars * 20)
            tags["RATING WMP"] = str(stars * 20)
            tags["FMPS_RATING"] = str(stars)
        return _save_audio(audio, path)
    except Exception as exc:
        return _err(exc)


RIFF_INFO_MAP = {
    "INAM": "title", "IART": "artist", "IPRD": "album", "IGNR": "genre",
    "ICRD": "year", "ICMT": "comment", "ITRK": "track", "IPRT": "disc",
    "ICOP": None, "ISFT": None,
}


def _read_riff_info(path):
    """RIFF-INFO-Tags aus einer WAV-Datei lesen (INAM=Titel, IART=Interpret …)."""
    info = {}
    try:
        with open(_open_path(path), "rb") as fh:
            head = fh.read(12)
            if len(head) < 12 or head[:4] != b"RIFF" or head[8:12] != b"WAVE":
                return info
            while True:
                header = fh.read(8)
                if len(header) < 8:
                    break
                cid = header[:4]
                size = int.from_bytes(header[4:8], "little")
                if cid == b"LIST":
                    form = fh.read(4)
                    end = fh.tell() + size - 4
                    if form == b"INFO":
                        while fh.tell() + 8 <= end:
                            sub = fh.read(8)
                            if len(sub) < 8:
                                break
                            sid = sub[:4]
                            ssize = int.from_bytes(sub[4:8], "little")
                            data = fh.read(ssize + (ssize & 1))
                            try:
                                info[sid.decode("ascii", "ignore")] = data.rstrip(b"\x00").decode("utf-8", "ignore")
                            except Exception:
                                pass
                    else:
                        fh.seek(end)
                else:
                    fh.seek(size + (size & 1), 1)
    except OSError:
        pass
    return info


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
    meta["title"] = ""  # Fallback auf Dateinamen erst ganz am Ende
    try:
        meta["size"] = os.path.getsize(path)
    except OSError:
        pass
    try:
        audio = MutagenFile(_open_path(path))
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
            meta["year"] = meta["year"][:4]
            meta["track"] = meta["track"].split("/")[0]
            meta["disc"] = meta["disc"].split("/")[0]
        if meta["ext"] == "wav":
            # WAV ohne (vollständige) ID3-Tags: RIFF-INFO als Fallback
            info = _read_riff_info(path)
            for riff_key, field in RIFF_INFO_MAP.items():
                if field and riff_key in info and not meta[field]:
                    meta[field] = info[riff_key]
            if not meta["title"]:
                meta["title"] = os.path.splitext(meta["filename"])[0]
            meta["year"] = meta["year"][:4]
            meta["track"] = meta["track"].split("/")[0]
            meta["disc"] = meta["disc"].split("/")[0]
    if not meta["title"]:
        meta["title"] = os.path.splitext(meta["filename"])[0]
    meta["rating"] = read_rating(path)
    return meta


def _write_id3(tag, fields):
    for key, frame_cls in ID3_FRAME_CLASS.items():
        if key in fields:
            try:
                tag.delall(frame_cls.__name__)
            except KeyError:
                pass
            if fields[key]:
                tag.add(frame_cls(encoding=3, text=[fields[key]]))
    if "comment" in fields:
        try:
            tag.delall("COMM")
        except KeyError:
            pass
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
    global last_error
    last_error = None
    try:
        audio = MutagenFile(_open_path(path))
        if audio is None:
            return _err(RuntimeError("Datei nicht lesbar"))
        if audio.tags is not None and hasattr(audio.tags, "getall"):
            _write_id3(audio.tags, fields)
            return _save_audio(audio, path)
        if path.lower().endswith(".mp3"):
            tag = ID3()
            _write_id3(tag, fields)
            audio.add_tags(tag)
            return _save_audio(audio, path)
        tags = _ensure_tags(audio)
        if hasattr(tags, "getall"):
            _write_id3(tags, fields)
            return _save_audio(audio, path)
        _write_vorbis(tags, fields)
        return _save_audio(audio, path)
    except Exception as exc:
        return _err(exc)


def read_cover(path):
    """Cover-Bilddaten (bytes) aus den Tags lesen, oder None wenn keines vorhanden."""
    try:
        audio = MutagenFile(_open_path(path))
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


def write_cover(path, image_bytes, mime="image/png"):
    """Cover setzen (image_bytes=None entfernt das Cover). True bei Erfolg."""
    global last_error
    last_error = None
    try:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".mp3" or ext == ".wav":
            try:
                tag = ID3(_open_path(path))
            except Exception:
                tag = ID3()
            try:
                tag.delall("APIC")
            except KeyError:
                pass
            if image_bytes:
                tag.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=image_bytes))
            tag.save(_open_path(path))
            return True
        audio = MutagenFile(_open_path(path))
        if audio is None:
            return _err(RuntimeError("Datei nicht lesbar"))
        if ext in (".ogg", ".oga"):
            tags = _ensure_tags(audio)
            if image_bytes:
                tags["METADATA_BLOCK_PICTURE"] = [base64.b64encode(image_bytes).decode("ascii")]
            elif "METADATA_BLOCK_PICTURE" in tags:
                del tags["METADATA_BLOCK_PICTURE"]
            return _save_audio(audio, path)
        _ensure_tags(audio)
        if image_bytes:
            from mutagen.flac import Picture
            pic = Picture()
            pic.type = 3
            pic.mime = mime
            pic.desc = "Cover"
            pic.data = image_bytes
            audio.clear_pictures()
            audio.add_picture(pic)
        else:
            audio.clear_pictures()
        return _save_audio(audio, path)
    except Exception as exc:
        return _err(exc)


def remove_cover(path):
    return write_cover(path, None)
