import json
import unittest
from urllib.error import HTTPError

from twitter_research.socialdata_client import SocialDataClient, SocialDataError


class FakeResponse:
    def __init__(self, body: object):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class SocialDataClientTests(unittest.TestCase):
    def test_search_builds_authorized_latest_request(self):
        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return FakeResponse({"tweets": [{"id_str": "1", "full_text": "hello"}]})

        client = SocialDataClient(api_key="sd-token", opener=fake_urlopen)
        result = client.search("from:elonmusk doge", search_type="Latest")

        self.assertEqual(result["tweets"][0]["full_text"], "hello")
        request, timeout = requests[0]
        self.assertEqual(timeout, 30)
        self.assertIn("query=from%3Aelonmusk+doge", request.full_url)
        self.assertIn("type=Latest", request.full_url)
        self.assertEqual(request.headers["Authorization"], "Bearer sd-token")
        self.assertEqual(request.headers["Accept"], "application/json")

    def test_search_translates_payment_error(self):
        def fake_urlopen(request, timeout):
            raise HTTPError(
                request.full_url,
                402,
                "Payment Required",
                {},
                io_bytes({"status": "error", "message": "Insufficient balance"}),
            )

        client = SocialDataClient(api_key="sd-token", opener=fake_urlopen)

        with self.assertRaises(SocialDataError) as ctx:
            client.search("bitcoin")

        self.assertIn("Insufficient balance", str(ctx.exception))

    def test_search_translates_non_object_http_error(self):
        def fake_urlopen(request, timeout):
            raise HTTPError(
                request.full_url,
                500,
                "Server Error",
                {},
                io_bytes(["not", "an", "object"]),
            )

        client = SocialDataClient(api_key="sd-token", opener=fake_urlopen)

        with self.assertRaises(SocialDataError) as ctx:
            client.search("bitcoin")

        self.assertIn("HTTP 500", str(ctx.exception))

    def test_search_rejects_non_object_json_response(self):
        def fake_urlopen(request, timeout):
            return FakeResponse(["not", "an", "object"])

        client = SocialDataClient(api_key="sd-token", opener=fake_urlopen)

        with self.assertRaisesRegex(SocialDataError, "JSON object"):
            client.search("bitcoin")

    def test_search_rejects_response_with_non_list_tweets(self):
        def fake_urlopen(request, timeout):
            return FakeResponse({"tweets": {"id_str": "1"}})

        client = SocialDataClient(api_key="sd-token", opener=fake_urlopen)

        with self.assertRaisesRegex(SocialDataError, "tweets"):
            client.search("bitcoin")


def io_bytes(body: object):
    import io

    return io.BytesIO(json.dumps(body).encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
