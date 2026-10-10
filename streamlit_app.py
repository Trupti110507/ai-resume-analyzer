"""
AI Resume Analyzer - Streamlit version (for publishing online).

Uses the same modules as the Flask application (app.py): text extraction,
preprocessing, skill identification, matching, suggestions and the database.

A user must register and log in with an email and password before using the
analyzer. Only a hash of the password is stored. Every user sees only their
own reports.

Run on your own computer:   streamlit run streamlit_app.py
"""

import os

import pandas as pd
import streamlit as st
from werkzeug.security import check_password_hash, generate_password_hash

import database
from matching import calculate_score, match_skills
from preprocessing import top_keywords
from skill_identification import find_skills, skill_words
from suggestions import build_suggestions
from text_extraction import ResumeError, extract_text

MAX_RESUMES = 10
MAX_JOB_DESCRIPTION_LENGTH = 20000
SAMPLES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
SAMPLE_RESUMES = ["resume_1_strong_match.pdf", "sample_resume.pdf", "resume_2_partial_match.pdf", "resume_3_weak_match.pdf"]

st.set_page_config(page_title="AI Resume Analyzer", page_icon="📄", layout="centered")

# Hide Streamlit's grey hints inside input boxes ("Press Enter to submit form").
# Pressing Enter still works.
st.markdown('<style>[data-testid="InputInstructions"] { display: none !important; }</style>', unsafe_allow_html=True)


def read_sample(name, mode="rb"):
    with open(os.path.join(SAMPLES, name), mode) as f:
        return f.read()


def split_list(text):
    """Turn "Python, SQL" from the database back into a list."""
    return [item.strip() for item in (text or "").split(",") if item.strip()]


def analyze(user_id, resumes, title, description):
    """
    resumes: list of (file name, file type, resume text).
    Saves the job description, the resumes and the results for this user.
    Returns (required skills, list of results), best score first.
    """
    required_skills = find_skills(description)                 # Job Description Analysis Module
    if not required_skills:
        return [], []
    keywords = top_keywords(description, ignore=skill_words())
    jd_id = database.save_job_description(user_id, title, description, required_skills)   # Database Module
    results = []
    for file_name, file_type, resume_text in resumes:
        resume_skills = find_skills(resume_text)               # Resume Analysis Module
        matched, missing = match_skills(resume_skills, required_skills)   # Matching Module
        score = calculate_score(matched, required_skills)      # Score Calculation Module
        missing_keywords = [word for word in keywords if word not in resume_text.lower()]
        suggestions = build_suggestions(score, matched, missing, resume_text, missing_keywords)   # Suggestion Module
        resume_id = database.save_resume(user_id, file_name, file_type, resume_text)
        database.save_result(resume_id, jd_id, score, matched, missing, suggestions)
        results.append({"file_name": file_name, "score": score, "matched": matched,
                        "missing": missing, "suggestions": suggestions})
    results.sort(key=lambda r: (-r["score"], r["file_name"]))
    return required_skills, results


def show_report(result, total):
    """Report Module: score, matched skills, missing skills and suggestions for one resume."""
    st.metric("Resume match score", f"{result['score']:g}%")
    st.progress(min(int(round(result["score"])), 100))
    st.write(f"{len(result['matched'])} of {total} required skills were found in this resume. "
             f"Score = ({len(result['matched'])} ÷ {total}) × 100")
    left, right = st.columns(2)
    with left:
        st.markdown(f"**Matched skills ({len(result['matched'])})**")
        st.markdown("\n".join(f"- ✓ {skill}" for skill in result["matched"]) or "None of the required skills were found.")
    with right:
        st.markdown(f"**Missing skills ({len(result['missing'])})**")
        st.markdown("\n".join(f"- ✗ {skill}" for skill in result["missing"]) or "No required skill is missing.")
    st.markdown("**Suggestions for improvement**")
    st.markdown("\n".join(f"{number}. {text}" for number, text in enumerate(result["suggestions"], start=1)))


# ------------------------------------------------------- register and log in

@st.cache_resource
def prepare_database():
    database.init_db()
    return True


def current_user():
    """The logged-in user, or None."""
    user_id = st.session_state.get("user_id")
    return database.get_user(user_id) if user_id else None


def show_login_page():
    st.write("Compare resumes with a job description and see the match score, matched skills, "
             "missing skills and suggestions. Please log in to continue.")
    login_tab, register_tab = st.tabs(["Log in", "Register"])

    with login_tab:
        with st.form("login"):
            email = st.text_input("Email", max_chars=150).strip().lower()
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", type="primary"):
                account = database.get_user_by_email(email)
                if account is None or not check_password_hash(account["password_hash"], password):
                    st.error("The email or password is not correct.")
                else:
                    st.session_state.clear()
                    st.session_state["user_id"] = account["user_id"]
                    st.rerun()

    with register_tab:
        with st.form("register"):
            name = st.text_input("Name", max_chars=100).strip()
            email = st.text_input("Email", max_chars=150, key="register_email").strip().lower()
            password = st.text_input("Password (at least 8 characters)", type="password", key="register_password")
            if st.form_submit_button("Create account", type="primary"):
                if not name:
                    st.error("Please enter your name.")
                elif "@" not in email or "." not in email.split("@")[-1]:
                    st.error("Please enter a valid email address.")
                elif len(password) < 8:
                    st.error("The password must have at least 8 characters.")
                elif database.get_user_by_email(email):
                    st.error("An account with this email already exists. Please log in.")
                else:
                    # Only a hash of the password is stored, never the password itself.
                    user_id = database.create_user(name, email, generate_password_hash(password))
                    st.session_state.clear()
                    st.session_state["user_id"] = user_id
                    st.rerun()


def show_history_page(user):
    st.header("History")
    rows = database.list_results(user["user_id"])
    if not rows:
        st.write("You have no saved reports yet. Open \"New analysis\" to create one.")
        return
    st.write(f"{len(rows)} saved reports, newest first.")
    for row in rows:
        label = f"{row['analyzed_at'][:16]} | {row['title'] or 'Job description'} | {row['file_name']}: {row['match_score']:g}%"
        with st.expander(label):
            matched, missing = split_list(row["matched_skills"]), split_list(row["missing_skills"])
            show_report({"score": row["match_score"], "matched": matched, "missing": missing,
                         "suggestions": [line for line in (row["suggestions"] or "").split("\n") if line]},
                        len(split_list(row["required_skills"])))
            if st.button("Delete this report", key=f"delete_{row['result_id']}"):
                database.delete_result(row["result_id"], user["user_id"])
                st.session_state.pop("analysis", None)
                st.rerun()


def show_analysis_page(user):
    st.write("Upload one or more resumes, paste a job description, and see which required skills each resume shows and which it does not.")

    with st.expander("How the score is calculated"):
        st.write("Match score = (required skills found in the resume ÷ total required skills) × 100")
        st.write("Example: a job needs Python, SQL, Django and Git. The resume shows Python, SQL and Git. "
                 "Score = 3 ÷ 4 × 100 = 75%. Django is listed as a missing skill.")

    st.subheader("Step 1: Upload resumes")
    use_samples = st.checkbox("Use the sample resumes and sample job description instead of my own files")

    uploaded = []
    if not use_samples:
        uploaded = st.file_uploader(
            f"Resume files (PDF or DOCX, up to 2 MB each, up to {MAX_RESUMES} files)",
            type=["pdf", "docx"], accept_multiple_files=True,
            help="A scanned resume (a photo of a page) cannot be read.")
        st.caption("The text of each resume is saved in your account with its report. You can delete a report on the History page.")
    else:
        st.caption("Four sample resumes will be used: " + ", ".join(SAMPLE_RESUMES))

    st.subheader("Step 2: Enter the job details")
    sample_description = read_sample("sample_job_description.txt", "r") if use_samples else ""
    title = st.text_input("Job title (optional)", value="Junior Python Developer" if use_samples else "", max_chars=150)
    description = st.text_area("Job description", value=sample_description, height=260,
                               placeholder="Paste the full description, including required skills and qualifications.")

    if st.button("Analyze", type="primary"):
        files = [(name, read_sample(name)) for name in SAMPLE_RESUMES] if use_samples else [(f.name, f.getvalue()) for f in uploaded]

        if not files:
            st.error("Please choose a resume file.")
        elif len(files) > MAX_RESUMES:
            st.error(f"You can upload up to {MAX_RESUMES} resumes at one time.")
        elif not description.strip():
            st.error("Please enter a job description before analysis.")
        elif len(description) > MAX_JOB_DESCRIPTION_LENGTH:
            st.error("The job description is too long. Please shorten it.")
        else:
            resumes = []
            for name, data in files:
                # Every file is checked on its own, so one bad file does not stop the others.
                try:
                    file_type, text = extract_text(name, data)     # Resume Upload and Text Extraction Modules
                    resumes.append((name, file_type, text))
                except ResumeError as error:
                    st.error(f"{name}: {error}")
            if resumes:
                required_skills, results = analyze(user['user_id'], resumes, title.strip(), description.strip())
                if not required_skills:
                    st.error("No recognized skills were found. Check the resume or job description wording.")
                else:
                    st.session_state["analysis"] = {"title": title.strip(), "required": required_skills, "results": results}

    analysis = st.session_state.get("analysis")
    if analysis:
        results, total = analysis["results"], len(analysis["required"])
        st.divider()
        heading = analysis["title"] or "Job description"

        if len(results) == 1:
            st.header("Resume analysis report")
            st.caption(f"{heading} | Resume: {results[0]['file_name']}")
            show_report(results[0], total)
        else:
            st.header("Resume comparison")
            st.caption(f"{heading} | {len(results)} resumes")
            st.write(f"The job description asks for {total} skills. The resumes are listed from the highest match score to the lowest.")
            table = pd.DataFrame([{
                "Rank": rank, "Resume": r["file_name"], "Match score (%)": r["score"],
                "Matched": len(r["matched"]), "Missing": len(r["missing"]),
            } for rank, r in enumerate(results, start=1)])
            st.dataframe(
                table, hide_index=True, width="stretch",
                column_config={"Match score (%)": st.column_config.ProgressColumn("Match score (%)", min_value=0, max_value=100, format="%g%%")})
            st.subheader("Report for each resume")
            for rank, r in enumerate(results, start=1):
                with st.expander(f"{rank}. {r['file_name']}: {r['score']:g}%", expanded=(rank == 1)):
                    show_report(r, total)

        st.info("This score shows skill overlap only. It does not measure the quality of experience and is not a guarantee of selection.")



# ----------------------------------------------------------------- page

prepare_database()
st.title("AI Resume Analyzer")

user = current_user()
if user is None:
    st.session_state.pop("user_id", None)
    show_login_page()
else:
    with st.sidebar:
        st.write(f"Logged in as **{user['name']}**")
        st.caption(user["email"])
        page = st.radio("Menu", ["New analysis", "History"])
        if st.button("Log out"):
            st.session_state.clear()
            st.rerun()
    if page == "History":
        show_history_page(user)
    else:
        show_analysis_page(user)

st.divider()
st.caption("AI Resume Analyzer, a mini-project for S.Y. B.Sc. Computer Science. The score is an indication, not a prediction of selection.")
