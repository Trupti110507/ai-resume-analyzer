"""Tests for the login of the Streamlit version. Run: python -m unittest discover tests -v"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["RESUME_ANALYZER_DB"] = os.path.join(tempfile.mkdtemp(), "test_streamlit.db")

try:
    from streamlit.testing.v1 import AppTest
except ImportError:          # Streamlit is needed only for the online version.
    AppTest = None

import database

APP = os.path.join(ROOT, "streamlit_app.py")


def texts(app):
    return " ".join([e.value for e in app.error] + [m.value for m in app.markdown] + [h.value for h in app.header])


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class StreamlitLoginTests(unittest.TestCase):
    def open_app(self):
        return AppTest.from_file(APP, default_timeout=60).run()

    def register(self, app, name, email, password):
        app.text_input[2].set_value(name)
        app.text_input(key="register_email").set_value(email)
        app.text_input(key="register_password").set_value(password)
        app.button[1].click()
        return app.run()

    def login(self, app, email, password):
        app.text_input[0].set_value(email)
        app.text_input[1].set_value(password)
        app.button[0].click()
        return app.run()

    def test_1_analyzer_is_hidden_before_login(self):
        app = self.open_app()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.checkbox), 0)
        self.assertEqual(len(app.text_area), 0)
        self.assertIn("Please log in", texts(app))

    def test_2_register_checks_the_details(self):
        app = self.register(self.open_app(), "Asha", "asha@example.com", "short")
        self.assertIn("at least 8 characters", texts(app))
        app = self.register(self.open_app(), "Asha", "not-an-email", "longenough1")
        self.assertIn("valid email", texts(app))
        self.assertIsNone(database.get_user_by_email("asha@example.com"))

    def test_3_register_login_analyze_history_logout(self):
        app = self.register(self.open_app(), "Asha", "asha@example.com", "longenough1")
        self.assertFalse(app.exception)
        self.assertIn("Asha", texts(app))
        account = database.get_user_by_email("asha@example.com")
        self.assertNotIn("longenough1", account["password_hash"])

        app.checkbox[0].check()
        app = app.run()
        [b for b in app.button if b.label == "Analyze"][0].click()
        app = app.run()
        self.assertFalse(app.exception)
        self.assertIn("Resume comparison", texts(app))
        self.assertEqual(len(database.list_results(account["user_id"])), 4)

        app.sidebar.radio[0].set_value("History")
        app = app.run()
        self.assertIn("4 saved reports", texts(app))

        app.sidebar.button[0].click()              # Log out
        app = app.run()
        self.assertIn("Please log in", texts(app))
        self.assertEqual(len(app.checkbox), 0)

    def test_4_wrong_password_is_refused_and_right_one_accepted(self):
        app = self.login(self.open_app(), "asha@example.com", "wrongpassword")
        self.assertIn("not correct", texts(app))
        self.assertEqual(len(app.checkbox), 0)
        app = self.login(self.open_app(), "ASHA@example.com", "longenough1")
        self.assertIn("Asha", texts(app))
        self.assertEqual(len(app.checkbox), 1)

    def test_5_duplicate_email_and_private_history(self):
        app = self.register(self.open_app(), "Other", "asha@example.com", "anotherpass1")
        self.assertIn("already exists", texts(app))
        app = self.register(self.open_app(), "Ravi", "ravi@example.com", "anotherpass1")
        app.sidebar.radio[0].set_value("History")
        app = app.run()
        self.assertIn("no saved resume reports", texts(app))


if __name__ == "__main__":
    unittest.main()
