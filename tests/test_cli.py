import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from twitter_research.cli import main
from twitter_research.storage import save_run


class CliTests(unittest.TestCase):
    def test_show_latest_falls_back_to_raw_json_for_unknown_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            save_run(
                {
                    "query": "PUMP token",
                    "mode": "custom-mode",
                    "fetched": 1,
                },
                runs_dir=runs_dir,
                timestamp="2026-04-29T11:00:00Z",
            )

            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--runs-dir", str(runs_dir), "show", "latest"])

            self.assertEqual(code, 0)
            self.assertIn("PUMP token", out.getvalue())
            self.assertIn("custom-mode", out.getvalue())

    def test_plan_query_prints_transformed_search_command(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["plan-query", "почему PUMP токен падает последний месяц?"])

        text = out.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("PUMP token", text)
        self.assertIn("dump OR down OR bearish", text)
        self.assertIn("--days 30", text)
        self.assertIn("python3 -m twitter_research ask", text)
        self.assertIn("--provider PROVIDER", text)
        self.assertNotIn("python3 -m twitter_research search", text)

    def test_ask_requires_provider_when_noninteractive(self):
        class NonInteractiveInput(io.StringIO):
            def isatty(self):
                return False

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"

            err = io.StringIO()
            with patch("sys.stdin", NonInteractiveInput("")), redirect_stderr(err):
                code = main(
                    [
                        "--runs-dir",
                        str(runs_dir),
                        "ask",
                        "почему PUMP токен падает последний месяц?",
                    ]
                )

            self.assertEqual(code, 1)
            self.assertIn("--provider", err.getvalue())
            self.assertEqual(len(list(runs_dir.glob("*.json"))), 0)

    def test_grok_search_uses_only_grok_client_and_saves_result(self):
        class FakeGrokClient:
            def __init__(self, api_key, model):
                self.api_key = api_key
                self.model = model

            def search(self, question, max_search_results=20):
                return {
                    "answer": f"grok-only answer for {question}",
                    "citations": ["https://example.com/source"],
                    "usage": {"num_sources_used": 1},
                }

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            env_path = Path(tmp) / ".env"
            env_path.write_text("XAI_API_KEY=xai-token\n", encoding="utf-8")

            out = io.StringIO()
            with (
                patch("twitter_research.cli.GrokClient", FakeGrokClient),
                redirect_stdout(out),
            ):
                code = main(
                    [
                        "--env-file",
                        str(env_path),
                        "--runs-dir",
                        str(runs_dir),
                        "grok-search",
                        "что пишут про PUMP token?",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertIn("Grok-only search", out.getvalue())
            self.assertIn("grok-only answer", out.getvalue())
            self.assertEqual(len(list(runs_dir.glob("*.json"))), 1)

    def test_grok_search_always_uses_single_model_without_selection(self):
        created_clients = []

        class FakeGrokClient:
            def __init__(self, api_key, model):
                self.api_key = api_key
                self.model = model
                created_clients.append(self)

            def search(self, question, max_search_results=20):
                return {
                    "answer": "fixed model answer",
                    "citations": [],
                    "usage": {},
                }

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            env_path = Path(tmp) / ".env"
            env_path.write_text("XAI_API_KEY=xai-token\n", encoding="utf-8")

            out = io.StringIO()
            with patch("twitter_research.cli.GrokClient", FakeGrokClient), redirect_stdout(out):
                code = main(
                    [
                        "--env-file",
                        str(env_path),
                        "--runs-dir",
                        str(runs_dir),
                        "grok-search",
                        "что пишут про PUMP token?",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(created_clients[0].model, "grok-4.3")
            self.assertNotIn("Какую модель Grok использовать?", out.getvalue())
            saved = next(runs_dir.glob("*.json")).read_text(encoding="utf-8")
            self.assertIn('"model": "grok-4.3"', saved)

    def test_grok_search_rejects_unknown_model_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            env_path = Path(tmp) / ".env"
            env_path.write_text("XAI_API_KEY=xai-token\n", encoding="utf-8")

            err = io.StringIO()
            with redirect_stderr(err):
                with self.assertRaises(SystemExit):
                    main(
                        [
                            "--env-file",
                            str(env_path),
                            "--runs-dir",
                            str(runs_dir),
                            "grok-search",
                            "что пишут про PUMP token?",
                            "--model",
                            "grok-4-1-fast-reasoning",
                        ]
                    )

            self.assertIn("unrecognized arguments", err.getvalue())

    def test_surf_search_uses_surf_client_and_saves_result(self):
        created_clients = []

        class FakeSurfClient:
            def __init__(self, binary_path="surf"):
                self.binary_path = binary_path
                created_clients.append(self)

            def search_social_posts(self, query, limit=20):
                return {
                    "data": [
                        {
                            "tweet_id": "1",
                            "text": f"surf result for {query}",
                            "created_at": 1770000000,
                            "url": "https://x.com/source/status/1",
                            "author": {"handle": "source", "name": "Source"},
                            "stats": {"likes": 5, "reposts": 1, "replies": 0, "views": 100},
                        }
                    ],
                    "meta": {"credits_used": 3, "limit": limit, "has_more": False},
                }

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"

            out = io.StringIO()
            with (
                patch("twitter_research.cli.SurfClient", FakeSurfClient),
                patch("twitter_research.cli.GrokClient") as grok_client,
                redirect_stdout(out),
            ):
                code = main(
                    [
                        "--runs-dir",
                        str(runs_dir),
                        "surf-search",
                        "PUMP token since:2026-06-01",
                        "--limit",
                        "5",
                        "--surf-binary",
                        "/tmp/fake-surf",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(created_clients[0].binary_path, "/tmp/fake-surf")
            self.assertFalse(grok_client.called)
            self.assertIn("Surf search", out.getvalue())
            self.assertIn("@source", out.getvalue())
            saved = next(runs_dir.glob("*.json")).read_text(encoding="utf-8")
            self.assertIn('"source": "surf"', saved)
            self.assertIn('"mode": "surf-search"', saved)
            self.assertIn("surf result for PUMP token", saved)

    def test_surf_call_runs_any_surf_operation_and_saves_result(self):
        class FakeSurfClient:
            def __init__(self, binary_path=None):
                self.binary_path = binary_path

            def call_operation(self, operation, params=None, body=None):
                return {
                    "data": [{"symbol": params["symbol"], "price": 100000}],
                    "meta": {"credits_used": 1},
                }

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            out = io.StringIO()
            with patch("twitter_research.cli.SurfClient", FakeSurfClient), redirect_stdout(out):
                code = main(
                    [
                        "--runs-dir",
                        str(runs_dir),
                        "surf-call",
                        "market-price",
                        "--param",
                        "symbol=BTC",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertIn("Surf operation", out.getvalue())
            saved = next(runs_dir.glob("*.json")).read_text(encoding="utf-8")
            self.assertIn('"source": "surf"', saved)
            self.assertIn('"mode": "surf-call"', saved)
            self.assertIn('"operation": "market-price"', saved)
            self.assertIn('"symbol": "BTC"', saved)

    def test_surf_api_call_uses_surf_api_key_and_saves_result(self):
        created_clients = []

        class FakeSurfApiClient:
            def __init__(self, api_key):
                self.api_key = api_key
                created_clients.append(self)

            def request(self, method, endpoint, params=None, body=None):
                return {"data": [{"symbol": params["symbol"]}], "meta": {"credits_used": 1}}

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            env_path = Path(tmp) / ".env"
            env_path.write_text("SURF_API_KEY=surf-token\n", encoding="utf-8")
            out = io.StringIO()
            with patch("twitter_research.cli.SurfApiClient", FakeSurfApiClient), redirect_stdout(out):
                code = main(
                    [
                        "--env-file",
                        str(env_path),
                        "--runs-dir",
                        str(runs_dir),
                        "surf-api-call",
                        "market/price",
                        "--param",
                        "symbol=BTC",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(created_clients[0].api_key, "surf-token")
            self.assertIn("Surf API", out.getvalue())
            saved = next(runs_dir.glob("*.json")).read_text(encoding="utf-8")
            self.assertIn('"mode": "surf-api-call"', saved)
            self.assertIn('"endpoint": "market/price"', saved)

    def test_surf_ask_posts_to_responses_api(self):
        class FakeSurfApiClient:
            def __init__(self, api_key):
                self.api_key = api_key

            def chat_response(self, question, model="surf-2.0", effort="medium"):
                return {
                    "output_text": f"Surf answer for {question}",
                    "model": model,
                    "reasoning": {"effort": effort},
                }

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            env_path = Path(tmp) / ".env"
            env_path.write_text("SURF_API_KEY=surf-token\n", encoding="utf-8")
            out = io.StringIO()
            with patch("twitter_research.cli.SurfApiClient", FakeSurfApiClient), redirect_stdout(out):
                code = main(
                    [
                        "--env-file",
                        str(env_path),
                        "--runs-dir",
                        str(runs_dir),
                        "surf-ask",
                        "What happened to BTC today?",
                        "--effort",
                        "high",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertIn("Surf answer", out.getvalue())
            saved = next(runs_dir.glob("*.json")).read_text(encoding="utf-8")
            self.assertIn('"mode": "surf-ask"', saved)
            self.assertIn('"model": "surf-2.0"', saved)

    def test_socialdata_search_uses_socialdata_client_and_saves_result(self):
        created_clients = []

        class FakeSocialDataClient:
            def __init__(self, api_key):
                self.api_key = api_key
                created_clients.append(self)

            def search(self, query, search_type="Latest"):
                return {
                    "next_cursor": "cursor-1",
                    "tweets": [
                        {
                            "id_str": "1",
                            "full_text": f"socialdata result for {query}",
                            "tweet_created_at": "2026-06-09T10:00:00.000000Z",
                            "user": {"screen_name": "source", "name": "Source"},
                            "favorite_count": 7,
                            "retweet_count": 2,
                            "reply_count": 1,
                            "views_count": 300,
                        }
                    ],
                }

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            env_path = Path(tmp) / ".env"
            env_path.write_text("SOCIALDATA_API_KEY=sd-token\n", encoding="utf-8")

            out = io.StringIO()
            with (
                patch("twitter_research.cli.SocialDataClient", FakeSocialDataClient),
                patch("twitter_research.cli.GrokClient") as grok_client,
                redirect_stdout(out),
            ):
                code = main(
                    [
                        "--env-file",
                        str(env_path),
                        "--runs-dir",
                        str(runs_dir),
                        "socialdata-search",
                        "PUMP token since_time:1770000000",
                        "--type",
                        "Top",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(created_clients[0].api_key, "sd-token")
            self.assertFalse(grok_client.called)
            self.assertIn("SocialData search", out.getvalue())
            self.assertIn("@source", out.getvalue())
            saved = next(runs_dir.glob("*.json")).read_text(encoding="utf-8")
            self.assertIn('"source": "socialdata"', saved)
            self.assertIn('"mode": "socialdata-search"', saved)
            self.assertIn('"search_type": "Top"', saved)
            self.assertIn("socialdata result for PUMP token", saved)

    def test_ask_with_socialdata_provider_runs_socialdata_pipeline(self):
        class FakeSocialDataClient:
            def __init__(self, api_key):
                self.api_key = api_key

            def search(self, query, search_type="Latest"):
                return {
                    "tweets": [
                        {
                            "id_str": "1",
                            "full_text": f"socialdata answer for {query}",
                            "tweet_created_at": "2026-06-09T10:00:00.000000Z",
                            "user": {"screen_name": "source"},
                            "favorite_count": 1,
                            "retweet_count": 0,
                            "reply_count": 0,
                            "views_count": 10,
                        }
                    ]
                }

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            env_path = Path(tmp) / ".env"
            env_path.write_text("SOCIALDATA_API_KEY=sd-token\n", encoding="utf-8")

            out = io.StringIO()
            with (
                patch("twitter_research.cli.SocialDataClient", FakeSocialDataClient),
                patch("twitter_research.cli.GrokClient") as grok_client,
                redirect_stdout(out),
            ):
                code = main(
                    [
                        "--env-file",
                        str(env_path),
                        "--runs-dir",
                        str(runs_dir),
                        "ask",
                        "что пишут про PUMP token?",
                        "--provider",
                        "socialdata",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertFalse(grok_client.called)
            self.assertIn("SocialData search", out.getvalue())
            saved = next(runs_dir.glob("*.json")).read_text(encoding="utf-8")
            self.assertIn('"source": "socialdata"', saved)

    def test_ask_prompts_for_provider_when_interactive(self):
        class InteractiveInput(io.StringIO):
            def isatty(self):
                return True

        class FakeSurfClient:
            def __init__(self, binary_path="surf"):
                self.binary_path = binary_path

            def search_social_posts(self, query, limit=20):
                return {
                    "data": [
                        {
                            "tweet_id": "1",
                            "text": "surf interactive provider result",
                            "created_at": 1770000000,
                            "url": "https://x.com/source/status/1",
                            "author": {"handle": "source"},
                            "stats": {"likes": 1, "reposts": 0, "replies": 0, "views": 10},
                        }
                    ],
                    "meta": {},
                }

        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"

            out = io.StringIO()
            with (
                patch("twitter_research.cli.SurfClient", FakeSurfClient),
                patch("sys.stdin", InteractiveInput("2\n")),
                redirect_stdout(out),
            ):
                code = main(
                    [
                        "--runs-dir",
                        str(runs_dir),
                        "ask",
                        "что пишут про PUMP token?",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertIn("Какого провайдера поиска использовать?", out.getvalue())
            self.assertIn("Surf search", out.getvalue())
            saved = next(runs_dir.glob("*.json")).read_text(encoding="utf-8")
            self.assertIn('"source": "surf"', saved)

    def test_show_latest_prints_saved_surf_posts(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            save_run(
                {
                    "query": "PUMP token",
                    "source": "surf",
                    "mode": "surf-search",
                    "requested_limit": 1,
                    "fetched": 1,
                    "surf_data": {
                        "data": [
                            {
                                "tweet_id": "1",
                                "text": "Surf found a post about PUMP liquidity",
                                "created_at": 1770000000,
                                "url": "https://x.com/source/status/1",
                                "author": {"handle": "source"},
                                "stats": {"likes": 5, "reposts": 1, "replies": 0, "views": 100},
                            }
                        ],
                        "meta": {"credits_used": 3},
                    },
                },
                runs_dir=runs_dir,
                timestamp="2026-06-09T11:00:00Z",
            )

            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--runs-dir", str(runs_dir), "show", "latest"])

            self.assertEqual(code, 0)
            self.assertIn("PUMP token", out.getvalue())
            self.assertIn("Surf found a post", out.getvalue())
            self.assertIn("@source", out.getvalue())

    def test_show_latest_prints_saved_socialdata_posts(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            save_run(
                {
                    "query": "PUMP token",
                    "source": "socialdata",
                    "mode": "socialdata-search",
                    "fetched": 1,
                    "socialdata_data": {
                        "tweets": [
                            {
                                "id_str": "1",
                                "full_text": "SocialData found a post about PUMP liquidity",
                                "tweet_created_at": "2026-06-09T10:00:00.000000Z",
                                "user": {"screen_name": "source"},
                                "favorite_count": 5,
                                "retweet_count": 1,
                                "reply_count": 0,
                                "views_count": 100,
                            }
                        ]
                    },
                },
                runs_dir=runs_dir,
                timestamp="2026-06-09T11:00:00Z",
            )

            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--runs-dir", str(runs_dir), "show", "latest"])

            self.assertEqual(code, 0)
            self.assertIn("PUMP token", out.getvalue())
            self.assertIn("SocialData found a post", out.getvalue())
            self.assertIn("@source", out.getvalue())

    def test_content_filter_marks_close_summary_as_irrelevant_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            index_path = Path(tmp) / "content_research_index.md"
            index_path.write_text(
                "| Дата добавления | Тема | Категория | Краткое содержание | Ссылка на источник | Файл с заметкой | Статус |\n"
                "| --------------- | ---- | --------- | ------------------ | ------------------ | --------------- | ------ |\n"
                "| 30/05/26 | Гигиена криптокошелька | Безопасность | Практические привычки для защиты кошелька: разделение кошельков, осторожность с подписями, offline-хранение seed phrase и проверка approvals. | https://x.com/source/status/1 | content_research/wallet.md | accepted |\n",
                encoding="utf-8",
            )

            out = io.StringIO()
            with redirect_stdout(out):
                code = main(
                    [
                        "content-filter",
                        "--index-file",
                        str(index_path),
                        "--summary",
                        "Практические привычки для защиты криптокошелька: разделение кошельков, "
                        "осторожность с подписями, хранение seed phrase офлайн и проверка approvals.",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertIn("Status: irrelevant_duplicate", out.getvalue())
            self.assertIn("Гигиена криптокошелька", out.getvalue())

if __name__ == "__main__":
    unittest.main()
