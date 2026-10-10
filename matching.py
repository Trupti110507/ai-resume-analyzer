"""
Matching Module and Score Calculation Module.

Compares the skills required by the job description with the skills found in
the resume, and calculates the match score.

Formula:
    match score = (number of required skills found in the resume
                   / total number of required skills) x 100

Example: the job needs Python, SQL, Django and Git. The resume has Python,
SQL and Git. Score = (3 / 4) x 100 = 75%. Django is a missing skill.
"""


def match_skills(resume_skills, required_skills):
    """Split the required skills into those found in the resume and those not found."""
    resume_set = set(resume_skills)
    matched = [skill for skill in required_skills if skill in resume_set]
    missing = [skill for skill in required_skills if skill not in resume_set]
    return matched, missing


def calculate_score(matched, required_skills):
    """Return the match score as a percentage with two decimal places."""
    if not required_skills:
        return 0.0
    return round(len(matched) / len(required_skills) * 100, 2)
