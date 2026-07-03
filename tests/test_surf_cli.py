import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from twitter_research.cli import main


class SurfCliTests(unittest.TestCase):
    def test_surf_ask_wraps_question_for_agent_research_and_saves_prompt(self):
        calls = []

        class FakeSurfApiClient:
            def __init__(self, api_key):
                self.api_key = api_key

            def chat_response(self, question, model="surf-2.0", effort="medium"):
                calls.append((question, model, effort))
                return {"output_text": "Короткий вывод: кошелек активно покупал ETH на DEX."}

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            env_path = Path(tmp) / ".env"
            env_path.write_text("SURF_API_KEY=surf-token\n", encoding="utf-8")

            out = io.StringIO()
            with (
                patch("twitter_research.cli.SurfApiClient", FakeSurfApiClient),
                patch("twitter_research.cli.GrokClient") as grok_client,
                patch("twitter_research.cli.NansenClient") as nansen_client,
                patch("twitter_research.cli.SocialDataClient") as socialdata_client,
                redirect_stdout(out),
            ):
                code = main(
                    [
                        "--env-file",
                        str(env_path),
                        "--runs-dir",
                        str(runs_dir),
                        "surf-ask",
                        "проверь кошелек 0xabc: что он покупал за последние 7 дней?",
                    ]
                )

            self.assertEqual(code, 0)
            prompt, model, effort = calls[0]
            self.assertEqual(model, "surf-2.0")
            self.assertEqual(effort, "medium")
            self.assertIn("проверь кошелек 0xabc", prompt)
            self.assertIn("Ответь на русском", prompt)
            self.assertIn("Короткий вывод", prompt)
            self.assertIn("on-chain", prompt)
            self.assertFalse(grok_client.called)
            self.assertFalse(nansen_client.called)
            self.assertFalse(socialdata_client.called)
            self.assertIn("Surf/AskSurfAI answer", out.getvalue())
            self.assertIn("кошелек активно покупал ETH", out.getvalue())
            saved = json.loads(next(runs_dir.glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(saved["mode"], "surf-ask")
            self.assertEqual(saved["query"], "проверь кошелек 0xabc: что он покупал за последние 7 дней?")
            self.assertEqual(saved["effort"], "medium")
            self.assertIn("Ответь на русском", saved["surf_prompt"])

    def test_surf_ask_auto_effort_uses_high_for_deep_research(self):
        calls = []

        class FakeSurfApiClient:
            def __init__(self, api_key):
                self.api_key = api_key

            def chat_response(self, question, model="surf-2.0", effort="medium"):
                calls.append((question, model, effort))
                return {"output_text": "Глубокий Surf-разбор готов."}

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            env_path = Path(tmp) / ".env"
            env_path.write_text("SURF_API_KEY=surf-token\n", encoding="utf-8")

            with patch("twitter_research.cli.SurfApiClient", FakeSurfApiClient), redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--env-file",
                        str(env_path),
                        "--runs-dir",
                        str(runs_dir),
                        "surf-ask",
                        "сделай глубокий разбор ончейн причин притока в SOL за неделю",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(calls[0][2], "high")


if __name__ == "__main__":
    unittest.main()
