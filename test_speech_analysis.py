"""Tests for the Voice Interview Analysis Module. Run: python -m unittest discover tests -v"""

import os
import sys
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import speech_analysis as sa  # noqa: E402

AUDIO = os.path.join(ROOT, "tests", "audio")


def read(name):
    with open(os.path.join(AUDIO, name), "rb") as f:
        return sa.load_audio(f.read())


def fake_words(text, seconds_per_word=0.4, gap=0.05, probability=0.95, start=0.3):
    """Stand-in for the speech model: evenly timed words."""
    words, t = [], start
    for word in text.split():
        words.append({"word": word, "start": t, "end": t + seconds_per_word, "probability": probability})
        t += seconds_per_word + gap
    return words


GOOD = ("Hello, my name is Asha. I recently completed my degree in computer science. "
        "During my final year I built a resume analyzer in Python with Flask and SQL. "
        "I enjoy solving problems and learning new tools quickly, and I explain my work clearly to my team.")


class SpeechTests(unittest.TestCase):
    def test_pitch_of_a_pure_tone(self):
        pitches = sa.pitch_track(read("tone_200hz.wav"))
        self.assertGreater(len(pitches), 100)
        self.assertAlmostEqual(float(np.median(pitches)), 200, delta=4)

    def test_pitch_of_speech_is_in_voice_range(self):
        pitches = sa.pitch_track(read("clear_answer.wav"))
        self.assertGreater(len(pitches), 50)
        self.assertTrue(70 < np.median(pitches) < 400)

    def test_silence_gives_no_pitch(self):
        self.assertEqual(len(sa.pitch_track(np.zeros(sa.SAMPLE_RATE * 3, dtype=np.float32))), 0)

    def test_good_answer_scores_well(self):
        audio = read("clear_answer.wav")
        r = sa.analyze_speech(audio, fake_words(GOOD), ["Python", "Flask", "SQL"])
        self.assertEqual(r["filler_total"], 0)
        self.assertEqual(r["grammar"], [])
        self.assertTrue(120 < r["wpm"] < 160, r["wpm"])
        self.assertGreaterEqual(r["scores"]["Fluency"], 95)
        self.assertGreaterEqual(r["scores"]["Pronunciation clarity"], 95)
        self.assertGreater(r["overall"], 70)
        self.assertEqual(r["skills"], ["Python", "Flask", "SQL"])

    def test_fillers_lower_fluency(self):
        text = "Um so I uh like worked on, you know, a project um and uh I I basically made it work um."
        r = sa.analyze_speech(read("clear_answer.wav"), fake_words(text))
        self.assertGreaterEqual(r["filler_total"], 8)
        self.assertEqual(r["repeats"], 1)
        self.assertLess(r["scores"]["Fluency"], 50)
        self.assertTrue(any("filler" in tip for tip in r["suggestions"]))

    def test_like_as_a_verb_is_not_a_filler(self):
        self.assertEqual(sa.count_fillers("I like Python and I would like to learn more"), {})
        self.assertEqual(sa.count_fillers("it was like really hard"), {"like": 1})

    def test_unclear_words_lower_pronunciation(self):
        words = fake_words(GOOD, probability=0.95)
        for w in words[::2]:
            w["probability"] = 0.3
        r = sa.analyze_speech(read("clear_answer.wav"), words)
        self.assertLess(r["scores"]["Pronunciation clarity"], 60)
        self.assertTrue(r["unclear_words"])

    def test_fast_and_slow_pace(self):
        audio = read("clear_answer.wav")
        fast = sa.analyze_speech(audio, fake_words(GOOD, seconds_per_word=0.2, gap=0.02))
        slow = sa.analyze_speech(audio, fake_words(GOOD, seconds_per_word=0.6, gap=0.3))
        self.assertGreater(fast["wpm"], 200)
        self.assertLess(slow["wpm"], 80)
        self.assertLess(fast["scores"]["Pace"], 60)
        self.assertLess(slow["scores"]["Pace"], 60)

    def test_long_pauses_are_counted(self):
        words = fake_words(GOOD)
        for w in words[10:]:
            w["start"] += 3
            w["end"] += 3
        r = sa.analyze_speech(read("clear_answer.wav"), words)
        self.assertEqual(r["long_pauses"], 1)

    def test_grammar_slips(self):
        found = [p for p, _ in sa.grammar_slips("Myself is Ravi. He don't like it. I has done it. We discuss about it. It is more better.")]
        self.assertEqual(len(found), 5)
        self.assertEqual(sa.grammar_slips("He doesn't like it. I have done it."), [])

    def test_monotone_voice_gets_advice(self):
        r = sa.analyze_speech(read("tone_200hz.wav"), fake_words(GOOD))
        self.assertLess(r["pitch_range"], 1)
        self.assertTrue(any("flat" in tip for tip in r["suggestions"]))

    def test_band_names(self):
        self.assertEqual([sa.band(x) for x in (90, 75, 55, 20)], ["Excellent", "Good", "Fair", "Needs practice"])


if __name__ == "__main__":
    unittest.main()
