"""
AI Resume Analyzer - main application.

A Flask web application that compares a resume with a job description and
shows a match score, matched skills, missing skills and suggestions.

Run:   python app.py     then open http://127.0.0.1:5000 in a browser.
"""

import os
import secrets
from functools import wraps

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import database
from matching import calculate_score, match_skills
from preprocessing import top_keywords
from skill_identification import find_skills, skill_words
from suggestions import build_suggestions
from text_extraction import MAX_FILE_SIZE, ResumeError, extract_text

MAX_JOB_DESCRIPTION_LENGTH = 20000   # characters
MAX_RESUMES = 10                     # resumes that can be uploaded at one time


def _secret_key():
    """A random key that signs the login session. Created once and kept in a local file."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "secret_key.txt")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        return f.read().strip()


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or _secret_key()
app.config["MAX_CONTENT_LENGTH"] = MAX_RESUMES * MAX_FILE_SIZE + 512 * 1024   # all files together, plus the form
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
database.init_db()


# ------------------------------------------------------------ helpers

@app.before_request
def load_user_and_check_form():
    """Runs before every request: finds the signed-in user and protects forms."""
    g.user = database.get_user(session["user_id"]) if "user_id" in session else None
    if "user_id" in session and g.user is None:
        session.clear()
    # Every form carries a secret token, so another website cannot submit forms for the user.
    if "form_token" not in session:
        session["form_token"] = secrets.token_hex(16)
    if request.method == "POST" and request.form.get("form_token") != session["form_token"]:
        abort(400)


@app.context_processor
def template_values():
    return {"user": g.get("user"), "form_token": session.get("form_token", "")}


def login_required(view):
    """Send a visitor who is not signed in to the login page."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "info")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def split_list(text):
    """Turn 'Python, SQL, Git' from the database back into a list."""
    return [item.strip() for item in (text or "").split(",") if item.strip()]


@app.errorhandler(413)
def file_too_large(_error):
    flash("The files are too large together. Each file can be up to 2 MB.", "error")
    return redirect(url_for("upload"))


@app.errorhandler(400)
def bad_request(_error):
    return render_template("message.html", title="This page has expired", text="Please go back, refresh the page and try again."), 400


@app.errorhandler(404)
def not_found(_error):
    return render_template("message.html", title="Page not found", text="The page you asked for does not exist."), 404


# -------------------------------------------------------------- pages

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or len(name) > 100:
            flash("Please enter your name.", "error")
        elif "@" not in email or "." not in email.split("@")[-1] or len(email) > 150:
            flash("Please enter a valid email address.", "error")
        elif len(password) < 8:
            flash("The password must have at least 8 characters.", "error")
        elif database.get_user_by_email(email):
            flash("An account with this email already exists. Please log in.", "error")
        else:
            # Only a hash of the password is stored, never the password itself.
            user_id = database.create_user(name, email, generate_password_hash(password))
            session.clear()
            session["user_id"] = user_id
            flash("Your account has been created.", "success")
            return redirect(url_for("upload"))
        return render_template("register.html", name=name, email=email)
    return render_template("register.html", name="", email="")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        account = database.get_user_by_email(email)
        if account is None or not check_password_hash(account["password_hash"], password):
            flash("The email or password is not correct.", "error")
            return render_template("login.html", email=email)
        session.clear()
        session["user_id"] = account["user_id"]
        return redirect(url_for("upload"))
    return render_template("login.html", email="")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """Step 1: the user uploads one or more resumes. Each file is checked and its text is extracted."""
    if request.method == "POST":
        files = [f for f in request.files.getlist("resume") if f and f.filename]
        if not files:
            flash("Please choose a resume file.", "error")
            return render_template("upload.html", max_resumes=MAX_RESUMES)
        if len(files) > MAX_RESUMES:
            flash(f"You can upload up to {MAX_RESUMES} resumes at one time.", "error")
            return render_template("upload.html", max_resumes=MAX_RESUMES)

        resume_ids = []
        for file in files:
            # Every file is checked on its own, so one bad file does not stop the others.
            try:
                file_type, text = extract_text(file.filename, file.read())
            except ResumeError as error:
                flash(f"{file.filename}: {error}", "error")
                continue
            # The file itself is not kept. Only its name and text are stored.
            file_name = secure_filename(file.filename) or "resume"
            resume_ids.append(database.save_resume(g.user["user_id"], file_name, file_type, text))

        if not resume_ids:
            return render_template("upload.html", max_resumes=MAX_RESUMES)
        session["resume_ids"] = resume_ids
        if len(resume_ids) == 1:
            flash("File uploaded successfully.", "success")
        else:
            flash(f"{len(resume_ids)} files uploaded successfully.", "success")
        return redirect(url_for("job"))
    return render_template("upload.html", max_resumes=MAX_RESUMES)


@app.route("/job", methods=["GET", "POST"])
@login_required
def job():
    """Step 2: the user enters the job description, and the analysis runs for every uploaded resume."""
    resumes = [database.get_resume(resume_id, g.user["user_id"]) for resume_id in session.get("resume_ids", [])]
    resumes = [resume for resume in resumes if resume is not None]
    if not resumes:
        flash("Please upload your resume first.", "info")
        return redirect(url_for("upload"))

    title = request.form.get("title", "").strip()[:150]
    description = request.form.get("description", "").strip()
    if request.method == "POST":
        if not description:
            flash("Please enter a job description before analysis.", "error")
        elif len(description) > MAX_JOB_DESCRIPTION_LENGTH:
            flash("The job description is too long. Please shorten it.", "error")
        else:
            try:
                jd_id, result_ids = analyze(resumes, title, description)
            except Exception:
                app.logger.exception("Analysis failed")
                flash("The analysis could not be completed. Please try again.", "error")
            else:
                if jd_id is None:
                    flash("No recognized skills were found. Check the resume or job description wording.", "error")
                elif len(result_ids) == 1:
                    return redirect(url_for("result", result_id=result_ids[0]))
                else:
                    return redirect(url_for("compare", jd_id=jd_id))
    listed = [{"file_name": r["file_name"], "file_type": r["file_type"], "words": len(r["extracted_text"].split())} for r in resumes]
    return render_template("job.html", resumes=listed, title=title, description=description)


def analyze(resumes, title, description):
    """
    The analysis itself. The job description is read once, then every resume is
    compared with it. Returns (job description id, list of result ids), or
    (None, []) if the job description contains no recognized skill.
    """
    required_skills = find_skills(description)          # Job Description Analysis Module
    if not required_skills:
        return None, []
    # Important job-description words (other than skills).
    keywords = top_keywords(description, ignore=skill_words())
    jd_id = database.save_job_description(g.user["user_id"], title, description, required_skills)

    result_ids = []
    for resume in resumes:
        resume_text = resume["extracted_text"]
        resume_skills = find_skills(resume_text)            # Resume Analysis Module
        matched, missing = match_skills(resume_skills, required_skills)   # Matching Module
        score = calculate_score(matched, required_skills)   # Score Calculation Module
        resume_lower = resume_text.lower()
        missing_keywords = [word for word in keywords if word not in resume_lower]
        suggestions = build_suggestions(score, matched, missing, resume_text, missing_keywords)   # Suggestion Module
        result_ids.append(database.save_result(resume["resume_id"], jd_id, score, matched, missing, suggestions))
    return jd_id, result_ids


@app.route("/compare/<int:jd_id>")
@login_required
def compare(jd_id):
    """Shows all resumes that were analyzed against one job description, best score first."""
    rows = database.list_results_for_job(jd_id, g.user["user_id"])
    if not rows:
        abort(404)
    results = [{
        "result_id": row["result_id"], "file_name": row["file_name"], "match_score": row["match_score"],
        "matched": split_list(row["matched_skills"]), "missing": split_list(row["missing_skills"]),
    } for row in rows]
    total = len(split_list(rows[0]["required_skills"]))
    return render_template("compare.html", job=rows[0], results=results, total=total)


@app.route("/result/<int:result_id>")
@login_required
def result(result_id):
    """Report Module: shows the score, matched skills, missing skills and suggestions."""
    row = database.get_result(result_id, g.user["user_id"])
    if row is None:
        abort(404)
    matched = split_list(row["matched_skills"])
    missing = split_list(row["missing_skills"])
    return render_template(
        "result.html", row=row, matched=matched, missing=missing,
        total=len(matched) + len(missing), suggestions=(row["suggestions"] or "").split("\n"))


@app.route("/history")
@login_required
def history():
    return render_template("history.html", results=database.list_results(g.user["user_id"]))


@app.route("/result/<int:result_id>/delete", methods=["POST"])
@login_required
def delete(result_id):
    if not database.delete_result(result_id, g.user["user_id"]):
        abort(404)
    flash("The analysis has been deleted.", "info")
    return redirect(url_for("history"))


if __name__ == "__main__":
    # 127.0.0.1 means the application is reachable only from this computer.
    app.run(host="127.0.0.1", port=5000, debug=False)
