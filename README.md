# AI Resume Analyzer

A web application that compares a resume with a job description and shows a match
score, matched skills, missing skills and suggestions for improvement.

Mini-project, S.Y. B.Sc. Computer Science (Software Engineering), SPPU.

Technologies: Python 3, Flask, SQLite, HTML, CSS, JavaScript, pypdf, python-docx.
Everything is free, and the application works offline after the packages are installed.

## How to run

1. Install Python 3.9 or newer from https://www.python.org/downloads/ .
   During installation, tick "Add python.exe to PATH".
2. Double-click `run.bat`.
   The first run installs the packages (needs internet), then the browser opens
   http://127.0.0.1:5000 .
3. Keep the black window open while you use the application. Close it to stop.

Manual way, in a Command Prompt opened in this folder:

    python -m pip install -r requirements.txt
    python app.py

## Online version (Streamlit)

`streamlit_app.py` is a second front end for publishing the project online with
Streamlit Community Cloud. It uses the same analysis modules as the Flask application.
A user must register and log in with an email and password before the analyzer opens.
Only a hash of the password is stored, and every user sees only their own reports
("History" in the menu on the left).

Note: Streamlit Community Cloud does not keep files permanently. When the app restarts
(after an update, or after it has been asleep), the database is empty again and users
must register again.

Run it on your own computer:

    python -m streamlit run streamlit_app.py

Publish it: put this folder in a GitHub repository, sign in at https://share.streamlit.io
with GitHub, choose "Create app", select the repository, and set the main file to
`streamlit_app.py`.

## How to use

1. Click "Start analysis" and register with a name, email and password.
2. Upload one resume, or up to 10 at one time (PDF or DOCX, up to 2 MB each).
   To choose several files, hold the Ctrl key while clicking them. The `samples` folder has four resumes to try.
3. Paste a job description. Try the text in `samples/sample_job_description.txt`.
4. Read the report. With several resumes you first see a comparison, ranked from the
   highest score to the lowest, and can open each resume's own report from there.
   "History" lists your earlier reports.

## Voice interview (online version)

Open "Voice interview" in the menu, pick a question, click the microphone, answer, and
click it again to stop. "Analyze my answer" then reports, each out of 100:

- Pronunciation clarity: how confidently each word was recognized by the speech model
- Fluency: filler words (um, uh, like, you know), repeated words and long pauses
- Pace: words per minute (comfortable range 120 to 160)
- Tone and pitch: how much the voice rises and falls (a flat voice sounds monotone) and steady volume
- English usage: vocabulary variety, sentence length and common grammar slips

Speech is turned into text by faster-whisper, a free speech-to-text model that runs on the
server (about 150 MB, downloaded automatically the first time). Pitch and loudness are measured
directly from the sound with NumPy. The scores are practice estimates, not a certified test.
Results are saved in the `interview_result` table and listed under "History".

## How the score is calculated

    match score = (required skills found in the resume / total required skills) x 100

Example: the job needs Python, SQL, Django and Git. The resume shows Python, SQL and Git.
Score = 3 / 4 x 100 = 75%. Django is a missing skill.

The score shows skill overlap only. It is not a prediction of selection.

## Files and the modules of the report

| File | Module in the report | What it does |
| --- | --- | --- |
| `app.py` | Resume Upload, Report | Web pages, login, and the steps of an analysis |
| `text_extraction.py` | Resume Upload, Text Extraction | Checks the file and reads text from PDF and DOCX |
| `preprocessing.py` | Text Preprocessing | Cleans text, splits it into words, removes stop words, finds keywords |
| `skill_identification.py` | Resume Analysis, Job Description Analysis | Finds skills in a text |
| `skills_data.py` | (data) | The predefined skill list and the stop-word list |
| `matching.py` | Matching, Score Calculation | Compares skills and calculates the score |
| `suggestions.py` | Suggestion | Writes the suggestions |
| `database.py` | Database | SQLite tables: user, resume, job_description, analysis_result, skill |
| `speech_analysis.py` | Voice Interview Analysis | Speech to text, pitch, loudness, pace, fillers, pronunciation and English scores |
| `streamlit_app.py` | Report (online version) | The same analysis as a Streamlit page, with register, login and history |
| `templates/` | Input and output screens | HTML pages |
| `static/` | | CSS styles and JavaScript |
| `tests/` | Testing | 54 automatic tests |
| `samples/` | | Four sample resumes (expected scores 100%, 62.5%, 25%, 0%) and a sample job description |
| `screenshots/` | | Screenshots of every screen, for the report |

## Database tables

- `user` (user_id, name, email, password_hash, created_at)
- `resume` (resume_id, user_id, file_name, file_type, upload_date, extracted_text)
- `job_description` (jd_id, user_id, title, description, required_skills, created_at)
- `analysis_result` (result_id, resume_id, jd_id, match_score, matched_skills, missing_skills, suggestions, analyzed_at)
- `interview_result` (interview_id, user_id, question, transcript, duration, overall_score, details, analyzed_at)
- `skill` (skill_id, skill_name, category)

The database is the file `resume_analyzer.db`, created automatically on the first run.
Delete that file to start with an empty database.

## Run the tests

    python -m unittest discover tests -v

## Limitations

- A scanned resume (a photo of a page) cannot be read, because it contains no text.
- Only skills in the predefined list (`skills_data.py`) are recognized.
- The system matches words. It cannot judge how well a person knows a skill.
- The application runs on one computer and is not published on the internet.

## Add a new skill

Open `skills_data.py` and add a line such as:

    ("Rust", "Programming Language", ["rustlang"]),

Then restart the application.
