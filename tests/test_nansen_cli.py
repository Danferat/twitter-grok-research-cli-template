import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from twitter_research.cli import main
from twitter_research.storage import save_run


class NansenCliTests(unittest.TestCase):
    def test_nansen_ask_wraps_question_for_chat_and_saves_readable_answer(self):
        calls = []

        class FakeNansenClient:
            def __init__(self, api_key):
                self.api_key = api_key

            def agent_research(self, question, mode="fast", conversation_id=None):
                calls.append((question, mode, conversation_id))
                return {
                    "answer": (
                        "Короткий вывод: smart money накапливает ETH.\n\n"
                        "Что видно в данных:\n- netflow ETH положительный\n\n"
                        "Что проверить дальше:\n- повторить через 24 часа"
                    ),
                    "conversation_id": "conv_chat",
                    "tool_calls": ["smart_money_netflow", "token_screener"],
                    "events": [{"type": "finish", "conversation_id": "conv_chat"}],
                }

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            env_path = Path(tmp) / ".env"
            env_path.write_text("NANSEN_API_KEY=nansen-token\n", encoding="utf-8")

            out = io.StringIO()
            with (
                patch("twitter_research.cli.NansenClient", FakeNansenClient),
                patch("twitter_research.cli.GrokClient") as grok_client,
                patch("twitter_research.cli.SurfClient") as surf_client,
                patch("twitter_research.cli.SocialDataClient") as socialdata_client,
                redirect_stdout(out),
            ):
                code = main(
                    [
                        "--env-file",
                        str(env_path),
                        "--runs-dir",
                        str(runs_dir),
                        "nansen-ask",
                        "какие токены сейчас накапливает smart money на Ethereum?",
                    ]
                )

            self.assertEqual(code, 0)
            prompt, mode, conversation_id = calls[0]
            self.assertEqual(mode, "fast")
            self.assertIsNone(conversation_id)
            self.assertIn("какие токены сейчас накапливает smart money", prompt)
            self.assertIn("Ответь на русском", prompt)
            self.assertIn("Короткий вывод", prompt)
            self.assertFalse(grok_client.called)
            self.assertFalse(surf_client.called)
            self.assertFalse(socialdata_client.called)
            self.assertIn("Nansen on-chain answer", out.getvalue())
            self.assertIn("smart money накапливает ETH", out.getvalue())
            saved = json.loads(next(runs_dir.glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(saved["mode"], "nansen-ask")
            self.assertEqual(saved["nansen_mode"], "fast")
            self.assertEqual(saved["query"], "какие токены сейчас накапливает smart money на Ethereum?")
            self.assertIn("Ответь на русском", saved["nansen_prompt"])

    def test_nansen_ask_auto_mode_uses_expert_for_deep_research(self):
        calls = []

        class FakeNansenClient:
            def __init__(self, api_key):
                self.api_key = api_key

            def agent_research(self, question, mode="fast", conversation_id=None):
                calls.append((question, mode, conversation_id))
                return {
                    "answer": "Глубокий разбор готов.",
                    "conversation_id": "conv_deep",
                    "tool_calls": [],
                    "events": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            env_path = Path(tmp) / ".env"
            env_path.write_text("NANSEN_API_KEY=nansen-token\n", encoding="utf-8")

            with patch("twitter_research.cli.NansenClient", FakeNansenClient), redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--env-file",
                        str(env_path),
                        "--runs-dir",
                        str(runs_dir),
                        "nansen-ask",
                        "сделай глубокий разбор ончейн причин притока в SOL за неделю",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(calls[0][1], "expert")

    def test_nansen_agent_uses_nansen_client_and_saves_result(self):
        created_clients = []

        class FakeNansenClient:
            def __init__(self, api_key):
                self.api_key = api_key
                created_clients.append(self)

            def agent_research(self, question, mode="fast", conversation_id=None):
                return {
                    "answer": f"Nansen answer for {question}",
                    "conversation_id": "conv_1",
                    "tool_calls": ["smart_money_netflow"],
                    "events": [{"type": "finish", "conversation_id": "conv_1"}],
                }

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            env_path = Path(tmp) / ".env"
            env_path.write_text("NANSEN_API_KEY=nansen-token\n", encoding="utf-8")

            out = io.StringIO()
            with (
                patch("twitter_research.cli.NansenClient", FakeNansenClient),
                patch("twitter_research.cli.GrokClient") as grok_client,
                redirect_stdout(out),
            ):
                code = main(
                    [
                        "--env-file",
                        str(env_path),
                        "--runs-dir",
                        str(runs_dir),
                        "nansen-agent",
                        "Which tokens are smart money accumulating on Ethereum?",
                        "--mode",
                        "fast",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(created_clients[0].api_key, "nansen-token")
            self.assertFalse(grok_client.called)
            self.assertIn("Nansen agent", out.getvalue())
            self.assertIn("Nansen answer", out.getvalue())
            saved = json.loads(next(runs_dir.glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(saved["source"], "nansen")
            self.assertEqual(saved["mode"], "nansen-agent")
            self.assertEqual(saved["nansen_mode"], "fast")
            self.assertEqual(saved["conversation_id"], "conv_1")

    def test_nansen_token_screener_builds_body_and_prints_rows(self):
        requests = []

        class FakeNansenClient:
            def __init__(self, api_key):
                self.api_key = api_key

            def post_json(self, endpoint, body):
                requests.append((endpoint, body))
                return {
                    "data": [
                        {
                            "chain": "ethereum",
                            "token_symbol": "ETH",
                            "price_usd": 3500,
                            "price_change": 3.2,
                            "volume": 1000000,
                            "netflow": 250000,
                        }
                    ],
                    "pagination": {"page": 1, "per_page": 5, "is_last_page": True},
                }

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            env_path = Path(tmp) / ".env"
            env_path.write_text("NANSEN_API_KEY=nansen-token\n", encoding="utf-8")

            out = io.StringIO()
            with patch("twitter_research.cli.NansenClient", FakeNansenClient), redirect_stdout(out):
                code = main(
                    [
                        "--env-file",
                        str(env_path),
                        "--runs-dir",
                        str(runs_dir),
                        "nansen-token-screener",
                        "--chains",
                        "ethereum,solana",
                        "--timeframe",
                        "24h",
                        "--per-page",
                        "5",
                        "--only-smart-money",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(requests[0][0], "token-screener")
            self.assertEqual(
                requests[0][1],
                {
                    "chains": ["ethereum", "solana"],
                    "timeframe": "24h",
                    "pagination": {"page": 1, "per_page": 5},
                    "filters": {"only_smart_money": True},
                },
            )
            self.assertIn("ETH", out.getvalue())
            saved = json.loads(next(runs_dir.glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(saved["mode"], "nansen-token-screener")
            self.assertEqual(saved["endpoint"], "token-screener")

    def test_nansen_call_accepts_arbitrary_endpoint_and_json_body(self):
        calls = []

        class FakeNansenClient:
            def __init__(self, api_key):
                self.api_key = api_key

            def post_json(self, endpoint, body):
                calls.append((endpoint, body))
                return {"data": [{"token_symbol": "SOL", "net_flow_24h_usd": 42}]}

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            env_path = Path(tmp) / ".env"
            env_path.write_text("NANSEN_API_KEY=nansen-token\n", encoding="utf-8")

            out = io.StringIO()
            with patch("twitter_research.cli.NansenClient", FakeNansenClient), redirect_stdout(out):
                code = main(
                    [
                        "--env-file",
                        str(env_path),
                        "--runs-dir",
                        str(runs_dir),
                        "nansen-call",
                        "smart-money/netflow",
                        "--body-json",
                        '{"chains":["solana"],"pagination":{"per_page":1}}',
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(calls[0], ("smart-money/netflow", {"chains": ["solana"], "pagination": {"per_page": 1}}))
            self.assertIn("SOL", out.getvalue())
            saved = json.loads(next(runs_dir.glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(saved["mode"], "nansen-call")

    def test_nansen_commands_require_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            env_path = Path(tmp) / ".env"
            env_path.write_text("", encoding="utf-8")

            err = io.StringIO()
            with redirect_stderr(err):
                code = main(
                    [
                        "--env-file",
                        str(env_path),
                        "--runs-dir",
                        str(runs_dir),
                        "nansen-agent",
                        "Which wallets bought ETH?",
                    ]
                )

            self.assertEqual(code, 1)
            self.assertIn("NANSEN_API_KEY", err.getvalue())
            self.assertEqual(len(list(runs_dir.glob("*.json"))), 0)

    def test_show_latest_prints_saved_nansen_agent_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            save_run(
                {
                    "query": "Which tokens are whales accumulating?",
                    "source": "nansen",
                    "mode": "nansen-agent",
                    "nansen_mode": "expert",
                    "answer": "Whales are accumulating ETH and SOL.",
                    "conversation_id": "conv_2",
                    "tool_calls": ["token_screener"],
                },
                runs_dir=runs_dir,
                timestamp="2026-06-18T11:00:00Z",
            )

            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--runs-dir", str(runs_dir), "show", "latest"])

            self.assertEqual(code, 0)
            self.assertIn("Whales are accumulating ETH", out.getvalue())
            self.assertIn("token_screener", out.getvalue())


if __name__ == "__main__":
    unittest.main()
