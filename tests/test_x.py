"""Tests for agents/x.py changes in this PR."""
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