"""
Skill Identification (used by the Resume Analysis and Job Description Analysis modules).

Finds which skills from the predefined list appear in a piece of text.
The same function is used for the resume and for the job description, so both
are judged by exactly the same rules.
"""

import re

from preprocessing import clean_text
from skills_data import SKILLS

# A skill must stand alone: "java" must not match inside "javascript".
_BEFORE = r"(?<![a-z0-9+#.])"
_AFTER = r"(?![a-z0-9+#])"

# Very short names need stricter rules, because "c", "r" and "go" also appear in
# ordinary writing. They count only inside a list ("C, C++, Java") or when
# followed by the word "programming" or "language".
_SHORT_NAMES = {"c", "r", "go"}
_SINGLE_LETTER = r"(?:^|[,/(|:;]\s*|\band\s+){letter}(?=\s*(?:[,/)|;]|$|\.\s|\.$|and\b|programming|language))"


def _build_pattern(name, aliases):
    """Create one search pattern that matches the skill name or any of its aliases."""
    parts = []
    for term in [name] + list(aliases):
        term = term.lower()
        if term in _SHORT_NAMES:
            parts.append(_SINGLE_LETTER.format(letter=re.escape(term)))
        else:
            # "node.js" should also match "node js" and "nodejs".
            escaped = re.escape(term).replace(r"\ ", r"[\s\-]+").replace(r"\.", r"[\.\s]?")
            # "excel" is a skill in "MS Excel", but a verb in "excel in" or "excel at".
            verb_check = r"(?!\s+(?:in|at)\b)" if term == "excel" else ""
            parts.append(_BEFORE + escaped + _AFTER + verb_check)
    return re.compile("|".join(parts), re.MULTILINE)


# Patterns are built once when the application starts.
_PATTERNS = [(name, category, _build_pattern(name, aliases)) for name, category, aliases in SKILLS]


def find_skills(text):
    """Return the list of skill names found in the text, in the order of the skill list."""
    cleaned = clean_text(text)
    return [name for name, _category, pattern in _PATTERNS if pattern.search(cleaned)]


def skill_words():
    """All single words used in skill names and aliases (used to avoid repeating them as keywords)."""
    words = set()
    for name, _category, aliases in SKILLS:
        for term in [name] + list(aliases):
            words.update(re.findall(r"[a-z][a-z+#]*", term.lower()))
    return words
