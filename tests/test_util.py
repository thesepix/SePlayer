import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seplayer.util import apply_filename_pattern, title_from_filename


class TestTitleFromFilename(unittest.TestCase):
    CASES = {
        "02 - krugah - upful light.mp3": "upful light",
        "07 - upful light.flac": "upful light",
        "1. Intro.mp3": "Intro",
        "Mein Song.mp3": "Mein Song",
        "99 Luftballons.mp3": "99 Luftballons",
        "03 - Artist - My - Song.wav": "My - Song",
    }

    def test_cases(self):
        for fn, want in self.CASES.items():
            self.assertEqual(title_from_filename(fn), want, fn)


class TestApplyFilenamePattern(unittest.TestCase):
    def test_pattern(self):
        meta = {"track": "2", "artist": "krugah", "title": "upful light"}
        self.assertEqual(apply_filename_pattern("## - artist - title", meta), "02 - krugah - upful light")

    def test_sanitize(self):
        meta = {"track": "1", "artist": 'a/b', "title": "t"}
        out = apply_filename_pattern("## - artist - title", meta)
        self.assertNotIn("/", out)


if __name__ == "__main__":
    unittest.main()
