import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seplayer import tags as taglib


def make_wav(path):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(8000)
        w.writeframes(b"\x80" * 800)


class TestWavTags(unittest.TestCase):
    def test_title_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "01 - test.wav")
            make_wav(p)
            self.assertTrue(taglib.write_metadata(p, {"title": "Mein Titel", "artist": "Künstler"}))
            meta = taglib.read_metadata(p)
            self.assertEqual(meta["title"], "Mein Titel")
            self.assertEqual(meta["artist"], "Künstler")

    def test_rating_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "02 - bewertung.wav")
            make_wav(p)
            self.assertTrue(taglib.write_rating(p, 4))
            self.assertEqual(taglib.read_rating(p), 4)
            self.assertTrue(taglib.write_rating(p, 0))
            self.assertEqual(taglib.read_rating(p), 0)


if __name__ == "__main__":
    unittest.main()
