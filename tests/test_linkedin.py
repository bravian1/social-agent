"""Tests for agents/linkedin.py changes in this PR."""
import json
import pytest
from unittest.mock import patch, MagicMock


# ── _build_user_profile_from_scan ────────────────────────────────────────

class TestBuildUserProfileFromScan:
    def test_extracts_name(self):
        from agents.linkedin import _build_user_profile_from_scan
        raw = "Name: Jane Doe\nHeadline: Senior Engineer\nHandle: janedoe\nAbout: Not provided"
        result = _build_user_profile_from_scan(raw)
        assert "Jane Doe" in result

    def test_extracts_headline_as_career(self):
        from agents.linkedin import _build_user_profile_from_scan
        raw = "Name: Jane Doe\nHeadline: Machine Learning Engineer\nHandle: janedoe\nAbout: Not provided"
        result = _build_user_profile_from_scan(raw)
        assert "Machine Learning Engineer" in result

    def test_extracts_handle(self):
        from agents.linkedin import _build_user_profile_from_scan
        raw = "Name: Jane Doe\nHeadline: Engineer\nHandle: janedoe123\nAbout: Not provided"
        result = _build_user_profile_from_scan(raw)
        assert "janedoe123" in result

    def test_includes_about_when_present(self):
        from agents.linkedin import _build_user_profile_from_scan
        raw = "Name: Jane\nHeadline: Engineer\nHandle: jane\nAbout: I build ML systems for fun."
        result = _build_user_profile_from_scan(raw)
        assert "I build ML systems for fun." in result

    def test_omits_about_when_not_provided(self):
        from agents.linkedin import _build_user_profile_from_scan
        raw = "Name: Jane\nHeadline: Engineer\nHandle: jane\nAbout: Not provided"
        result = _build_user_profile_from_scan(raw)
        assert "Not provided" not in result

    def test_defaults_career_to_professional_when_no_headline(self):
        from agents.linkedin import _build_user_profile_from_scan
        raw = "Name: Jane\nHandle: jane\nAbout: Not provided"
        result = _build_user_profile_from_scan(raw)
        assert "Professional" in result

    def test_includes_post_previews(self):
        from agents.linkedin import _build_user_profile_from_scan
        raw = (
            "Name: Jane\nHeadline: Engineer\nHandle: jane\nAbout: Not provided\n"
            "Recent posts (preview snippets):\n"
            "  - Just shipped a new feature for edge inference.\n"
            "  - Thoughts on the future of on-device ML.\n"
        )
        result = _build_user_profile_from_scan(raw)
        assert "Just shipped a new feature for edge inference." in result
        assert "Thoughts on the future of on-device ML." in result

    def test_excludes_no_recent_posts_placeholder(self):
        from agents.linkedin import _build_user_profile_from_scan
        raw = (
            "Name: Jane\nHeadline: Engineer\nHandle: jane\nAbout: Not provided\n"
            "Recent posts (preview snippets):\n"
            "  - No recent posts\n"
        )
        result = _build_user_profile_from_scan(raw)
        assert "No recent posts" not in result

    def test_post_previews_truncated_to_150_chars(self):
        from agents.linkedin import _build_user_profile_from_scan
        long_preview = "A" * 200
        raw = (
            f"Name: Jane\nHeadline: Engineer\nHandle: jane\nAbout: Not provided\n"
            f"Recent posts (preview snippets):\n"
            f"  - {long_preview}\n"
        )
        result = _build_user_profile_from_scan(raw)
        # The preview should appear but only up to 150 chars
        assert "A" * 150 in result
        assert "A" * 151 not in result

    def test_max_four_post_previews(self):
        from agents.linkedin import _build_user_profile_from_scan
        raw = (
            "Name: Jane\nHeadline: Engineer\nHandle: jane\nAbout: Not provided\n"
            "Recent posts (preview snippets):\n"
            "  - Post one preview.\n"
            "  - Post two preview.\n"
            "  - Post three preview.\n"
            "  - Post four preview.\n"
            "  - Post five preview.\n"
        )
        result = _build_user_profile_from_scan(raw)
        assert "Post four preview." in result
        assert "Post five preview." not in result

    def test_includes_anti_ai_style_rules(self):
        from agents.linkedin import _build_user_profile_from_scan
        raw = "Name: Jane\nHeadline: Engineer\nHandle: jane\nAbout: Not provided"
        result = _build_user_profile_from_scan(raw)
        assert "AI giveaway patterns" in result or "NEVER use" in result

    def test_includes_tone_instructions(self):
        from agents.linkedin import _build_user_profile_from_scan
        raw = "Name: Jane\nHeadline: Engineer\nHandle: jane\nAbout: Not provided"
        result = _build_user_profile_from_scan(raw)
        assert "conversational" in result or "Default tone" in result

    def test_empty_raw_scan_returns_valid_string(self):
        from agents.linkedin import _build_user_profile_from_scan
        result = _build_user_profile_from_scan("")
        # Should not raise; returns a string with defaults
        assert isinstance(result, str)
        assert "Professional" in result  # default career

    def test_result_is_stripped(self):
        from agents.linkedin import _build_user_profile_from_scan
        raw = "Name: Jane\nHeadline: Engineer\nHandle: jane\nAbout: Not provided"
        result = _build_user_profile_from_scan(raw)
        assert result == result.strip()


# ── build_task — market mode ──────────────────────────────────────────────

class TestLinkedInBuildTaskMarketMode:
    def test_no_strategy_returns_error_message(self, tmp_data_dir):
        from agents.linkedin import build_task
        with patch("agents.linkedin.load_context", return_value=""):
            result = build_task("market", {})
        assert "ERROR" in result
        assert "marketing strategy" in result.lower()
        assert "linkedin.com/feed" in result

    def test_with_strategy_returns_market_task(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy
        from agents.linkedin import build_task
        save_strategy(sample_strategy)
        with patch("agents.linkedin.load_context", return_value=""):
            result = build_task("market", {})
        # Should not contain ERROR
        assert "ERROR" not in result
        assert "linkedin" in result.lower() or "LINKEDIN" in result.upper()

    def test_force_action_passed_to_build_market_task(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy
        from agents.linkedin import build_task
        save_strategy(sample_strategy)
        with patch("agents.linkedin.load_context", return_value=""):
            result = build_task("market", {"force_action": "product_post"})
        assert "Product Post" in result
        assert "specifically requested" in result

    def test_no_force_action_uses_auto_decision(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy
        from agents.linkedin import build_task
        save_strategy(sample_strategy)
        with patch("agents.linkedin.load_context", return_value=""):
            result = build_task("market", {"force_action": None})
        assert "decide the best action" in result


# ── build_task — login mode ───────────────────────────────────────────────

class TestLinkedInBuildTaskLoginMode:
    def test_login_basic_task_always_included(self, tmp_data_dir):
        from agents.linkedin import build_task
        result = build_task("login", {})
        assert "https://www.linkedin.com/login" in result
        assert "log into" in result.lower() or "Login" in result

    def test_profile_scan_included_when_both_files_missing(self, tmp_data_dir):
        from agents.linkedin import build_task
        result = build_task("login", {})
        assert "PROFILE_DATA_START" in result
        assert "PROFILE_DATA_END" in result

    def test_profile_scan_included_when_user_profile_missing(self, tmp_data_dir):
        from agents.linkedin import build_task
        # Only linkedin_profile.txt exists
        (tmp_data_dir / "linkedin_profile.txt").write_text("some profile data")
        result = build_task("login", {})
        assert "PROFILE_DATA_START" in result

    def test_profile_scan_included_when_linkedin_profile_missing(self, tmp_data_dir):
        from agents.linkedin import build_task
        # Only user_profile.txt exists
        (tmp_data_dir / "user_profile.txt").write_text("some user data")
        result = build_task("login", {})
        assert "PROFILE_DATA_START" in result

    def test_no_profile_scan_when_both_profiles_exist(self, tmp_data_dir):
        from agents.linkedin import build_task
        (tmp_data_dir / "user_profile.txt").write_text("some user data")
        (tmp_data_dir / "linkedin_profile.txt").write_text("some profile data")
        result = build_task("login", {})
        assert "PROFILE_DATA_START" not in result

    def test_profile_scan_skipped_when_files_exist_but_empty(self, tmp_data_dir):
        """Empty files should be treated as missing — scan should still be included."""
        from agents.linkedin import build_task
        (tmp_data_dir / "user_profile.txt").write_text("")
        (tmp_data_dir / "linkedin_profile.txt").write_text("")
        result = build_task("login", {})
        assert "PROFILE_DATA_START" in result


# ── handle_agent_result — market mode ────────────────────────────────────

class TestLinkedInHandleAgentResultMarketMode:
    def test_delegates_to_handle_market_result(self, tmp_data_dir):
        from agents.linkedin import handle_agent_result
        result_text = "POSTS: https://linkedin.com/p/1\nACTION_TYPE: product_post\nPILLAR_USED: Educational\nDid the thing."
        result = handle_agent_result("market", result_text)
        assert result.startswith("✅")
        assert "Market action completed" in result

    def test_returns_checkmark_prefix(self, tmp_data_dir):
        from agents.linkedin import handle_agent_result
        result = handle_agent_result("market", "POSTS: url1\nACTION_TYPE: educational\nDone.")
        assert "✅" in result


# ── handle_agent_result — login mode ─────────────────────────────────────

class TestLinkedInHandleAgentResultLoginMode:
    def test_with_profile_data_saves_linkedin_profile(self, tmp_data_dir):
        from agents.linkedin import handle_agent_result
        result_text = (
            "Logged in successfully!\n"
            "PROFILE_DATA_START\n"
            "Name: Alice Smith\n"
            "Headline: Senior ML Engineer\n"
            "Handle: alicesmith\n"
            "About: Not provided\n"
            "PROFILE_DATA_END\n"
        )
        handle_agent_result("login", result_text)
        li_profile = tmp_data_dir / "linkedin_profile.txt"
        assert li_profile.exists()
        assert "Alice Smith" in li_profile.read_text()

    def test_with_profile_data_saves_user_profile_when_missing(self, tmp_data_dir):
        from agents.linkedin import handle_agent_result
        result_text = (
            "PROFILE_DATA_START\n"
            "Name: Alice Smith\n"
            "Headline: Engineer\n"
            "Handle: alicesmith\n"
            "About: Not provided\n"
            "PROFILE_DATA_END\n"
        )
        handle_agent_result("login", result_text)
        user_profile = tmp_data_dir / "user_profile.txt"
        assert user_profile.exists()
        assert "Alice Smith" in user_profile.read_text()

    def test_with_profile_data_does_not_overwrite_existing_user_profile(self, tmp_data_dir):
        from agents.linkedin import handle_agent_result
        existing_content = "Custom user profile content"
        (tmp_data_dir / "user_profile.txt").write_text(existing_content)
        result_text = (
            "PROFILE_DATA_START\n"
            "Name: Alice Smith\n"
            "Headline: Engineer\n"
            "Handle: alicesmith\n"
            "About: Not provided\n"
            "PROFILE_DATA_END\n"
        )
        handle_agent_result("login", result_text)
        user_profile = tmp_data_dir / "user_profile.txt"
        assert user_profile.read_text() == existing_content

    def test_with_profile_data_returns_scan_saved_message(self, tmp_data_dir):
        from agents.linkedin import handle_agent_result
        result_text = (
            "PROFILE_DATA_START\n"
            "Name: Alice\n"
            "Headline: Dev\n"
            "Handle: alice\n"
            "About: Not provided\n"
            "PROFILE_DATA_END\n"
        )
        result = handle_agent_result("login", result_text)
        assert "✅" in result
        assert "Login completed" in result

    def test_without_profile_data_returns_simple_success(self, tmp_data_dir):
        from agents.linkedin import handle_agent_result
        result = handle_agent_result("login", "Logged in successfully. No profile data extracted.")
        assert "✅" in result
        assert "Login completed" in result

    def test_empty_result_returns_no_output(self, tmp_data_dir):
        from agents.linkedin import handle_agent_result
        result = handle_agent_result("login", "")
        assert "No output generated" in result or "❌" in result

    def test_none_result_returns_no_output(self, tmp_data_dir):
        from agents.linkedin import handle_agent_result
        result = handle_agent_result("login", None)
        assert "No output generated" in result or "❌" in result


# ── handle_agent_result — post and comment modes ──────────────────────────

class TestLinkedInHandleAgentResultPostComment:
    def test_post_mode_returns_success(self, tmp_data_dir):
        from agents.linkedin import handle_agent_result
        result = handle_agent_result("post", "The post was published.")
        assert "✅" in result
        assert "Post" in result

    def test_comment_mode_returns_success(self, tmp_data_dir):
        from agents.linkedin import handle_agent_result
        result = handle_agent_result("comment", "Left a comment.")
        assert "✅" in result
        assert "Comment" in result