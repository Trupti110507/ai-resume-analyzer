"""
Tests for the AI Resume Analyzer.

Run from the project folder:   python -m unittest discover tests -v
"""

import io
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# The tests use their own temporary database, never the real one.
_TEMP = tempfile.mkdtemp()
os.environ["RESUME_ANALYZER_DB"] = os.path.join(_TEMP, "test.db")
os.environ["SECRET_KEY"] = "test-secret"

from pypdf import PdfWriter   # noqa: E402

import database               # noqa: E402
from app import app           # noqa: E402
from matching import calculate_score, match_skills       # noqa: E402
from preprocessing import clean_text, remove_stop_words, tokenize, top_keywords   # noqa: E402
from skill_identification import find_skills             # noqa: E402
from suggestions import build_suggestions                # noqa: E402
from text_extraction import ResumeError, extract_text    # noqa: E402

SAMPLES = os.path.join(ROOT, "samples")


def sample(name):
    with open(os.path.join(SAMPLES, name), "rb") as f:
        return f.read()


class MatchingTests(unittest.TestCase):
    def test_example_from_the_report_gives_75_percent(self):
        required = find_skills("We need Python, SQL, Django and Git.")
        resume = find_skills("Skills: Python, SQL, Git")
        matched, missing = match_skills(resume, required)
        self.assertEqual(matched, ["Python", "SQL", "Git"])
        self.assertEqual(missing, ["Django"])
        self.assertEqual(calculate_score(matched, required), 75.0)

    def test_score_limits(self):
        self.assertEqual(calculate_score([], ["Python"]), 0.0)
        self.assertEqual(calculate_score(["Python"], ["Python"]), 100.0)
        self.assertEqual(calculate_score([], []), 0.0)          # no division by zero
        self.assertEqual(calculate_score(["A"], ["A", "B", "C"]), 33.33)

    def test_extra_resume_skills_do_not_change_the_score(self):
        matched, missing = match_skills(["Python", "Java", "Docker"], ["Python"])
        self.assertEqual((matched, missing), (["Python"], []))


class SkillIdentificationTests(unittest.TestCase):
    def test_a_skill_is_not_found_inside_another_word(self):
        self.assertEqual(find_skills("JavaScript developer"), ["JavaScript"])   # not Java
        self.assertNotIn("Go", find_skills("We go to market with good governance"))
        self.assertNotIn("R", find_skills("Research and development for our customers"))

    def test_short_names_are_found_in_lists(self):
        found = find_skills("Languages: C, C++, Java, Python and R")
        for skill in ["C", "C++", "Java", "Python", "R"]:
            self.assertIn(skill, found)

    def test_symbols_in_skill_names(self):
        found = find_skills("C#, .NET, CI/CD, Node.js and REST APIs")
        self.assertEqual(sorted(found), sorted(["C#", "ASP.NET", "CI/CD", "Node.js", "REST API"]))

    def test_other_spellings_count_as_the_same_skill(self):
        self.assertEqual(find_skills("reactjs"), ["React"])
        self.assertEqual(find_skills("OOPs concepts"), ["Object-Oriented Programming"])
        self.assertEqual(find_skills("Structured Query Language"), ["SQL"])

    def test_capital_letters_and_spacing_do_not_matter(self):
        self.assertEqual(find_skills("PYTHON,sql ,  Django"), ["Python", "Django", "SQL"])

    def test_excel_the_verb_is_not_excel_the_skill(self):
        self.assertEqual(find_skills("Candidates who excel in teamwork"), ["Teamwork"])
        self.assertEqual(find_skills("Advanced Excel and Power BI"), ["Power BI", "MS Excel"])

    def test_text_with_no_skills(self):
        self.assertEqual(find_skills("We sell fresh vegetables every morning."), [])


class PreprocessingTests(unittest.TestCase):
    def test_cleaning_and_tokenizing(self):
        self.assertEqual(clean_text("  Python•  SQL — Git  "), "python, sql - git")
        self.assertEqual(tokenize("c++ and python3"), ["c++", "and", "python"])
        self.assertEqual(remove_stop_words(["the", "backend", "and", "api", "is"]), ["backend", "api"])

    def test_keywords_are_repeated_meaningful_words(self):
        text = "Backend work. The backend team builds backend services. Payments once."
        self.assertEqual(top_keywords(text), ["backend"])


class SuggestionTests(unittest.TestCase):
    def test_missing_skills_come_with_a_warning_to_stay_truthful(self):
        text = " ".join(build_suggestions(50.0, ["Python"], ["Django"], "Python projects education skills internship a@b.com " * 40, []))
        self.assertIn("Django", text)
        self.assertIn("Do not add skills you do not have", text)

    def test_short_resume_without_sections_gets_specific_advice(self):
        text = " ".join(build_suggestions(0.0, [], ["Python"], "I like computers.", ["backend"]))
        for expected in ["Projects section", "Education section", "Skills section", "email address", "very short", "backend"]:
            self.assertIn(expected, text)

    def test_complete_resume_gets_no_section_advice(self):
        resume = sample_text()
        text = " ".join(build_suggestions(100.0, ["Python"], [], resume, []))
        for unexpected in ["Add a Projects section", "Add an Education section", "Add a clear Skills section", "email address", "very short"]:
            self.assertNotIn(unexpected, text)


def sample_text():
    return extract_text("sample_resume.docx", sample("sample_resume.docx"))[1]


class TextExtractionTests(unittest.TestCase):
    def test_docx_and_pdf_give_the_same_skills(self):
        docx_type, docx_text = extract_text("resume.DOCX", sample("sample_resume.docx"))
        pdf_type, pdf_text = extract_text("resume.pdf", sample("sample_resume.pdf"))
        self.assertEqual((docx_type, pdf_type), ("DOCX", "PDF"))
        self.assertIn("Aarav Kulkarni", docx_text)
        self.assertIn("Aarav Kulkarni", pdf_text)
        self.assertEqual(find_skills(docx_text), find_skills(pdf_text))

    def test_unsupported_file_type(self):
        for name in ["resume.txt", "resume.doc", "photo.jpg", "resume"]:
            with self.assertRaisesRegex(ResumeError, "supported PDF or DOCX"):
                extract_text(name, b"hello")

    def test_wrong_content_with_right_extension(self):
        with self.assertRaisesRegex(ResumeError, "could not be extracted"):
            extract_text("resume.pdf", b"this is not really a pdf")
        with self.assertRaisesRegex(ResumeError, "could not be extracted"):
            extract_text("resume.docx", b"this is not really a docx")

    def test_pdf_without_text_such_as_a_scan(self):
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        buffer = io.BytesIO()
        writer.write(buffer)
        with self.assertRaisesRegex(ResumeError, "could not be extracted"):
            extract_text("scan.pdf", buffer.getvalue())

    def test_empty_and_oversized_files(self):
        with self.assertRaisesRegex(ResumeError, "empty"):
            extract_text("resume.pdf", b"")
        with self.assertRaisesRegex(ResumeError, "larger than 2 MB"):
            extract_text("resume.pdf", b"x" * (2 * 1024 * 1024 + 1))


class WebTests(unittest.TestCase):
    """Uses the whole application through its pages, as a browser would."""

    def setUp(self):
        self.client = app.test_client()

    def token(self, client=None):
        page = (client or self.client).get("/login").get_data(as_text=True)
        return re.search(r'name="form_token" value="([0-9a-f]+)"', page).group(1)

    def post(self, path, data, client=None, **kwargs):
        client = client or self.client
        return client.post(path, data={**data, "form_token": self.token(client)}, follow_redirects=True, **kwargs)

    def register(self, email, client=None, password="secret123"):
        return self.post("/register", {"name": "Test User", "email": email, "password": password}, client)

    def upload(self, name="sample_resume.docx", data=None, client=None):
        data = sample(name) if data is None else data
        return self.post("/upload", {"resume": (io.BytesIO(data), name)}, client, content_type="multipart/form-data")

    def test_home_page_opens_without_login(self):
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn("Check your resume against a job description", page)
        self.assertIn("Start analysis", page)

    def test_pages_need_login(self):
        for path in ["/upload", "/job", "/history", "/result/1"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertIn("/login", response.headers["Location"])

    def test_registration_checks(self):
        self.assertIn("at least 8 characters", self.register("short@example.com", password="123").get_data(as_text=True))
        self.assertIn("valid email", self.register("not-an-email").get_data(as_text=True))
        self.register("dup@example.com")
        other = app.test_client()
        self.assertIn("already exists", self.register("DUP@example.com", other).get_data(as_text=True))

    def test_password_is_stored_as_a_hash(self):
        self.register("hash@example.com", password="my-secret-password")
        stored = database.get_user_by_email("hash@example.com")["password_hash"]
        self.assertNotIn("my-secret-password", stored)
        self.assertTrue(stored.startswith(("scrypt:", "pbkdf2:")))

    def test_login_and_logout(self):
        self.register("login@example.com")
        self.post("/logout", {})
        self.assertEqual(self.client.get("/upload").status_code, 302)
        wrong = self.post("/login", {"email": "login@example.com", "password": "wrong-password"})
        self.assertIn("email or password is not correct", wrong.get_data(as_text=True))
        unknown = self.post("/login", {"email": "nobody@example.com", "password": "secret123"})
        self.assertIn("email or password is not correct", unknown.get_data(as_text=True))
        ok = self.post("/login", {"email": "login@example.com", "password": "secret123"})
        self.assertIn("Upload your resume", ok.get_data(as_text=True))

    def test_form_without_token_is_refused(self):
        response = self.client.post("/register", data={"name": "X", "email": "x@example.com", "password": "secret123"})
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(database.get_user_by_email("x@example.com"))

    def test_upload_messages(self):
        self.register("upload@example.com")
        self.assertIn("supported PDF or DOCX", self.upload("notes.txt", b"plain text").get_data(as_text=True))
        self.assertIn("could not be extracted", self.upload("broken.pdf", b"not a pdf").get_data(as_text=True))
        self.assertIn("larger than 2 MB", self.upload("big.pdf", b"x" * (3 * 1024 * 1024)).get_data(as_text=True))
        self.assertIn("Please choose a resume file", self.post("/upload", {}).get_data(as_text=True))
        ok = self.upload().get_data(as_text=True)
        self.assertIn("File uploaded successfully", ok)
        self.assertIn("Enter the job details", ok)

    def test_job_page_needs_a_resume_first(self):
        self.register("nojob@example.com")
        self.assertIn("upload your resume first", self.client.get("/job", follow_redirects=True).get_data(as_text=True))

    def test_full_analysis_and_history(self):
        self.register("flow@example.com")
        self.upload("sample_resume.pdf")

        self.assertIn("enter a job description before analysis", self.post("/job", {"title": "", "description": "   "}).get_data(as_text=True))
        self.assertIn("No recognized skills were found", self.post("/job", {"description": "We sell fresh vegetables."}).get_data(as_text=True))

        page = self.post("/job", {"title": "Trainee Developer", "description": "Required: Python, SQL, Django and Git."}).get_data(as_text=True)
        self.assertIn("Resume analysis report", page)
        self.assertIn("75%", page)
        self.assertIn("3 of 4 required skills", page)
        self.assertRegex(page, r"Missing skills \(1\)[\s\S]*Django")
        self.assertIn("Do not add skills you do not have", page)
        self.assertIn("not a guarantee of selection", page)

        history = self.client.get("/history").get_data(as_text=True)
        self.assertIn("Trainee Developer", history)
        self.assertIn("75%", history)

        result_id = database.list_results(database.get_user_by_email("flow@example.com")["user_id"])[0]["result_id"]
        stored = database.get_result(result_id, database.get_user_by_email("flow@example.com")["user_id"])
        self.assertEqual(stored["match_score"], 75)
        self.assertEqual(stored["matched_skills"], "Python, SQL, Git")
        self.assertEqual(stored["missing_skills"], "Django")
        self.assertEqual(stored["required_skills"], "Python, Django, SQL, Git")

        # A second job description can be checked against the same resume.
        jd = sample("sample_job_description.txt").decode()
        second = self.post("/job", {"title": "Junior Python Developer", "description": jd}).get_data(as_text=True)
        self.assertIn("Resume analysis report", second)
        self.assertEqual(len(database.list_results(database.get_user_by_email("flow@example.com")["user_id"])), 2)

        # Deleting one result leaves the other.
        self.post(f"/result/{result_id}/delete", {})
        remaining = self.client.get("/history").get_data(as_text=True)
        self.assertNotIn("Trainee Developer", remaining)
        self.assertIn("Junior Python Developer", remaining)
        self.assertEqual(self.client.get(f"/result/{result_id}").status_code, 404)

    def test_one_user_cannot_see_or_delete_another_users_result(self):
        self.register("owner@example.com")
        self.upload()
        self.post("/job", {"description": "Python and SQL"})
        owner_id = database.get_user_by_email("owner@example.com")["user_id"]
        result_id = database.list_results(owner_id)[0]["result_id"]
        self.assertEqual(self.client.get(f"/result/{result_id}").status_code, 200)

        other = app.test_client()
        self.register("other@example.com", other)
        self.assertEqual(other.get(f"/result/{result_id}").status_code, 404)
        self.assertEqual(other.post(f"/result/{result_id}/delete", data={"form_token": self.token(other)}).status_code, 404)
        self.assertNotIn("Python", other.get("/history").get_data(as_text=True))
        self.assertIsNotNone(database.get_result(result_id, owner_id))

    def upload_many(self, names, client=None):
        files = [(io.BytesIO(data if data is not None else sample(name)), name) for name, data in names]
        return self.post("/upload", {"resume": files}, client, content_type="multipart/form-data")

    def test_several_resumes_are_compared_against_one_job(self):
        self.register("many@example.com")
        user_id = database.get_user_by_email("many@example.com")["user_id"]
        # Uploaded in a mixed order on purpose: the comparison must sort by score.
        page = self.upload_many([("resume_3_weak_match.pdf", None), ("resume_1_strong_match.docx", None), ("resume_2_partial_match.pdf", None)]).get_data(as_text=True)
        self.assertIn("3 files uploaded successfully", page)
        self.assertIn("3 resumes will be compared", page)

        jd = sample("sample_job_description.txt").decode()
        page = self.post("/job", {"title": "Junior Python Developer", "description": jd}).get_data(as_text=True)
        self.assertIn("Resume comparison", page)
        order = [page.index(name) for name in ["resume_1_strong_match.docx", "resume_2_partial_match.pdf", "resume_3_weak_match.pdf"]]
        self.assertEqual(order, sorted(order), "resumes are listed from the highest score to the lowest")
        for score in ["100%", "25%", "0%"]:
            self.assertIn(score, page)

        results = database.list_results(user_id)
        self.assertEqual(len(results), 3)
        self.assertEqual(len({r["jd_id"] for r in results}), 1, "one job description is shared by all three results")
        self.assertEqual(sorted(r["match_score"] for r in results), [0, 25, 100])

        # Each resume still has its own full report, with a way back to the comparison.
        best = max(results, key=lambda r: r["match_score"])
        report = self.client.get(f"/result/{best['result_id']}").get_data(as_text=True)
        self.assertIn("16 of 16 required skills", report)
        self.assertIn("Back to comparison", report)
        self.assertIn("Compare", self.client.get("/history").get_data(as_text=True))

        # Deleting one result keeps the job description and the other results.
        jd_id = best["jd_id"]
        self.post(f"/result/{best['result_id']}/delete", {})
        self.assertEqual(len(database.list_results_for_job(jd_id, user_id)), 2)
        for r in database.list_results(user_id):
            self.post(f"/result/{r['result_id']}/delete", {})
        with database.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM job_description WHERE jd_id = ?", (jd_id,)).fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM resume WHERE user_id = ?", (user_id,)).fetchone()[0], 0)

    def test_a_bad_file_among_good_ones_is_reported_and_skipped(self):
        self.register("mixed@example.com")
        page = self.upload_many([("sample_resume.pdf", None), ("notes.txt", b"plain text"), ("broken.pdf", b"not a pdf"), ("sample_resume.docx", None)]).get_data(as_text=True)
        self.assertIn("notes.txt: Please upload a supported PDF or DOCX file.", page)
        self.assertIn("broken.pdf: Text could not be extracted.", page)
        self.assertIn("2 files uploaded successfully", page)
        self.assertIn("2 resumes will be compared", page)

    def test_only_bad_files_keeps_the_user_on_the_upload_page(self):
        self.register("allbad@example.com")
        page = self.upload_many([("a.txt", b"x"), ("b.jpg", b"y")]).get_data(as_text=True)
        self.assertIn("a.txt: Please upload a supported PDF or DOCX file.", page)
        self.assertIn("Upload your resume", page)
        self.assertNotIn("uploaded successfully", page)

    def test_at_most_ten_resumes_at_one_time(self):
        self.register("toomany@example.com")
        page = self.upload_many([(f"resume{i}.pdf", sample("sample_resume.pdf")) for i in range(11)]).get_data(as_text=True)
        self.assertIn("up to 10 resumes at one time", page)
        self.assertEqual(self.client.get("/job").status_code, 302)   # nothing was uploaded
        ok = self.upload_many([(f"resume{i}.pdf", sample("sample_resume.pdf")) for i in range(10)]).get_data(as_text=True)
        self.assertIn("10 files uploaded successfully", ok)

    def test_one_user_cannot_open_another_users_comparison(self):
        self.register("cmp-owner@example.com")
        self.upload_many([("sample_resume.pdf", None), ("resume_2_partial_match.pdf", None)])
        self.post("/job", {"description": "Python, SQL and Git"})
        owner_id = database.get_user_by_email("cmp-owner@example.com")["user_id"]
        jd_id = database.list_results(owner_id)[0]["jd_id"]
        self.assertEqual(self.client.get(f"/compare/{jd_id}").status_code, 200)
        other = app.test_client()
        self.register("cmp-other@example.com", other)
        self.assertEqual(other.get(f"/compare/{jd_id}").status_code, 404)

    def test_text_typed_by_the_user_is_shown_safely(self):
        self.register("safe@example.com")
        self.upload()
        page = self.post("/job", {"title": "<script>alert(1)</script>", "description": "Python"}).get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_skill_table_is_filled(self):
        with database.connect() as db:
            count = db.execute("SELECT COUNT(*) FROM skill").fetchone()[0]
            python = db.execute("SELECT category FROM skill WHERE skill_name = 'Python'").fetchone()[0]
        self.assertGreater(count, 100)
        self.assertEqual(python, "Programming Language")


if __name__ == "__main__":
    unittest.main()
