"""
English Level Module.

Estimates the candidate's spoken English level on the CEFR scale
(Common European Framework of Reference for Languages):

    A1  A2  A2+  B1  B1+  B2  B2+  C1  C2

The "plus" levels are part of the CEFR descriptors (Council of Europe). The goal
set for candidates is at least B2 (independent user) or B2+.

Two ways of estimating:
- With the AI service, the AI examiner judges the transcripts together with the
  measured speech figures (see interviewer.assess_english).
- Without it, this module combines measurable signals: vocabulary range,
  sentence complexity, linking words, grammar slips, fluency (pace, fillers,
  pauses) and pronunciation clarity. The rule-based estimate never goes above C1,
  because rules cannot reliably recognise C2.

This is a practice estimate, not an official certificate.
"""

import math
import re

LEVELS = ["A1", "A2", "A2+", "B1", "B1+", "B2", "B2+", "C1", "C2"]
TARGET = "B2"

NAMES = {
    "A1": "Beginner", "A2": "Elementary", "A2+": "Strong elementary", "B1": "Intermediate",
    "B1+": "Strong intermediate", "B2": "Upper intermediate", "B2+": "Strong upper intermediate",
    "C1": "Advanced", "C2": "Proficient",
}

DESCRIPTIONS = {
    "A1": "Uses single words and very short memorised phrases; long pauses; hard to follow without help.",
    "A2": "Uses short, simple sentences about familiar things; basic grammar mistakes are frequent.",
    "A2+": "Can describe simple experiences in short sentences, but rarely links ideas or gives reasons.",
    "B1": "Can talk about experience and plans and give simple reasons, with noticeable pauses and errors.",
    "B1+": "Talks with some ease on familiar topics; begins to explain and compare, but vocabulary and accuracy limit precision.",
    "B2": "Speaks with fluency and spontaneity; gives clear, detailed answers with reasons and examples; errors rarely cause misunderstanding.",
    "B2+": "Argues a point well, links ideas smoothly and uses a good range of vocabulary with few errors.",
    "C1": "Expresses ideas fluently and precisely, with complex sentences and natural, flexible language.",
    "C2": "Speaks effortlessly with precision and nuance, close to an educated native speaker.",
}

LINKERS = ["because", "although", "however", "therefore", "which", "while", "whereas", "unless", "despite",
           "moreover", "furthermore", "in addition", "as a result", "for example", "for instance", "on the other hand",
           "even though", "so that", "in order to", "instead", "whether", "since", "if", "when", "after", "before",
           "first", "finally", "overall"]

# Step-by-step tips for moving from each level to the next, up to the B2/B2+ goal.
LEVEL_TIPS = {
    "A1": [
        "Learn the 500 most common English words, 10 a day, and say each one in a short sentence.",
        "Practise answering 'Tell me about yourself' in 5 simple sentences until you can say it without notes.",
        "Use the present simple correctly: I work, he works, I don't, he doesn't.",
        "Listen to slow English (for example 'VOA Learning English') for 15 minutes a day and repeat sentences aloud.",
    ],
    "A2": [
        "Join two ideas with 'and', 'but', 'because' and 'so' instead of speaking in single short sentences.",
        "Practise the past simple for your experience: I studied, I built, I worked, I learned.",
        "Prepare short answers (4 to 6 sentences) for the 10 most common interview questions and record yourself.",
        "Learn 15 words used in your field and practise one sentence for each.",
    ],
    "A2+": [
        "Always add a reason and an example: 'I enjoy coding because… For example, …'.",
        "Practise past simple and present perfect: 'I worked on…' and 'I have worked with…'.",
        "Speak for one full minute on a familiar topic every day without stopping; record it and listen back.",
        "Replace 'very good' and 'nice' with precise words such as 'efficient', 'reliable', 'challenging'.",
    ],
    "B1": [
        "Structure every answer: point, example (situation, action, result), what you learned (the STAR method).",
        "Use linking words that show logic: however, although, as a result, therefore, for instance.",
        "Cut filler words: when you need time to think, pause silently for one second instead of saying 'um'.",
        "Watch 10-minute interview or business videos with English subtitles, then retell them in your own words.",
    ],
    "B1+": [
        "Explain the 'why' and 'how' in detail: give two reasons and one measurable result in each answer.",
        "Use more complex sentences: relative clauses (which, who), conditionals (if I had…, I would…), passive (it was tested).",
        "Learn collocations used in interviews: meet a deadline, take responsibility, solve a problem, work under pressure.",
        "Have a 15-minute English conversation three times a week (a friend, a club or an online exchange) and note your mistakes.",
    ],
    "B2": [
        "Show a range of opinion and comparison: 'On the one hand…, on the other hand…', 'compared with…'.",
        "Paraphrase instead of repeating the same word; keep a list of synonyms for words you overuse.",
        "Correct your recurring grammar errors: write down each mistake from your recordings and practise the correct form.",
        "Practise answering unexpected questions for 2 minutes with no preparation to build spontaneity.",
    ],
    "B2+": [
        "Use precise, less common vocabulary and idiomatic phrases naturally (e.g. 'streamline', 'trade-off', 'take ownership').",
        "Vary sentence structure: start some sentences with 'Having…', 'What I found was…', 'Not only…, but also…'.",
        "Work on intonation: stress key words and use falling tone at the end of statements to sound confident.",
        "Read one quality English article a day (for example a business or technology news site) and summarise it aloud.",
    ],
    "C1": [
        "Refine nuance: hedge and qualify ideas ('to some extent', 'arguably', 'it largely depends on').",
        "Practise presenting and defending a complex idea for 5 minutes, then answer challenging follow-up questions.",
        "Listen to native-speed podcasts and shadow (repeat at the same time) to polish rhythm and connected speech.",
    ],
    "C2": [
        "Keep the level by using English daily in demanding situations: presentations, negotiations and writing.",
    ],
}


def level_index(level):
    return LEVELS.index(level) if level in LEVELS else -1


def normalise(level):
    level = (level or "").strip().upper().replace(" PLUS", "+").replace("PLUS", "+")
    return level if level in LEVELS else None


def name(level):
    return NAMES.get(level, "")


def gap_to_target(level):
    """How far the level is from B2."""
    i, target = level_index(level), level_index(TARGET)
    if i < 0:
        return ""
    if i >= level_index("B2+"):
        return f"You are at or above the B2+ goal. Aim for {LEVELS[min(i + 1, len(LEVELS) - 1)]} next."
    if i == target:
        return "You have reached the B2 goal. Next step: B2+."
    steps = target - i
    return f"You are {steps} step{'s' if steps > 1 else ''} below the B2 goal ({' → '.join(LEVELS[i:target + 1])})."


def plan_tips(level):
    """Tips for the next steps from the current level up to B2+ (or the next level if already there)."""
    i = level_index(level)
    if i < 0:
        return []
    stop = max(level_index("B2+"), i)
    tips = []
    for step in LEVELS[i:stop + 1]:
        tips.extend(LEVEL_TIPS.get(step, [])[:2] if step != level else LEVEL_TIPS.get(step, []))
        if len(tips) >= 7:
            break
    return tips[:7]


# ------------------------------------------------------------ rule-based estimate

def _words(text):
    return re.findall(r"[a-zA-Z']+", text.lower())


def measure(text, speech_results=None):
    """Signals used for the estimate. speech_results: list of compact speech analysis results."""
    words = _words(text)
    count = len(words)
    sentences = [s for s in re.split(r"[.?!]+", text) if len(s.split()) >= 2]
    lower = " " + " ".join(words) + " "
    linkers = sum(lower.count(f" {w} ") for w in LINKERS)
    long_words = sum(1 for w in words if len(w) >= 7)
    speech_results = [dict(s, clarity=s.get("clarity", (s.get("scores") or {}).get("Pronunciation clarity")))
                      for s in (speech_results or []) if s]

    def average(key, default):
        values = [(s[key], s.get("duration", 1)) for s in speech_results if s.get(key) is not None]
        total = sum(d for _v, d in values)
        return sum(v * d for v, d in values) / total if total else default

    fillers = sum(s.get("filler_total", 0) for s in speech_results)
    long_pauses = sum(s.get("long_pauses", 0) for s in speech_results)
    grammar = sum(len(s.get("grammar", [])) for s in speech_results)
    speaking_minutes = sum(s.get("duration", 0) for s in speech_results) / 60
    return {
        "words": count,
        "guiraud": len(set(words)) / math.sqrt(count) if count else 0,      # vocabulary range
        "sentence_length": count / max(len(sentences), 1),
        "linkers_per_100": linkers / max(count, 1) * 100,
        "long_word_share": long_words / max(count, 1),
        "grammar_per_100": grammar / max(count, 1) * 100,
        "fillers_per_100": fillers / max(count, 1) * 100,
        "long_pauses_per_min": long_pauses / speaking_minutes if speaking_minutes else 0,
        "wpm": average("wpm", 0),
        "clarity": average("clarity", None),
    }


def scale(value, low, high):
    """0 at low, 100 at high (clamped)."""
    if high == low:
        return 0.0
    return max(0.0, min(100.0, (value - low) / (high - low) * 100))


def estimate(text, speech_results=None):
    """
    Rule-based CEFR estimate. Returns a dictionary with level, criteria scores,
    or level None when there is not enough speech.
    """
    m = measure(text, speech_results)
    if m["words"] < 25:
        return {"level": None, "method": "rules", "reason": "Not enough speech to estimate the level (fewer than 25 words).",
                "measures": m}
    vocabulary = 0.7 * scale(m["guiraud"], 3.5, 10.5) + 0.3 * scale(m["long_word_share"], 0.08, 0.32)
    complexity = 0.5 * scale(m["sentence_length"], 6, 24) + 0.5 * scale(m["linkers_per_100"], 1.5, 10)
    accuracy = max(0.0, 100 - m["grammar_per_100"] * 25)
    if m["wpm"]:
        pace = 100 - max(0, 120 - m["wpm"]) * 1.4 - max(0, m["wpm"] - 175) * 1.2
    else:
        pace = 60
    fluency = max(0.0, min(100.0, 0.5 * pace + 0.5 * (100 - m["fillers_per_100"] * 8) - m["long_pauses_per_min"] * 8))
    clarity = m["clarity"] if m["clarity"] is not None else 70
    criteria = {"Vocabulary range": vocabulary, "Grammar and complexity": 0.5 * complexity + 0.5 * accuracy,
                "Fluency": fluency, "Pronunciation": clarity}
    index = 0.27 * vocabulary + 0.18 * complexity + 0.15 * accuracy + 0.22 * fluency + 0.18 * clarity
    bands = [(22, "A1"), (34, "A2"), (42, "A2+"), (51, "B1"), (59, "B1+"), (67, "B2"), (76, "B2+")]
    level = next((lvl for limit, lvl in bands if index < limit), "C1")
    # Higher levels need a long enough sample to show sustained, detailed speech.
    for minimum_words, highest in ((80, "B1+"), (130, "B2"), (200, "B2+")):
        if m["words"] < minimum_words and level_index(level) > level_index(highest):
            level = highest
            break
    return {"level": level, "method": "rules", "index": round(index, 1),
            "criteria": {k: cefr_for_score(v) for k, v in criteria.items()}, "measures": m}


def cefr_for_score(score):
    bands = [(22, "A1"), (34, "A2"), (42, "A2+"), (51, "B1"), (59, "B1+"), (67, "B2"), (76, "B2+")]
    return next((lvl for limit, lvl in bands if score < limit), "C1")


def personal_tips(result):
    """Tips based on the weakest measured areas."""
    m, tips = result.get("measures") or {}, []
    if not m:
        return tips
    if m.get("fillers_per_100", 0) > 3:
        tips.append(f"You used about {m['fillers_per_100']:.0f} filler words per 100 words. Replace 'um', 'uh' and 'like' "
                    "with a short silent pause.")
    if m.get("linkers_per_100", 10) < 2.5:
        tips.append("Your ideas were rarely linked. Use 'because', 'however', 'as a result' and 'for example' to show logic.")
    if m.get("sentence_length", 15) < 8:
        tips.append("Your sentences were very short. Combine ideas with 'which', 'when' and 'so that' to build longer sentences.")
    if m.get("guiraud", 10) < 5:
        tips.append("You repeated the same words often. Learn three synonyms for the words you use most.")
    if m.get("grammar_per_100", 0) > 1:
        tips.append("Grammar slips were noticeable. Review the corrections in this report and practise each correct form aloud.")
    if m.get("wpm") and m["wpm"] < 110:
        tips.append(f"Your pace was slow ({m['wpm']:.0f} words per minute). Practise prepared answers until they flow at 130 to 150.")
    if m.get("clarity") is not None and m["clarity"] < 70:
        tips.append("Some words were unclear. Record yourself, compare with a native speaker saying the same sentence, and repeat.")
    return tips
