"""
Database Module.

Stores users, resumes, job descriptions, analysis results and the skill list
in an SQLite database file (resume_analyzer.db). SQLite is part of Python, so
no separate database server has to be installed.
"""

import json
import os
import sqlite3
from datetime import datetime

from skills_data import SKILLS

DB_PATH = os.environ.get("RESUME_ANALYZER_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "resume_analyzer.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS user (
    user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name           VARCHAR(100) NOT NULL,
    email          VARCHAR(150) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    created_at     DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS resume (
    resume_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES user (user_id) ON DELETE CASCADE,
    file_name       VARCHAR(255) NOT NULL,
    file_type       VARCHAR(20) NOT NULL,
    upload_date     DATETIME NOT NULL,
    extracted_text  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_description (
    jd_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL REFERENCES user (user_id) ON DELETE CASCADE,
    title            VARCHAR(150),
    description      TEXT NOT NULL,
    required_skills  TEXT,
    created_at       DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_result (
    result_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id       INTEGER NOT NULL REFERENCES resume (resume_id) ON DELETE CASCADE,
    jd_id           INTEGER NOT NULL REFERENCES job_description (jd_id) ON DELETE CASCADE,
    match_score     DECIMAL(5,2) NOT NULL CHECK (match_score BETWEEN 0 AND 100),
    matched_skills  TEXT,
    missing_skills  TEXT,
    suggestions     TEXT,
    analyzed_at     DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS interview_result (
    interview_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES user (user_id) ON DELETE CASCADE,
    question        VARCHAR(255),
    transcript      TEXT,
    duration        DECIMAL(6,1),
    overall_score   DECIMAL(5,2) NOT NULL CHECK (overall_score BETWEEN 0 AND 100),
    details         TEXT NOT NULL,
    analyzed_at     DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS skill (
    skill_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name  VARCHAR(100) NOT NULL UNIQUE,
    category    VARCHAR(50)
);
"""


def now():
    """Current date and time as text, for the DATETIME columns."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect():
    """Open a connection. Rows can be read by column name, and foreign keys are enforced."""
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    """Create the tables if they do not exist, and fill the skill table from the skill list."""
    with connect() as db:
        db.executescript(SCHEMA)
        for name, category, _aliases in SKILLS:
            db.execute("INSERT OR IGNORE INTO skill (skill_name, category) VALUES (?, ?)", (name, category))


# ----------------------------------------------------------------- users

def create_user(name, email, password_hash):
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO user (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (name, email, password_hash, now()))
        return cursor.lastrowid


def get_user_by_email(email):
    with connect() as db:
        return db.execute("SELECT * FROM user WHERE email = ?", (email,)).fetchone()


def get_user(user_id):
    with connect() as db:
        return db.execute("SELECT * FROM user WHERE user_id = ?", (user_id,)).fetchone()


# --------------------------------------------------------------- resumes

def save_resume(user_id, file_name, file_type, extracted_text):
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO resume (user_id, file_name, file_type, upload_date, extracted_text) VALUES (?, ?, ?, ?, ?)",
            (user_id, file_name, file_type, now(), extracted_text))
        return cursor.lastrowid


def get_resume(resume_id, user_id):
    """Return the resume only if it belongs to this user."""
    with connect() as db:
        return db.execute("SELECT * FROM resume WHERE resume_id = ? AND user_id = ?", (resume_id, user_id)).fetchone()


# ------------------------------------------------- job descriptions, results

def save_job_description(user_id, title, description, required_skills):
    """Save one job description. Several resumes can be analyzed against it. Returns its id."""
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO job_description (user_id, title, description, required_skills, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, title, description, ", ".join(required_skills), now()))
        return cursor.lastrowid


def save_result(resume_id, jd_id, score, matched, missing, suggestions):
    """Save the analysis result of one resume against one job description. Returns the result id."""
    with connect() as db:
        cursor = db.execute(
            """INSERT INTO analysis_result
               (resume_id, jd_id, match_score, matched_skills, missing_skills, suggestions, analyzed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (resume_id, jd_id, score, ", ".join(matched), ", ".join(missing), "\n".join(suggestions), now()))
        return cursor.lastrowid


_RESULT_QUERY = """
    SELECT a.*, r.file_name, r.file_type, j.title, j.description, j.required_skills,
           (SELECT COUNT(*) FROM analysis_result x WHERE x.jd_id = a.jd_id) AS resumes_compared
      FROM analysis_result a
      JOIN resume r ON r.resume_id = a.resume_id
      JOIN job_description j ON j.jd_id = a.jd_id
     WHERE r.user_id = ?
"""


def get_result(result_id, user_id):
    """Return one analysis result, only if it belongs to this user."""
    with connect() as db:
        return db.execute(_RESULT_QUERY + " AND a.result_id = ?", (user_id, result_id)).fetchone()


def list_results(user_id):
    """All analysis results of this user, newest first."""
    with connect() as db:
        return db.execute(_RESULT_QUERY + " ORDER BY a.result_id DESC", (user_id,)).fetchall()


def list_results_for_job(jd_id, user_id):
    """All results for one job description (one per resume), best score first."""
    with connect() as db:
        return db.execute(
            _RESULT_QUERY + " AND a.jd_id = ? ORDER BY a.match_score DESC, r.file_name", (user_id, jd_id)).fetchall()


def delete_result(result_id, user_id):
    """Delete one analysis result of this user. Its job description and resume go too when nothing else uses them."""
    with connect() as db:
        row = db.execute(_RESULT_QUERY + " AND a.result_id = ?", (user_id, result_id)).fetchone()
        if row is None:
            return False
        db.execute("DELETE FROM analysis_result WHERE result_id = ?", (result_id,))
        db.execute(
            "DELETE FROM job_description WHERE jd_id = ? AND NOT EXISTS (SELECT 1 FROM analysis_result WHERE jd_id = ?)",
            (row["jd_id"], row["jd_id"]))
        db.execute(
            "DELETE FROM resume WHERE resume_id = ? AND NOT EXISTS (SELECT 1 FROM analysis_result WHERE resume_id = ?)",
            (row["resume_id"], row["resume_id"]))
        return True


# ------------------------------------------------------ voice interviews

def save_interview(user_id, question, result):
    """Save the analysis of one spoken interview answer. Returns its id."""
    with connect() as db:
        cursor = db.execute(
            """INSERT INTO interview_result
               (user_id, question, transcript, duration, overall_score, details, analyzed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, question, result["transcript"], round(result["duration"], 1), result["overall"],
             json.dumps(result), now()))
        return cursor.lastrowid


def list_interviews(user_id):
    """All voice interview results of this user, newest first, with the details unpacked."""
    with connect() as db:
        rows = db.execute("SELECT * FROM interview_result WHERE user_id = ? ORDER BY interview_id DESC", (user_id,)).fetchall()
    return [dict(row, details=json.loads(row["details"])) for row in rows]


def delete_interview(interview_id, user_id):
    with connect() as db:
        return db.execute("DELETE FROM interview_result WHERE interview_id = ? AND user_id = ?",
                          (interview_id, user_id)).rowcount > 0
