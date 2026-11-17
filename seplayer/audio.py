"""Wiedergabe-Engine auf Basis von pygame.mixer (MP3, FLAC, OGG, WAV, OPUS u. a.)."""
import time

import pygame

END_EVENT = pygame.USEREVENT + 1


class PlaybackEngine:
    """Kapselt pygame.mixer.music: Play/Pause/Stop, Seek, Lautstärke, Position, Track-Ende.

    Die Position wird über eine eigene Uhr gerechnet, damit Pause/Seek auf allen
    Plattformen konsistent sind (mixer.music.get_pos() verhält sich je nach Backend
    beim Pausieren unterschiedlich).
    """

    def __init__(self, volume=0.7):
        pygame.mixer.init()
        pygame.mixer.music.set_endevent(END_EVENT)
        self.current_path = None
        self.paused = False
        self._playing = False
        self._offset = 0.0
        self._clock = 0.0
        pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))

    def load(self, path):
        """Datei laden (noch nicht abspielen). Wirft pygame.error bei nicht unterstütztem Format."""
        pygame.mixer.music.load(path)
        self.current_path = path
        self._playing = False
        self.paused = False
        self._offset = 0.0

    def play(self, start=0.0):
        pygame.mixer.music.play(start=start)
        self._offset = max(0.0, start)
        self._clock = time.monotonic()
        self._playing = True
        self.paused = False

    def pause(self):
        if self._playing and not self.paused:
            self._offset = self.position()
            pygame.mixer.music.pause()
            self.paused = True

    def resume(self):
        if self.paused:
            pygame.mixer.music.unpause()
            self._clock = time.monotonic()
            self.paused = False

    def stop(self):
        pygame.mixer.music.stop()
        self._playing = False
        self.paused = False
        self._offset = 0.0

    def seek(self, seconds):
        """Ab Position `seconds` abspielen (Seek)."""
        pygame.mixer.music.play(start=max(0.0, seconds))
        self._offset = max(0.0, seconds)
        self._clock = time.monotonic()
        self._playing = True
        self.paused = False

    def set_volume(self, value):
        pygame.mixer.music.set_volume(max(0.0, min(1.0, value)))

    def position(self):
        """Aktuelle Wiedergabeposition in Sekunden."""
        if not self._playing:
            return 0.0
        if self.paused:
            return self._offset
        return self._offset + (time.monotonic() - self._clock)

    def is_playing(self):
        return self._playing and not self.paused and pygame.mixer.music.get_busy()

    def finished(self):
        """True, wenn der geladene Track von selbst zu Ende gespielt wurde."""
        ended = False
        for event in pygame.event.get():
            if event.type == END_EVENT:
                ended = True
        return ended or (self._playing and not self.paused and not pygame.mixer.music.get_busy())
