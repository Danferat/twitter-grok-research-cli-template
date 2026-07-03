import json
import unittest
from urllib.error import HTTPError

from twitter_research.nansen_client import NansenClient, NansenError


class FakeResponse:
    def __init__(self, body: bytes | object, headers: dict[str, str] | None = None):
        if isinstance(body, bytes):
            self.body = body
        else:
            self.body = json.dumps(body).encode("utf-8")
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class NansenClientTests(unittest.TestCase):
    def test_post_json_builds_authenticated_post_request(self):
        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return FakeResponse({"data": [{"token_symbol": "ETH"}]})

        client = NansenClient(api_key="nansen-token", opener=fake_urlopen)
        result = client.post_json("token-screener", {"chains": ["ethereum"], "timeframe": "24h"})

        self.assertEqual(result["data"][0]["token_symbol"], "ETH")
        request, timeout = requests[0]
        self.assertEqual(timeout, 60)
        self.assertEqual(request.full_url, "https://api.nansen.ai/api/v1/token-screener")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Apikey"), "nansen-token")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {"chains": ["ethereum"], "timeframe": "24h"},
        )

    def test_post_json_translates_api_error_message(self):
        def fake_urlopen(request, timeout):
            raise HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                {},
                io_bytes({"error": {"message": "Invalid or missing API key"}}),
            )

        client = NansenClient(api_key="bad-token", opener=fake_urlopen)

        with self.assertRaises(NansenError) as ctx:
            client.post_json("token-screener", {"chains": ["ethereum"], "timeframe": "24h"})

        self.assertIn("Invalid or missing API key", str(ctx.exception))

    def test_agent_research_parses_sse_stream(self):
        requests = []
        stream = b"".join(
            [
                b'data: {"type":"delta","text":"Smart money "}\n\n',
                b'data: {"type":"tool_call","name":"smart_money_netflow"}\n\n',
                b'data: {"type":"delta","text":"is accumulating ETH."}\n\n',
                b'data: {"type":"finish","conversation_id":"conv_1","tool_calls":["smart_money_netflow"]}\n\n',
                b"data: [DONE]\n\n",
            ]
        )

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return FakeResponse(stream, headers={"Content-Type": "text/event-stream"})

        client = NansenClient(api_key="nansen-token", opener=fake_urlopen)
        result = client.agent_research("Which tokens are funds buying?", mode="fast")

        self.assertEqual(result["answer"], "Smart money is accumulating ETH.")
        self.assertEqual(result["conversation_id"], "conv_1")
        self.assertEqual(result["tool_calls"], ["smart_money_netflow"])
        request, _timeout = requests[0]
        self.assertEqual(request.full_url, "https://api.nansen.ai/api/v1/agent/fast")
        self.assertEqual(json.loads(request.data.decode("utf-8")), {"text": "Which tokens are funds buying?"})

    def test_agent_research_raises_stream_error_event(self):
        def fake_urlopen(request, timeout):
            return FakeResponse(b'data: {"type":"error","error":"agent timeout","status_code":500}\n\n')

        client = NansenClient(api_key="nansen-token", opener=fake_urlopen)

        with self.assertRaisesRegex(NansenError, "agent timeout"):
            client.agent_research("What happened on-chain?", mode="expert")


def io_bytes(body: object):
    import io

    return io.BytesIO(json.dumps(body).encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
