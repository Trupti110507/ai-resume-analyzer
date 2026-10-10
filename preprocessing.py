"""
Text Preprocessing Module.

Prepares raw text for analysis using basic Natural Language Processing steps:
  1. cleaning       - lower case, remove unusual symbols, tidy the spacing
  2. tokenization   - split the text into separate words
  3. stop words     - remove common words such as "the" and "and"
  4. keyword count  - find the words a job description uses most often
"""

import re
from collections import Counter

from skills_data import JOB_FILLER_WORDS, STOP_WORDS


def clean_text(text):
    """Return the text in lower case with tidy spacing and plain punctuation."""
    text = text.lower()
    # Curly quotes, long dashes and bullet symbols are replaced by plain characters.
    text = text.replace("’", "'").replace("‘", "'")
    text = re.sub(r"[–—]", "-", text)
    text = re.sub(r"[•●▪◦‣➢]", ", ", text)
    # Keep letters, digits and the symbols that appear in skill names (C++, C#, .NET, CI/CD).
    text = re.sub(r"[^a-z0-9+#./&'\-,:;()|\n ]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def tokenize(text):
    """Split cleaned text into a list of words."""
    return re.findall(r"[a-z][a-z+#]*", text)


def remove_stop_words(words):
    """Remove common words that do not help in matching."""
    return [word for word in words if word not in STOP_WORDS and len(word) > 2]


def top_keywords(text, ignore=(), limit=8):
    """
    Return the most frequent meaningful words in a job description.

    ignore: words to leave out (for example words already counted as skills).
    """
    words = remove_stop_words(tokenize(clean_text(text)))
    ignore = set(ignore) | JOB_FILLER_WORDS
    counts = Counter(word for word in words if word not in ignore)
    # A keyword must appear at least twice to be considered important.
    return [word for word, count in counts.most_common(limit) if count >= 2]
