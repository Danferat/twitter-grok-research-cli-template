import unittest
from unittest.mock import patch

from twitter_research.grok_client import GrokClient, build_run_analysis_prompt


class GrokClientTests(unittest.TestCase):
    def test_chat_posts_openai_compatible_payload_and_returns_text(self):
        requests = []

        def fake_transport(url, payload, headers, timeout):
            requests.append(
                {
                    "url": url,
                    "payload": payload,
                    "headers": headers,
                    "timeout": timeout,
                }
            )
            return {"choices": [{"message": {"content": "Grok analysis"}}]}

        client = GrokClient(
            api_key="xai-token",
            model="grok-test-model",
            temperature=0.2,
            max_tokens=500,
            transport=fake_transport,
        )

        text = client.chat([{"role": "user", "content": "Analyze this"}])

        self.assertEqual(text, "Grok analysis")
        self.assertEqual(requests[0]["url"], "https://api.x.ai/v1/chat/completions")
        self.assertEqual(requests[0]["payload"]["model"], "grok-test-model")
        self.assertEqual(requests[0]["payload"]["temperature"], 0.2)
        self.assertEqual(requests[0]["payload"]["max_tokens"], 500)
        self.assertEqual(requests[0]["headers"]["Authorization"], "Bearer xai-token")

    def test_build_run_analysis_prompt_includes_query_and_tweets(self):
        run = {
            "query": "PUMP token",
            "api_data": {
                "data": [
                    {
                        "text": "PUMP is down because volume faded",
                        "created_at": "2026-04-29T08:00:00Z",
                        "author_id": "42",
                    }
                ],
                "includes": {"users": [{"id": "42", "username": "analyst"}]},
            },
        }

        prompt = build_run_analysis_prompt(run, max_tweets=5)

        self.assertIn("PUMP token", prompt)
        self.assertIn("@analyst", prompt)
        self.assertIn("volume faded", prompt)

    def test_search_uses_only_x_search_tool_and_never_web_search(self):
        requests = []

        def fake_transport(url, payload, headers, timeout):
            requests.append(payload)
            return {
                "output_text": "Live Grok answer",
                "citations": ["https://example.com/source"],
                "usage": {
                    "num_sources_used": 1,
                    "server_side_tool_usage_details": {
                        "web_search_calls": 0,
                        "x_search_calls": 1,
                    },
                },
            }

        client = GrokClient(
            api_key="xai-token",
            model="grok-test-model",
            transport=fake_transport,
        )

        result = client.search("что пишут про PUMP token?", max_search_results=7)

        self.assertEqual(result["answer"], "Live Grok answer")
        self.assertEqual(result["citations"], ["https://example.com/source"])
        self.assertEqual(requests[0]["tools"], [{"type": "x_search"}])
        self.assertIn("Use only x_search", requests[0]["input"][0]["content"])
        self.assertNotIn("web_search", str(requests[0]))

    def test_search_rejects_response_if_grok_used_web_search(self):
        def fake_transport(url, payload, headers, timeout):
            return {
                "output_text": "Web answer",
                "usage": {
                    "server_side_tool_usage_details": {
                        "web_search_calls": 1,
                        "x_search_calls": 0,
                    }
                },
            }

        client = GrokClient(
            api_key="xai-token",
            model="grok-test-model",
            transport=fake_transport,
        )

        with self.assertRaisesRegex(Exception, "web_search"):
            client.search("что пишут про PUMP token?")

    def test_search_rejects_response_if_grok_did_not_use_x_search(self):
        def fake_transport(url, payload, headers, timeout):
            return {
                "output_text": "Model-only answer",
                "usage": {
                    "server_side_tool_usage_details": {
                        "web_search_calls": 0,
                        "x_search_calls": 0,
                    }
                },
            }

        client = GrokClient(
            api_key="xai-token",
            model="grok-test-model",
            transport=fake_transport,
        )

        with self.assertRaisesRegex(Exception, "x_search"):
            client.search("что пишут про PUMP token?")

    def test_search_rejects_response_without_tool_usage_details(self):
        def fake_transport(url, payload, headers, timeout):
            return {
                "output_text": "Unverifiable answer",
                "usage": {"num_sources_used": 1},
            }

        client = GrokClient(
            api_key="xai-token",
            model="grok-test-model",
            transport=fake_transport,
        )

        with self.assertRaisesRegex(Exception, "x_search"):
            client.search("что пишут про PUMP token?")

    def test_chat_translates_non_json_success_response(self):
        class NonJsonResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"not-json"

        client = GrokClient(api_key="xai-token", model="grok-test-model")

        with patch("twitter_research.grok_client.urlopen", return_value=NonJsonResponse()):
            with self.assertRaisesRegex(Exception, "non-JSON"):
                client.chat([{"role": "user", "content": "Analyze this"}])


if __name__ == "__main__":
    unittest.main()
