"""UI regression checks; Gemini is mocked and no external API is called."""

import os
import unittest
from unittest.mock import MagicMock, patch

from streamlit.testing.v1 import AppTest


class AppTests(unittest.TestCase):
    def test_generation_rejection_and_checklist_reset(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            app = AppTest.from_file("app.py", default_timeout=40).run()
            self.assertFalse(app.exception)
            next(c for c in app.checkbox if c.label.startswith("Step 1:")).check().run()
            app.text_area[0].input("4 switches in a ring with 8 PCs")
            next(b for b in app.button if b.label == "🚀 Generate Lab").click().run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertEqual(len(app.session_state.current_lab["links"]), 12)
            self.assertEqual(app.session_state.current_lab["generation"]["source"], "offline")
            self.assertTrue(any("Offline engine" in c.value for c in app.caption))
            self.assertFalse(next(c for c in app.checkbox if c.label.startswith("Step 1:")).value)
            previous = app.session_state.current_lab
            app.text_area[0].input("3 routers with 3 switches and 6 PCs")
            next(b for b in app.button if b.label == "🚀 Generate Lab").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            self.assertEqual(app.session_state.current_lab, previous)

    def test_fallback_warning_survives_rerun(self):
        client = MagicMock()
        client.models.generate_content.side_effect = RuntimeError("simulated outage")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-placeholder", "GEMINI_MODEL": "test-model"}), patch("google.genai.Client", return_value=client):
            app = AppTest.from_file("app.py", default_timeout=40).run()
            app.text_area[0].input("4 PCs on 1 switch")
            next(b for b in app.button if b.label == "🚀 Generate Lab").click().run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertTrue(any("Gemini request failed" in w.value for w in app.warning))
            self.assertEqual(app.session_state.current_lab["generation"]["source"], "offline")
            next(c for c in app.checkbox if c.label.startswith("Step 1:")).check().run()
            self.assertTrue(any("Gemini request failed" in w.value for w in app.warning))
            self.assertEqual(client.models.generate_content.call_count, 1)


if __name__ == "__main__":
    unittest.main()
