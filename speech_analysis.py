"""
Voice Interview Analysis Module.

The candidate answers an interview question into the microphone. This module
1. turns the recording into text with a free, offline speech-to-text model
   (faster-whisper; the model is downloaded once and then runs on the server), and
2. measures how the answer was spoken:
   - pitch (how high the voice is and how much it moves up and down),
   - tone (expressiveness: pitch and loudness variation, steadiness of volume),
   - pronunciation clarity (how confidently each word was recognized),
   - pace (words per minute) and pauses,
   - fluency (filler words such as "um", "uh", "like", and repeated words),
   - English usage (vocabulary range, sentence length, common grammar slips).

All scores are rule-based estimates out of 100. They are meant as practice
feedback, not as a certified language test.
"""

import io
import re

import numpy as np

SAMPLE_RATE = 16000
MAX_SECONDS = 180
MIN_SECONDS = 10

# A prompt that tells the speech model to write down filler words instead of
# silently removing them, so they can be counted.
FILLER_PROMPT = "Umm, so, uh, let me think, like, hmm... Okay, I mean, you know, here's what I, uh, did."

FILLER_WORDS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "ahh", "hmm", "mm"}
FILLER_PHRASES = ["you know", "i mean", "kind of", "sort of", "like", "basically", "actually", "literally"]

INTERVIEW_QUESTIONS = [
    "Tell me about yourself.",
    "Why do you want this job?",
    "What are your strengths and weaknesses?",
    "Describe a project you worked on and your role in it.",
    "Tell me about a problem you solved and how you solved it.",
    "Where do you see yourself in five years?",
    "Why should we hire you?",
    "How do you handle pressure or tight deadlines?",
]

# Common spoken-grammar slips: (pattern, explanation).
GRAMMAR_RULES = [
    (r"\b(he|she|it) (don't|have|do|were)\b", "use 'doesn't / has / does / was' after he, she or it"),
    (r"\b(i|you|we|they) (was|has|does|doesn't)\b", "use 'were / have / do / don't' after I, you, we or they"),
    (r"\bi is\b", "say 'I am', not 'I is'"),
    (r"\bmore (better|worse|easier|faster|bigger)\b", "say 'better', not 'more better'"),
    (r"\bmost (best|worst|easiest)\b", "say 'the best', not 'most best'"),
    (r"\bdid(n't| not)? (went|came|did|saw|got|made|took)\b", "after 'did' use the base verb, e.g. 'did go'"),
    (r"\b(can|could|should|will|would|must) (went|did|was|goes|done)\b", "after can/should/will use the base verb"),
    (r"\bmyself (is|am)\b", "say 'My name is' or 'I am', not 'Myself is'"),
    (r"\bdiscuss about\b", "say 'discuss', not 'discuss about'"),
    (r"\bcope up\b", "say 'cope with', not 'cope up'"),
    (r"\bpass ?out (in|from)\b", "say 'graduated from', not 'passed out from'"),
    (r"\bdo the needful\b", "say what you will do instead of 'do the needful'"),
    (r"\bsince (\d+|two|three|four|five|six|seven|eight|nine|ten) (years|months|days)\b", "use 'for' with a length of time: 'for two years'"),
]

STOP_WORDS = set("""a an the and or but if so of to in on at for from by with as is am are was were be been being
it its this that these those i me my we our you your he she they them their his her him not no do does did have has
had will would can could should there here what which who when where how than then also just very really""".split())


# ------------------------------------------------------------------ audio

def load_audio(data):
    """Decode a recording (WAV, MP3, M4A, ...) to 16 kHz mono floats between -1 and 1."""
    import av
    chunks = []
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    with av.open(io.BytesIO(data), mode="r") as container:
        stream = container.streams.audio[0]
        for frame in container.decode(stream):
            frame.pts = None
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return (np.concatenate(chunks).astype(np.float32) / 32768.0)


def frame_signal(audio, frame, hop):
    if len(audio) < frame:
        return np.zeros((0, frame), dtype=np.float32)
    count = 1 + (len(audio) - frame) // hop
    index = np.arange(frame)[None, :] + hop * np.arange(count)[:, None]
    return audio[index]


def loudness(audio):
    """Loudness of every 30 ms frame in decibels, and which frames contain voice."""
    frames = frame_signal(audio, 480, 160)
    rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    if len(db) == 0:
        return db, np.zeros(0, dtype=bool)
    loud = np.percentile(db, 95)
    voiced = (db > loud - 30) & (db > -55)
    return db, voiced


def pitch_track(audio):
    """
    Pitch (fundamental frequency) of each 40 ms frame, found with autocorrelation.
    Returns the pitch in Hz of the frames that contain voice.
    """
    frame, hop = 640, 160
    frames = frame_signal(audio, frame, hop)
    if len(frames) == 0:
        return np.zeros(0)
    _db, voiced = loudness(audio)
    voiced = voiced[: len(frames)] if len(voiced) >= len(frames) else np.pad(voiced, (0, len(frames) - len(voiced)))
    frames = frames[voiced]
    if len(frames) == 0:
        return np.zeros(0)
    frames = frames - frames.mean(axis=1, keepdims=True)
    frames = frames * np.hanning(frame)
    spectrum = np.fft.rfft(frames, n=2 * frame, axis=1)
    ac = np.fft.irfft(np.abs(spectrum) ** 2, axis=1)[:, :frame]
    ac = ac / (ac[:, :1] + 1e-12)
    low, high = SAMPLE_RATE // 400, SAMPLE_RATE // 70            # 70 Hz to 400 Hz
    lags = np.argmax(ac[:, low:high], axis=1) + low
    strength = ac[np.arange(len(lags)), lags]
    pitches = SAMPLE_RATE / lags[strength > 0.45]
    return pitches.astype(float)


# ---------------------------------------------------------- speech to text

_model = None


def load_model(size="base.en"):
    """Load the free speech-to-text model (downloaded on first use, about 150 MB)."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(size, device="cpu", compute_type="int8")
    return _model


def transcribe(audio, model=None):
    """Return a list of recognized words: {"word", "start", "end", "probability"}."""
    model = model or load_model()
    segments, _info = model.transcribe(
        audio, language="en", word_timestamps=True, initial_prompt=FILLER_PROMPT,
        vad_filter=False, beam_size=5, condition_on_previous_text=False)
    words = []
    for segment in segments:
        for w in segment.words or []:
            text = w.word.strip()
            if text:
                words.append({"word": text, "start": float(w.start), "end": float(w.end), "probability": float(w.probability)})
    return words


# --------------------------------------------------------------- scoring

def clamp(value):
    return max(0.0, min(100.0, float(value)))


def band(score):
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "Fair"
    return "Needs practice"


def plain(word):
    return re.sub(r"[^a-z']", "", word.lower())


def count_fillers(text):
    lower = " " + re.sub(r"[^a-z' ]", " ", text.lower()) + " "
    found = {}
    for word in lower.split():
        if word in FILLER_WORDS:
            found[word] = found.get(word, 0) + 1
    for phrase in FILLER_PHRASES:
        n = len(re.findall(r"(?<= )" + re.escape(phrase) + r"(?= )", lower))
        if phrase == "like":
            # "I like ...", "would like", "looks like" are normal English, not fillers.
            n -= len(re.findall(r"(?<= )(i|we|you|they|would|really|also|don't|didn't|looks|look|feel|feels|something|just) like(?= )", lower))
        if n > 0:
            found[phrase] = found.get(phrase, 0) + n
    return found


def repeated_words(words):
    plain_words = [plain(w["word"]) for w in words]
    return sum(1 for a, b in zip(plain_words, plain_words[1:]) if a and a == b and a not in {"very", "bye", "no"})


def grammar_slips(text):
    lower = text.lower()
    found = []
    for pattern, advice in GRAMMAR_RULES:
        match = re.search(pattern, lower)
        if match:
            found.append((match.group(0), advice))
    return found


def analyze_speech(audio, words, spoken_skills=None):
    """Measure the recording and the recognized words. Returns a dictionary for the report."""
    duration = len(audio) / SAMPLE_RATE
    text = " ".join(w["word"] for w in words).strip()
    text = re.sub(r"\s+([,.?!])", r"\1", text)
    real_words = [w for w in words if plain(w["word"]) and plain(w["word"]) not in FILLER_WORDS]
    word_count = len(real_words)

    # Pace and pauses (from the time stamp of every word)
    if words:
        speaking_time = max(words[-1]["end"] - words[0]["start"], 1.0)
        gaps = [b["start"] - a["end"] for a, b in zip(words, words[1:])]
    else:
        speaking_time, gaps = max(duration, 1.0), []
    wpm = word_count / speaking_time * 60
    pauses = sum(1 for g in gaps if g >= 0.7)
    long_pauses = sum(1 for g in gaps if g >= 2.0)
    pace_score = clamp(100 - max(0, 115 - wpm) * 1.6 - max(0, wpm - 165) * 1.6)

    # Pronunciation clarity (how sure the speech model was about each word)
    probabilities = [w["probability"] for w in real_words]
    clear_share = (sum(1 for p in probabilities if p >= 0.7) / len(probabilities)) if probabilities else 0
    unclear = sorted({w["word"].strip(",.?!") for w in real_words if w["probability"] < 0.5 and len(plain(w["word"])) > 2})
    pronunciation_score = clamp(clear_share * 100 * 1.05)

    # Fluency (fillers, repeated words, long pauses)
    fillers = count_fillers(text)
    filler_total = sum(fillers.values())
    filler_rate = filler_total / max(word_count, 1) * 100          # fillers per 100 words
    repeats = repeated_words(words)
    fluency_score = clamp(100 - filler_rate * 6 - repeats * 4 - long_pauses * 6)

    # Pitch and tone
    pitches = pitch_track(audio)
    db, voiced = loudness(audio)
    if len(pitches) >= 20:
        median_pitch = float(np.median(pitches))
        semitones = 12 * np.log2(pitches / median_pitch)
        low, high = np.percentile(semitones, [10, 90])
        pitch_range = float(high - low)
    else:
        median_pitch, pitch_range = 0.0, 0.0
    voiced_db = db[voiced] if len(db) else np.zeros(0)
    loudness_spread = float(np.std(voiced_db)) if len(voiced_db) else 0.0
    average_db = float(np.mean(voiced_db)) if len(voiced_db) else -90.0
    # A lively voice moves about 4 to 12 semitones; below 3 sounds flat (monotone).
    pitch_score = clamp(100 - max(0, 4 - pitch_range) * 18 - max(0, pitch_range - 14) * 6) if median_pitch else 0
    volume_score = clamp(100 - max(0, -38 - average_db) * 3 - max(0, loudness_spread - 9) * 5)
    tone_score = clamp(0.6 * pitch_score + 0.4 * volume_score)

    # English usage
    content = [plain(w["word"]) for w in real_words if plain(w["word"]) and plain(w["word"]) not in STOP_WORDS]
    variety = len(set(content)) / len(content) if content else 0
    sentences = [s for s in re.split(r"[.?!]+", text) if len(s.split()) >= 2]
    sentence_length = word_count / max(len(sentences), 1)
    slips = grammar_slips(text)
    vocabulary_score = clamp(variety * 130)
    sentence_score = clamp(100 - abs(sentence_length - 15) * 3)
    english_score = clamp(0.6 * vocabulary_score + 0.4 * sentence_score - len(slips) * 8)
    if word_count < 15:
        english_score = min(english_score, 40)

    scores = {
        "Pronunciation clarity": pronunciation_score,
        "Fluency": fluency_score,
        "Pace": pace_score,
        "Tone and pitch": tone_score,
        "English usage": english_score,
    }
    weights = {"Pronunciation clarity": 0.25, "Fluency": 0.25, "Pace": 0.15, "Tone and pitch": 0.15, "English usage": 0.20}
    overall = round(sum(scores[k] * weights[k] for k in scores), 1)

    result = {
        "duration": duration, "transcript": text, "word_count": word_count, "wpm": wpm,
        "pauses": pauses, "long_pauses": long_pauses, "fillers": fillers, "filler_total": filler_total,
        "repeats": repeats, "unclear_words": unclear[:12], "median_pitch": median_pitch,
        "pitch_range": pitch_range, "average_db": average_db, "loudness_spread": loudness_spread,
        "variety": variety, "sentence_length": sentence_length, "grammar": slips,
        "skills": list(spoken_skills or []),
        "scores": {k: round(v, 1) for k, v in scores.items()}, "overall": overall, "band": band(overall),
    }
    result["suggestions"] = speech_suggestions(result)
    return result


def speech_suggestions(r):
    tips = []
    if r["word_count"] < 40:
        tips.append("Give a longer answer. Aim for 45 to 90 seconds with an example from your studies or work.")
    if r["wpm"] > 165:
        tips.append(f"You spoke fast ({r['wpm']:.0f} words per minute). Slow down to about 130 to 150 so every word is clear.")
    elif r["wpm"] < 115 and r["word_count"] >= 15:
        tips.append(f"You spoke slowly ({r['wpm']:.0f} words per minute). Prepare key points so the answer flows at about 130 to 150.")
    if r["filler_total"] >= 3:
        top = ", ".join(f"'{k}' ({v})" for k, v in sorted(r["fillers"].items(), key=lambda x: -x[1])[:3])
        tips.append(f"Reduce filler words: {top}. Pause silently instead of saying them.")
    if r["long_pauses"] >= 2:
        tips.append(f"There were {r['long_pauses']} long pauses (2 seconds or more). Practise the answer's outline: point, example, result.")
    if r["repeats"] >= 2:
        tips.append("Some words were repeated back to back. Finish the sentence you started instead of restarting it.")
    if r["unclear_words"]:
        tips.append("These words were hard to recognize; say them slowly and clearly: " + ", ".join(r["unclear_words"][:8]) + ".")
    if r["median_pitch"] and r["pitch_range"] < 3:
        tips.append("Your voice sounded flat (little change in pitch). Stress key words and let your voice rise and fall.")
    if r["average_db"] < -38:
        tips.append("Your voice was quiet. Speak a little louder or move closer to the microphone.")
    if r["loudness_spread"] > 10:
        tips.append("Your volume changed a lot. Keep a steady distance from the microphone.")
    if r["variety"] and r["variety"] < 0.45 and r["word_count"] >= 30:
        tips.append("Use a wider range of words; many words were repeated. Replace general words with specific ones.")
    for phrase, advice in r["grammar"][:4]:
        tips.append(f"Grammar: you said \"{phrase}\": {advice}.")
    if not tips:
        tips.append("Well spoken. Keep the same pace and clarity, and support each point with an example.")
    return tips
