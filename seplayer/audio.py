"""Wiedergabe-Engine auf Basis von pygame.mixer (MP3, FLAC, OGG, WAV, OPUS u. a.)."""
import contextlib
import io
import os
import sys
import tempfile
import time

# Im gepackten Build (PyInstaller setzt sys.frozen) oeffnet SePlayer kein pygame-Fenster
# (die GUI ist tkinter) - das SDL-Video-Subsystem wird nur fuer die Event-Queue (Track-Ende)
# gebraucht. Der Dummy-Video-Treiber macht pygame.display.init() zuverlaessig und verhindert
# "video system not initialized" in den gepackten .exe/.app (macOS + Windows).
if getattr(sys, "frozen", False):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

END_EVENT = pygame.USEREVENT + 1

_SILENT_WAV = None


def _silent_wav_bytes():
    """~50 ms stille WAV (8 kHz, 8-bit, mono) als Bytes — zum kurzzeitigen Freigeben von Datei-Handles."""
    global _SILENT_WAV
    if _SILENT_WAV is None:
        import wave
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(1)
            w.setframerate(8000)
            w.writeframes(b"\x80" * 160)
        _SILENT_WAV = buf.getvalue()
    return _SILENT_WAV


class PlaybackEngine:
    """Kapselt pygame.mixer.music: Play/Pause/Stop, Seek, Lautstärke, Position, Track-Ende.

    Die Position wird über eine eigene Uhr gerechnet, damit Pause/Seek auf allen
    Plattformen konsistent sind (mixer.music.get_pos() verhält sich je nach Backend
    beim Pausieren unterschiedlich).

    pygame.display.init() wird vor allem anderen aufgerufen: pygame.event und teils
    der Mixer werfen ohne initialisiertes SDL-Video-Subsystem "video system not
    initialized" (gesehen auf macOS und Windows). Schlägt die Audio-Initialisierung
    trotzdem fehl (z. B. kein Audio-Gerät), bleibt available=False und die App startet
    trotzdem — nur die Wiedergabe ist dann deaktiviert.
    """

    def __init__(self, volume=0.7):
        self.available = False
        self.current_path = None
        self.paused = False
        self._playing = False
        self._offset = 0.0
        self._clock = 0.0
        self._suppress_auto = False
        self._silent = None
        # Display zuerst: die Event-Queue (END_EVENT) braucht ein initialisiertes
        # Video-Subsystem. Schlaegt display.init() fehl, Fallback auf Dummy-Treiber.
        # Alle pygame-Fehler (auch Nicht-pygame.error wie NotImplementedError bei
        # fehlenden SDL-Libs im gepackten Build) duerfen den App-Start nicht killen.
        try:
            pygame.display.init()
        except Exception:
            try:
                os.environ["SDL_VIDEODRIVER"] = "dummy"
                pygame.display.init()
            except Exception:
                pass
        try:
            pygame.mixer.init()
        except Exception:
            try:
                pygame.display.init()
                pygame.mixer.init()
            except Exception:
                return
        try:
            pygame.mixer.music.set_endevent(END_EVENT)
            pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))
        except Exception:
            return
        self.available = True

    def load(self, path):
        """Datei laden (noch nicht abspielen). Wirft pygame.error bei nicht unterstütztem Format."""
        if not self.available:
            return
        pygame.mixer.music.load(path)
        self.current_path = path
        self._playing = False
        self.paused = False
        self._offset = 0.0

    def play(self, start=0.0):
        if not self.available:
            return
        pygame.mixer.music.play(start=start)
        self._offset = max(0.0, start)
        self._clock = time.monotonic()
        self._playing = True
        self.paused = False

    def pause(self):
        if self.available and self._playing and not self.paused:
            self._offset = self.position()
            pygame.mixer.music.pause()
            self.paused = True

    def resume(self):
        if self.available and self.paused:
            pygame.mixer.music.unpause()
            self._clock = time.monotonic()
            self.paused = False

    def stop(self):
        if self.available:
            pygame.mixer.music.stop()
        self._playing = False
        self.paused = False
        self._offset = 0.0

    def seek(self, seconds):
        """Ab Position `seconds` abspielen (Seek)."""
        if not self.available:
            return
        pygame.mixer.music.play(start=max(0.0, seconds))
        self._offset = max(0.0, seconds)
        self._clock = time.monotonic()
        self._playing = True
        self.paused = False

    def set_volume(self, value):
        if self.available:
            pygame.mixer.music.set_volume(max(0.0, min(1.0, value)))

    def position(self):
        """Aktuelle Wiedergabeposition in Sekunden."""
        if not self._playing or not self.available:
            return 0.0
        if self.paused:
            return self._offset
        return self._offset + (time.monotonic() - self._clock)

    def is_playing(self):
        return self.available and self._playing and not self.paused and pygame.mixer.music.get_busy()

    @contextlib.contextmanager
    def free_file(self, path):
        """Windows-Sperre umgehen (WinError 32 beim Umbenennen/Beschreiben der spielenden Datei).

        Wenn `path` gerade geladen ist: ~50 ms stille WAV abspielen (SDL gibt damit das
        Datei-Handle frei), dann `yield` (Datei darf jetzt umbenannt/beschrieben werden),
        danach `path` ab der letzten Position weiter abspielen. Sonst einfach durchreichen.
        """
        active = (self.available and self.current_path is not None
                  and os.path.abspath(path) == os.path.abspath(self.current_path))
        if not active:
            yield
            return
        pos = self.position()
        was_paused = self.paused
        was_playing = self._playing
        self._suppress_auto = True
        tmp = None
        try:
            pygame.mixer.music.stop()
            # stille WAV als echte Temp-Datei (fileobj bei music.load nicht überall zuverlässig)
            fd, tmp = tempfile.mkstemp(suffix=".wav")
            with os.fdopen(fd, "wb") as fh:
                fh.write(_silent_wav_bytes())
            pygame.mixer.music.load(tmp)
            pygame.mixer.music.play()
            try:
                pygame.event.get()
            except Exception:
                pass
            yield
        finally:
            self._suppress_auto = False
            pygame.mixer.music.load(path)
            self.current_path = path
            self._offset = 0.0
            self._playing = False
            self.paused = False
            if was_playing:
                self.play(start=pos)
                if was_paused:
                    self._offset = pos
                    pygame.mixer.music.pause()
                    self.paused = True
            try:
                pygame.event.get()  # altes END_EVENT der Stille-WAV verwerfen
            except Exception:
                pass
            if tmp:
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def finished(self):
        """True, wenn der geladene Track von selbst zu Ende gespielt wurde."""
        if getattr(self, "_suppress_auto", False):
            pygame.event.get()
            return False
        if not self.available or not self._playing or self.paused:
            return False
        try:
            for event in pygame.event.get():
                if event.type == END_EVENT:
                    return True
        except Exception:
            pass
        return not pygame.mixer.music.get_busy()
