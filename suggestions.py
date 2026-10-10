"""
Suggestion Module.

Creates practical suggestions from the analysis result. The rules are simple
and transparent, so every suggestion can be explained. The system never tells
a user to add a skill they do not have.
"""

import re


def _join(items, limit=6):
    """Write a list as 'A, B and C', shortening long lists."""
    items = list(items)
    shown = items[:limit]
    extra = len(items) - len(shown)
    text = ", ".join(shown[:-1]) + (" and " if len(shown) > 1 else "") + shown[-1]
    return text + (f" and {extra} more" if extra > 0 else "")


def build_suggestions(score, matched, missing, resume_text, missing_keywords):
    """Return a list of suggestion sentences for the result page."""
    suggestions = []
    text = resume_text.lower()
    word_count = len(resume_text.split())

    # 1. Overall comment based on the score.
    if score >= 80:
        suggestions.append("Your resume covers most of the skills this job asks for. Check that each skill is supported by a project, internship or course.")
    elif score >= 50:
        suggestions.append("Your resume covers a fair share of the required skills. Improving the points below can make the match clearer.")
    else:
        suggestions.append("Your resume shows only a few of the skills this job asks for. Review the missing skills and decide whether this role suits your current profile.")

    # 2. Missing skills. The user is reminded to stay truthful.
    if missing:
        suggestions.append(
            f"The job description asks for {_join(missing)}, which were not found in your resume. "
            "If you have really used them, mention them clearly with an example. "
            "If you have not, consider learning them first. Do not add skills you do not have."
        )

    # 3. Matched skills should be easy to find.
    if matched:
        suggestions.append(
            f"Make your matching skills ({_join(matched)}) easy to find. "
            "List them in a Skills section and show where you used each one."
        )

    # 4. Important resume sections.
    if not re.search(r"\bprojects?\b", text):
        suggestions.append("Add a Projects section. For each project, write what it does, the technologies used and your own contribution.")
    if not re.search(r"\b(education|qualification|b\.?sc|b\.?e|b\.?tech|bca|mca|degree)\b", text):
        suggestions.append("Add an Education section with your degree, college, university and year of passing.")
    if not re.search(r"\b(skills|technical skills|technologies)\b", text):
        suggestions.append("Add a clear Skills section so that a reader can find your skills quickly.")
    if not re.search(r"\b(internship|intern|experience|worked|training)\b", text):
        suggestions.append("Mention any internship, training, freelance work or college activity that shows practical experience.")
    if not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", resume_text):
        suggestions.append("No email address was found. Add your email address and phone number at the top of the resume.")

    # 5. Length of the resume.
    if word_count < 150:
        suggestions.append(f"The resume is very short (about {word_count} words). Add more detail about your projects, skills and achievements.")
    elif word_count > 900:
        suggestions.append(f"The resume is long (about {word_count} words). For a student or fresher, one to two pages is usually enough.")

    # 6. Other words the job description repeats that the resume does not use.
    if missing_keywords:
        suggestions.append(
            f"The job description repeats these words, which do not appear in your resume: {_join(missing_keywords)}. "
            "Use them where they honestly describe your work."
        )

    return suggestions
