"""Tests for agents/x.py changes in this PR."""
import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock


# ── build_task — market mode ──────────────────────────────────────────────

class TestXBuildTaskMarketMode:
    def test_no_strategy_returns_error_message(self, tmp_data_dir):
        from agents.x import build_task
        with patch("agents.x.load_context", return_value=""):
            result = build_task("market", {})
        assert "ERROR" in result
        assert "marketing strategy" in result.lower()
        assert "x.com/home" in result

    def test_with_strategy_returns_market_task(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy
        from agents.x import build_task
        save_strategy(sample_strategy)
        with patch("agents.x.load_context", return_value=""):
            result = build_task("market", {})
        assert "ERROR" not in result
        assert "TWEETS" in result

    def test_force_action_passed_through(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy
        from agents.x import build_task
        save_strategy(sample_strategy)
        with patch("agents.x.load_context", return_value=""):
            result = build_task("market", {"force_action": "keyword_reply"})
        assert "Keyword Reply" in result
        assert "specifically requested" in result

    def test_image_instruction_appended_when_image_provided(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy
        from agents.x import build_task
        save_strategy(sample_strategy)
        with patch("agents.x.load_context", return_value=""):
            result = build_task("market", {"image": "/path/to/product.png"})
        assert "/path/to/product.png" in result
        assert "image" in result.lower()

    def test_no_image_instruction_when_image_empty(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy
        from agents.x import build_task
        save_strategy(sample_strategy)
        with patch("agents.x.load_context", return_value=""):
            result = build_task("market", {"image": ""})
        assert "An image for the product" not in result

    def test_x_platform_urls_in_task(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy
        from agents.x import build_task
        save_strategy(sample_strategy)
        with patch("agents.x.load_context", return_value=""):
            result = build_task("market", {})
        assert "https://x.com/home" in result

    def test_no_force_action_uses_auto_decision(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy
        from agents.x import build_task
        save_strategy(sample_strategy)
        with patch("agents.x.load_context", return_value=""):
            result = build_task("market", {"force_action": None})
        assert "decide the best action" in result

    def test_x_typing_rule_present_in_market_task(self, tmp_data_dir, sample_strategy):
        """The X platform typing bug rule should be in the market task."""
        from agents.market import save_strategy
        from agents.x import build_task
        save_strategy(sample_strategy)
        with patch("agents.x.load_context", return_value=""):
            result = build_task("market", {})
        assert "KNOWN TYPING BUG" in result


# ── handle_agent_result — market mode ────────────────────────────────────

class TestXHandleAgentResultMarketMode:
    def test_delegates_to_handle_market_result(self, tmp_data_dir):
        from agents.x import handle_agent_result
        result_text = "TWEETS: https://x.com/s/1\nACTION_TYPE: product_post\nPILLAR_USED: Product Updates\nPosted a tweet."
        result = handle_agent_result("market", result_text)
        assert result.startswith("✅")
        assert "Market action completed" in result

    def test_saves_to_x_history(self, tmp_data_dir):
        from agents.x import handle_agent_result
        handle_agent_result("market", "TWEETS: https://x.com/s/1\nACTION_TYPE: product_post\nPosted.")
        history_file = tmp_data_dir / "market_history_x.json"
        assert history_file.exists()

    def test_uses_tweets_key_in_history(self, tmp_data_dir):
        from agents.x import handle_agent_result
        handle_agent_result("market", "TWEETS: https://x.com/s/1\nACTION_TYPE: product_post\nPosted.")
        history = json.loads((tmp_data_dir / "market_history_x.json").read_text())
        assert "tweets" in history[0]

    def test_empty_result_returns_no_output_wrapped(self, tmp_data_dir):
        from agents.x import handle_agent_result
        result = handle_agent_result("market", "")
        # handle_market_result returns "No output generated", x wraps it with ✅
        assert "No output generated" in result

    def test_market_insight_saved_to_file(self, tmp_data_dir):
        from agents.x import handle_agent_result
        handle_agent_result("market", "TWEETS: url1\nACTION_TYPE: educational\nMARKET_INSIGHT: Hashtags hurt reach.\nDone.")
        insights = (tmp_data_dir / "market_insights.txt").read_text()
        assert "Hashtags hurt reach." in insights


# ── handle_agent_result — market mode no longer uses market_history.json ──

class TestXMarketHistoryFilename:
    def test_market_mode_writes_market_history_x_not_market_history(self, tmp_data_dir):
        """After refactor, market history is in market_history_x.json, not market_history.json."""
        from agents.x import handle_agent_result
        handle_agent_result("market", "TWEETS: url1\nACTION_TYPE: product_post\nDone.")
        assert (tmp_data_dir / "market_history_x.json").exists()
        assert not (tmp_data_dir / "market_history.json").exists()


class FakeXquikResponse:
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeTextResponse:
    def __init__(self, status, text):
        self.status = status
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.text.encode("utf-8")


class TestXquikBackend:
    def test_extract_tweet_id_from_url_and_raw_id(self):
        from agents.x import extract_tweet_id
        assert extract_tweet_id("https://x.com/example/status/1234567890") == "1234567890"
        assert extract_tweet_id("https://twitter.com/example/status/9876543210") == "9876543210"
        assert extract_tweet_id("1234567890") == "1234567890"
        assert extract_tweet_id("https://x.com/example") is None

    def test_xquik_backend_without_text_keeps_browser_flow(self, monkeypatch):
        from agents.x import run_agent
        monkeypatch.setenv("X_BACKEND", "xquik")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        result = asyncio.run(run_agent("post", {"text": ""}))
        assert "Set GOOGLE_API_KEY or GEMINI_API_KEY" in result
        assert "requires --text" not in result

    def test_xquik_backend_with_none_text_keeps_browser_flow(self, monkeypatch):
        from agents.x import run_agent
        monkeypatch.setenv("X_BACKEND", "xquik")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        result = asyncio.run(run_agent("post", {"text": None}))
        assert "Set GOOGLE_API_KEY or GEMINI_API_KEY" in result
        assert "requires --text" not in result

    def test_xquik_post_sends_text_payload(self, monkeypatch):
        from agents.x import run_agent
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["headers"] = dict(request.header_items())
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeXquikResponse(200, {"tweetId": "1234567890", "success": True})

        monkeypatch.setenv("X_BACKEND", "xquik")
        monkeypatch.setenv("XQUIK_API_KEY", "test-key")
        monkeypatch.setenv("XQUIK_ACCOUNT", "@example")
        monkeypatch.setenv("XQUIK_BASE_URL", "https://xquik.com/")
        monkeypatch.setattr("agents.x.urllib.request.urlopen", fake_urlopen)

        result = asyncio.run(run_agent("post", {"text": " Hello from tests"}))

        assert result == "✅ Xquik published: https://x.com/i/status/1234567890"
        assert captured["url"] == "https://xquik.com/api/v1/x/tweets"
        assert captured["timeout"] == 30
        assert captured["headers"]["X-api-key"] == "test-key"
        assert captured["payload"] == {"account": "@example", "text": "Hello from tests"}

    def test_xquik_reply_sends_reply_to_tweet_id(self, monkeypatch):
        from agents.x import run_agent
        captured = {}

        def fake_urlopen(request, timeout):
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeXquikResponse(202, {"writeActionId": "42"})

        monkeypatch.setenv("X_BACKEND", "xquik")
        monkeypatch.setenv("XQUIK_API_KEY", "test-key")
        monkeypatch.setenv("XQUIK_ACCOUNT", "@example")
        monkeypatch.setattr("agents.x.urllib.request.urlopen", fake_urlopen)

        result = asyncio.run(run_agent(
            "reply",
            {
                "text": "Thanks for sharing.",
                "url": "https://x.com/example/status/1234567890",
            },
        ))

        assert "confirmation is pending" in result
        assert "writeActionId: 42" in result
        assert captured["payload"]["reply_to_tweet_id"] == "1234567890"

    def test_xquik_non_json_success_returns_error(self, monkeypatch):
        from agents.x import run_agent

        def fake_urlopen(request, timeout):
            return FakeTextResponse(200, "<html>proxy error</html>")

        monkeypatch.setenv("X_BACKEND", "xquik")
        monkeypatch.setenv("XQUIK_API_KEY", "test-key")
        monkeypatch.setenv("XQUIK_ACCOUNT", "@example")
        monkeypatch.setattr("agents.x.urllib.request.urlopen", fake_urlopen)

        result = asyncio.run(run_agent("post", {"text": "Hello"}))

        assert result == "❌ Xquik request failed: non-JSON response"

    def test_xquik_base_url_requires_https(self, monkeypatch):
        from agents.x import run_agent

        monkeypatch.setenv("X_BACKEND", "xquik")
        monkeypatch.setenv("XQUIK_API_KEY", "test-key")
        monkeypatch.setenv("XQUIK_ACCOUNT", "@example")
        monkeypatch.setenv("XQUIK_BASE_URL", "http://xquik.test")

        result = asyncio.run(run_agent("post", {"text": "Hello"}))

        assert "XQUIK_BASE_URL must use https" in result
