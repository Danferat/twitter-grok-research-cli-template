import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

from twitter_research.surf_client import SurfApiClient, SurfClient, SurfError


class CompletedProcess:
    def __init__(self, stdout: str, stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class SurfClientTests(unittest.TestCase):
    def test_search_rejects_non_object_json_response(self):
        completed = CompletedProcess(json.dumps(["not", "an", "object"]))

        with patch("twitter_research.surf_client.subprocess.run", return_value=completed):
            client = SurfClient(binary_path="/tmp/surf")

            with self.assertRaisesRegex(SurfError, "JSON object"):
                client.search_social_posts("PUMP token")

    def test_search_rejects_response_with_non_list_data(self):
        completed = CompletedProcess(json.dumps({"data": {"tweet_id": "1"}}))

        with patch("twitter_research.surf_client.subprocess.run", return_value=completed):
            client = SurfClient(binary_path="/tmp/surf")

            with self.assertRaisesRegex(SurfError, "data"):
                client.search_social_posts("PUMP token")

    def test_search_translates_string_error_payload(self):
        completed = CompletedProcess(json.dumps({"error": "bad request"}), returncode=1)

        with patch("twitter_research.surf_client.subprocess.run", return_value=completed):
            client = SurfClient(binary_path="/tmp/surf")

            with self.assertRaisesRegex(SurfError, "bad request"):
                client.search_social_posts("PUMP token")

    def test_call_operation_builds_flags_and_body_for_any_surf_operation(self):
        completed = CompletedProcess(json.dumps({"data": [{"ok": True}], "meta": {"credits_used": 1}}))

        with patch("twitter_research.surf_client.subprocess.run", return_value=completed) as run:
            client = SurfClient(binary_path="/tmp/surf")
            result = client.call_operation(
                "onchain-sql",
                params={"limit": 10, "include": ["labels", "metadata"], "debug": False},
                body={"sql": "SELECT 1"},
            )

        self.assertEqual(result["data"][0]["ok"], True)
        args, kwargs = run.call_args
        self.assertEqual(
            args[0],
            [
                "/tmp/surf",
                "onchain-sql",
                "--limit",
                "10",
                "--include",
                "labels,metadata",
                "--json",
            ],
        )
        self.assertEqual(kwargs["input"], '{"sql": "SELECT 1"}')

    def test_list_operations_returns_text_catalog(self):
        completed = CompletedProcess("GET    market-price    Token Price History")

        with patch("twitter_research.surf_client.subprocess.run", return_value=completed):
            client = SurfClient(binary_path="/tmp/surf")
            result = client.list_operations(category="market")

        self.assertIn("market-price", result["text"])

    def test_api_client_get_adds_bearer_header_and_query_params(self):
        requests = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"data":[{"symbol":"BTC"}],"meta":{"credits_used":1}}'

        def fake_opener(request: Request, timeout: int = 60):
            requests.append(request)
            return Response()

        client = SurfApiClient(api_key="surf-token", opener=fake_opener)
        result = client.request("GET", "market/price", params={"symbol": "BTC", "time_range": "24h"})

        self.assertEqual(result["data"][0]["symbol"], "BTC")
        self.assertEqual(
            requests[0].full_url,
            "https://api.asksurf.ai/gateway/v1/market/price?symbol=BTC&time_range=24h",
        )
        self.assertEqual(requests[0].headers["Authorization"], "Bearer surf-token")

    def test_api_client_accepts_gateway_prefixed_endpoint(self):
        requests = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"data":[],"meta":{"credits_used":1}}'

        def fake_opener(request: Request, timeout: int = 60):
            requests.append(request)
            return Response()

        client = SurfApiClient(api_key="surf-token", opener=fake_opener)
        client.request("GET", "/gateway/v1/market/price")

        self.assertEqual(requests[0].full_url, "https://api.asksurf.ai/gateway/v1/market/price")

    def test_api_client_translates_error_payload(self):
        class ErrorResponse:
            def read(self):
                return b'{"error":{"message":"invalid API key"}}'

            def close(self):
                return None

        def fake_opener(request: Request, timeout: int = 60):
            raise HTTPError(request.full_url, 401, "Unauthorized", {}, ErrorResponse())

        client = SurfApiClient(api_key="bad-token", opener=fake_opener)

        with self.assertRaisesRegex(SurfError, "invalid API key"):
            client.request("GET", "market/price")


if __name__ == "__main__":
    unittest.main()
