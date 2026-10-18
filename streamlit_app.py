"""
AI Resume Analyzer - Streamlit version (for publishing online).

Uses the same modules as the Flask application (app.py): text extraction,
preprocessing, skill identification, matching, suggestions and the database.

The "AI interview" page runs a mock video interview for any role with Emma, an AI
interviewer who speaks US English (see ai_interview_page.py and interviewer.py).

The "Voice interview" page records a spoken interview answer from the microphone
and reports pronunciation, fluency, pace, tone and pitch, and English usage.

A user must register and log in with an email and password before using the
analyzer. Only a hash of the password is stored. Every user sees only their
own reports.

Run on your own computer:   streamlit run streamlit_app.py
"""

import os

import pandas as pd
import streamlit as st
from werkzeug.security import check_password_hash, generate_password_hash

import ai_interview_page
import database
import english_level
import interviewer
import speech_analysis
from matching import calculate_score, match_skills
from preprocessing import top_keywords
from skill_identification import find_skills, skill_words
from suggestions import build_suggestions
from text_extraction import ResumeError, extract_text

MAX_RESUMES = 10
MAX_JOB_DESCRIPTION_LENGTH = 20000
SAMPLES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
SAMPLE_RESUMES = ["resume_1_strong_match.pdf", "sample_resume.pdf", "resume_2_partial_match.pdf", "resume_3_weak_match.pdf"]

st.set_page_config(page_title="Resume Analysis Report", page_icon="📄", layout="centered")

# Hide Streamlit's grey hints inside input boxes ("Press Enter to submit form").
# Pressing Enter still works.
st.markdown("""<style>
[data-testid="InputInstructions"] { display: none !important; }
h1 { letter-spacing: -0.3px; }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] a { color: #9ADBD4; }
/* Interview report summary band */
.ri-band { display: flex; gap: 28px; align-items: center; flex-wrap: wrap; padding: 20px 22px; margin: 6px 0 14px;
  background: #ffffff; border: 1px solid #D3DCE3; border-radius: 12px; }
.ri-score { min-width: 150px; }
.ri-big { font-family: "Source Serif 4", Georgia, serif; font-size: 54px; font-weight: 600; line-height: 1; color: #172338; }
.ri-big small { font-size: 18px; color: #5B6577; margin-left: 4px; font-weight: 500; }
.ri-verdict { margin-top: 6px; color: #0F6B66; font-weight: 600; }
.ri-bars { flex: 1; min-width: 240px; display: grid; gap: 10px; }
.ri-row { display: grid; grid-template-columns: 130px 1fr 92px; align-items: center; gap: 12px; font-size: 15px; }
.ri-track { height: 8px; border-radius: 4px; background: #E8EEF1; overflow: hidden; }
.ri-track i { display: block; height: 100%; background: #0F6B66; border-radius: 4px; }
.ri-num { font-variant-numeric: tabular-nums; font-weight: 600; }
.ri-na { font-weight: 400; color: #5B6577; font-size: 13px; }
/* English level (CEFR) */
.el-wrap { background: #ffffff; border: 1px solid #D3DCE3; border-radius: 12px; padding: 18px 20px; margin: 4px 0 12px; }
.el-head { display: flex; align-items: center; gap: 16px; margin-bottom: 14px; }
.el-level { font-family: "Source Serif 4", Georgia, serif; font-size: 44px; font-weight: 600; line-height: 1;
  color: #ffffff; background: #172338; border-radius: 10px; padding: 10px 16px; min-width: 86px; text-align: center; }
.el-name { font-weight: 600; font-size: 17px; }
.el-gap { color: #5B6577; font-size: 14.5px; margin-top: 2px; }
.el-scale { display: grid; grid-template-columns: repeat(9, 1fr); gap: 4px; }
.el-cell { text-align: center; padding: 7px 0; font-size: 13px; font-weight: 600; border-radius: 6px;
  background: #E8EEF1; color: #5B6577; border: 2px solid transparent; }
.el-cell.el-past { background: #CFE5E2; color: #0F6B66; }
.el-cell.el-goal { border-color: #0F6B66; }
.el-cell.el-now { background: #172338; color: #ffffff; }
.el-legend { margin-top: 8px; font-size: 12.5px; color: #5B6577; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.el-key { display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-left: 8px; }
.el-key-now { background: #172338; } .el-key-goal { border: 2px solid #0F6B66; }
</style>""", unsafe_allow_html=True)


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
    ai_interview_page.show_ai_history(user)
    interviews = database.list_interviews(user["user_id"])
    if interviews:
        st.subheader("Voice interviews")
        for row in interviews:
            with st.expander(f"{row['analyzed_at'][:16]} | {row['question']}: {row['overall_score']:g} / 100"):
                show_interview_report(row["details"])
                if st.button("Delete this interview", key=f"delete_interview_{row['interview_id']}"):
                    database.delete_interview(row["interview_id"], user["user_id"])
                    st.session_state.pop("interview", None)
                    st.rerun()
        st.subheader("Resume reports")
    rows = database.list_results(user["user_id"])
    if not rows:
        st.write("You have no saved resume reports yet. Open \"New analysis\" to create one.")
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
            st.header("Analysis result")
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



# ------------------------------------------------------- voice interview

@st.cache_resource(show_spinner="Loading the speech model (first time only, about a minute)...")
def speech_model():
    return speech_analysis.load_model()


def show_interview_report(r):
    """Voice Interview Report: overall score, the five part scores, the details and suggestions."""
    st.metric("Speaking score", f"{r['overall']:g} / 100  ({r['band']})")
    st.progress(min(int(round(r["overall"])), 100))
    for name, value in r["scores"].items():
        left, right = st.columns([2, 3])
        left.write(f"**{name}**: {value:g} ({speech_analysis.band(value)})")
        right.progress(min(int(round(value)), 100))

    st.markdown("**What was measured**")
    fillers = ", ".join(f"{k} ({v})" for k, v in sorted(r["fillers"].items(), key=lambda x: -x[1])) or "none"
    pitch = (f"{r['median_pitch']:.0f} Hz on average, moving across {r['pitch_range']:.1f} semitones"
             if r["median_pitch"] else "not enough voiced sound to measure")
    st.markdown("\n".join([
        f"- Length: {r['duration']:.0f} seconds, {r['word_count']} words",
        f"- Pace: {r['wpm']:.0f} words per minute (comfortable range 120 to 160)",
        f"- Pauses: {r['pauses']} short, {r['long_pauses']} long (2 seconds or more)",
        f"- Filler words: {fillers}; words repeated back to back: {r['repeats']}",
        f"- Pitch: {pitch}",
        f"- Volume: {r['average_db']:.0f} dB on average, steadiness spread {r['loudness_spread']:.1f} dB",
        f"- Vocabulary variety: {r['variety'] * 100:.0f}% different words; average sentence {r['sentence_length']:.0f} words",
        f"- Words that were hard to recognize: {', '.join(r['unclear_words']) or 'none'}",
        f"- Skills you mentioned: {', '.join(r['skills']) or 'none from the skill list'}",
    ]))
    st.markdown("**Suggestions for improvement**")
    st.markdown("\n".join(f"{n}. {t}" for n, t in enumerate(r["suggestions"], start=1)))
    if r.get("english") is not None:
        ai_interview_page.show_english_level(r["english"])
    with st.expander("What you said (transcript)"):
        st.write(r["transcript"] or "No words were recognized.")


def show_interview_page(user):
    st.header("Voice interview")
    st.write("Pick a question, switch on the microphone and answer as you would in an interview. "
             "The AI listens to your answer and reports your pronunciation, fluency, pace, tone and pitch, "
             "and English usage, with suggestions.")
    question = st.selectbox("Interview question", speech_analysis.INTERVIEW_QUESTIONS + ["My own question"])
    if question == "My own question":
        question = st.text_input("Type the question", max_chars=200).strip() or "Free answer"
    st.info(f"**{question}**  \nSpeak for 30 seconds to 3 minutes. Use a quiet room and keep the microphone close.")

    recording = st.audio_input("Click the microphone to start, and click it again to stop", key="interview_audio")
    with st.expander("Or upload a recording instead (WAV, MP3, M4A)"):
        uploaded = st.file_uploader("Recording", type=["wav", "mp3", "m4a", "ogg", "webm"], key="interview_file")
    audio_file = recording or uploaded

    if st.button("Analyze my answer", type="primary"):
        if audio_file is None:
            st.error("Please record your answer first (click the microphone, speak, then click it again).")
        elif audio_file.size > 25 * 1024 * 1024:
            st.error("The recording is too large. Please keep it under 3 minutes.")
        else:
            try:
                audio = speech_analysis.load_audio(audio_file.getvalue())
            except Exception:
                audio = None
                st.error("This recording could not be read. Please record again.")
            if audio is not None:
                seconds = len(audio) / speech_analysis.SAMPLE_RATE
                if seconds < speech_analysis.MIN_SECONDS:
                    st.error(f"The answer is too short. Please speak for at least {speech_analysis.MIN_SECONDS} seconds (30 seconds or more gives a better result).")
                elif seconds > speech_analysis.MAX_SECONDS + 5:
                    st.error("The answer is longer than 3 minutes. Please record a shorter answer.")
                else:
                    model = speech_model()
                    with st.spinner("Listening to your answer and analyzing it..."):
                        words = speech_analysis.transcribe(audio, model)
                    if not words:
                        st.error("No speech was recognized. Check that the microphone is working and speak clearly.")
                    else:
                        spoken_skills = find_skills(" ".join(w["word"] for w in words))
                        result = speech_analysis.analyze_speech(audio, words, spoken_skills)
                        rule_level = english_level.estimate(result["transcript"], [result])
                        result["english"], _ai = interviewer.assess_english(
                            [{"answer": result["transcript"], "speech": result, "evaluation": {}}], rule_level)
                        database.save_interview(user["user_id"], question, result)
                        st.session_state["interview"] = {"question": question, "result": result}

    saved = st.session_state.get("interview")
    if saved:
        st.divider()
        st.subheader("Voice interview report")
        st.caption(f"Question: {saved['question']}")
        show_interview_report(saved["result"])
        st.info("These scores are automatic estimates for practice. They are not a certified English test.")


# ----------------------------------------------------------------- page

prepare_database()
st.title("Resume Analysis Report")

user = current_user()
if user is None:
    st.session_state.pop("user_id", None)
    show_login_page()
else:
    with st.sidebar:
        st.write(f"Logged in as **{user['name']}**")
        st.caption(user["email"])
        page = st.radio("Menu", ["New analysis", "AI interview", "Voice interview", "History"])
        if st.button("Log out"):
            st.session_state.clear()
            st.rerun()
    if page == "History":
        show_history_page(user)
    elif page == "AI interview":
        ai_interview_page.show_ai_interview_page(user, speech_model)
    elif page == "Voice interview":
        show_interview_page(user)
    else:
        show_analysis_page(user)

st.divider()
st.caption("Resume Analysis Report, a mini-project for S.Y. B.Sc. Computer Science. The score is an indication, not a prediction of selection.")
