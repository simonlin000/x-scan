import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "xscan.py"
spec = importlib.util.spec_from_file_location("xscan", SCRIPT)
xscan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xscan)


class FakeSession:
    def __init__(self):
        self.navigated = None
        self.closed = False
        self.calls = 0

    def navigate(self, url, wait=6):
        self.navigated = url

    def wait_for_tweets(self, max_wait=15):
        return 1

    def evaluate(self, expression, timeout=20):
        if expression == "window.location.href":
            return "https://x.com/search?q=Claude&src=typed_query&f=live"
        if "querySelectorAll('article[data-testid=\\\"tweet\\\"]').length" in expression:
            return 1
        self.calls += 1
        return json.dumps([{
            "handle": "example",
            "displayName": "Example",
            "text": "AI update",
            "quotedText": "",
            "tweetUrl": "https://x.com/example/status/123/photo/1",
            "stats": {"views": "10"},
            "media": [],
            "time": "2026-07-27T10:00:00.000Z",
        }])

    def close(self):
        self.closed = True


class XScanTests(unittest.TestCase):
    def test_latest_search_uses_live_filter(self):
        url = xscan.search_url("Claude Code", latest=True)
        self.assertIn("f=live", url)
        self.assertNotIn("f=latest", url)

    def test_tweet_id_dedupes_photo_suffix(self):
        self.assertEqual(
            xscan.tweet_id("https://x.com/a/status/123/photo/1"),
            "123",
        )
        self.assertEqual(
            xscan.post_key({"tweetUrl": "https://x.com/a/status/123"}),
            xscan.post_key({"tweetUrl": "https://x.com/a/status/123/photo/1"}),
        )

    def test_scan_uses_live_search_and_validates_rounds(self):
        session = FakeSession()
        posts = xscan.scan(session, "search", query="Claude", latest=True, rounds=1)
        self.assertEqual(len(posts), 1)
        self.assertIn("f=live", session.navigated)
        with self.assertRaises(ValueError):
            xscan.scan(session, "search", query="Claude", rounds=0)

    def test_save_results_quotes_yaml_and_filters_media(self):
        post = {
            "handle": "example",
            "displayName": "A\nName",
            "time": "2026-07-27T10:00:00.000Z",
            "text": "# heading\nnormal",
            "quotedText": "quoted",
            "stats": {"views": "10"},
            "media": [
                "https://pbs.twimg.com/media/a.jpg",
                "https://evil.example/media.jpg",
            ],
            "tweetUrl": "https://x.com/example/status/123",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = xscan.save_results([post], "summary", "search", 'a"b', tmp)
            content = path.read_text(encoding="utf-8")
            self.assertIn('query: "a\\\"b"', content)
            self.assertIn("\\# heading", content)
            self.assertIn("https://pbs.twimg.com/media/a.jpg", content)
            self.assertNotIn("evil.example", content)


if __name__ == "__main__":
    unittest.main()
