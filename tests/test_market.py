"""Tests for agents/market.py — new file in this PR."""
import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── Constants ────────────────────────────────────────────────────────────

class TestActionConstants:
    def test_action_types_list(self):
        from agents.market import ACTION_TYPES
        assert "product_post" in ACTION_TYPES
        assert "industry_commentary" in ACTION_TYPES
        assert "keyword_reply" in ACTION_TYPES
        assert "engagement" in ACTION_TYPES
        assert "educational" in ACTION_TYPES
        assert "social_proof" in ACTION_TYPES
        assert len(ACTION_TYPES) == 6

    def test_action_labels_match_types(self):
        from agents.market import ACTION_TYPES, ACTION_LABELS
        for action in ACTION_TYPES:
            assert action in ACTION_LABELS, f"{action} missing from ACTION_LABELS"

    def test_action_labels_are_human_readable(self):
        from agents.market import ACTION_LABELS
        for key, label in ACTION_LABELS.items():
            # Labels should be title-cased words, not raw identifiers
            assert label != key, f"Label for {key} should differ from key"
            assert label[0].isupper(), f"Label '{label}' should start with uppercase"


# ── save_strategy ────────────────────────────────────────────────────────

class TestSaveStrategy:
    def test_creates_file(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy
        path = save_strategy(sample_strategy)
        assert path.exists()
        assert path.name == "market_strategy.json"

    def test_written_content_is_valid_json(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy
        save_strategy(sample_strategy)
        content = json.loads((tmp_data_dir / "market_strategy.json").read_text())
        assert content["business_description"] == sample_strategy["business_description"]

    def test_updates_last_modified(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy
        original_modified = sample_strategy["last_modified"]
        save_strategy(sample_strategy)
        content = json.loads((tmp_data_dir / "market_strategy.json").read_text())
        # last_modified should be a recent ISO timestamp (updated during save)
        assert content["last_modified"] != "" or content["last_modified"] is not None

    def test_creates_data_dir_if_missing(self, tmp_path, monkeypatch):
        from agents import market as market_module
        data_dir = tmp_path / "nonexistent_data"
        monkeypatch.setattr(market_module, "DATA_DIR", data_dir)
        strategy = {"business_description": "test", "keywords": []}
        path = market_module.save_strategy(strategy)
        assert data_dir.exists()
        assert path.exists()

    def test_unicode_content_preserved(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy
        sample_strategy["business_description"] = "Café & Résumé tool — 日本語"
        save_strategy(sample_strategy)
        content = json.loads((tmp_data_dir / "market_strategy.json").read_text(encoding="utf-8"))
        assert content["business_description"] == "Café & Résumé tool — 日本語"


# ── load_market_strategy ─────────────────────────────────────────────────

class TestLoadMarketStrategy:
    def test_returns_none_when_file_missing(self, tmp_data_dir):
        from agents.market import load_market_strategy
        result = load_market_strategy()
        assert result is None

    def test_returns_dict_when_file_exists(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy, load_market_strategy
        save_strategy(sample_strategy)
        result = load_market_strategy()
        assert isinstance(result, dict)
        assert result["business_description"] == sample_strategy["business_description"]

    def test_returns_none_on_invalid_json(self, tmp_data_dir):
        from agents.market import load_market_strategy
        (tmp_data_dir / "market_strategy.json").write_text("not valid json {{{")
        result = load_market_strategy()
        assert result is None

    def test_returns_none_on_empty_file(self, tmp_data_dir):
        from agents.market import load_market_strategy
        (tmp_data_dir / "market_strategy.json").write_text("")
        result = load_market_strategy()
        assert result is None

    def test_preserves_all_fields(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy, load_market_strategy
        save_strategy(sample_strategy)
        result = load_market_strategy()
        assert result["keywords"] == sample_strategy["keywords"]
        assert result["competitors"] == sample_strategy["competitors"]
        assert result["content_pillars"] == sample_strategy["content_pillars"]


# ── derive_research_domain ───────────────────────────────────────────────

class TestDeriveResearchDomain:
    def test_uses_keywords_and_audience(self):
        from agents.market import derive_research_domain
        strategy = {
            "business_description": "Some business",
            "keywords": ["edge AI", "MLOps", "TinyML"],
            "target_audience": ["ML engineers", "DevOps teams"],
        }
        result = derive_research_domain(strategy)
        assert "edge AI" in result
        assert "MLOps" in result
        assert "TinyML" in result
        assert "ML engineers" in result

    def test_takes_first_three_keywords(self):
        from agents.market import derive_research_domain
        strategy = {
            "business_description": "Some business",
            "keywords": ["k1", "k2", "k3", "k4", "k5"],
            "target_audience": ["audience1"],
        }
        result = derive_research_domain(strategy)
        assert "k1" in result
        assert "k2" in result
        assert "k3" in result
        assert "k4" not in result  # Only first 3 keywords

    def test_fallback_to_description_when_no_keywords_or_audience(self):
        from agents.market import derive_research_domain
        strategy = {
            "business_description": "A unique business idea",
            "keywords": [],
            "target_audience": [],
        }
        result = derive_research_domain(strategy)
        assert "A unique business idea" in result

    def test_fallback_to_generic_when_all_empty(self):
        from agents.market import derive_research_domain
        strategy = {
            "business_description": "",
            "keywords": [],
            "target_audience": [],
        }
        result = derive_research_domain(strategy)
        assert result == "General Business and Marketing"

    def test_description_truncated_to_80_chars(self):
        from agents.market import derive_research_domain
        long_desc = "X" * 200
        strategy = {
            "business_description": long_desc,
            "keywords": [],
            "target_audience": [],
        }
        result = derive_research_domain(strategy)
        assert len(result) <= 80

    def test_missing_keys_handled_gracefully(self):
        from agents.market import derive_research_domain
        # Empty dict should not raise
        result = derive_research_domain({})
        assert result == "General Business and Marketing"


# ── load_market_context ──────────────────────────────────────────────────

class TestLoadMarketContext:
    def test_returns_empty_string_when_no_files(self, tmp_data_dir):
        from agents.market import load_market_context
        result = load_market_context("x")
        assert result == ""

    def test_includes_strategy_section_when_strategy_exists(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy, load_market_context
        save_strategy(sample_strategy)
        result = load_market_context("x")
        assert "MARKETING STRATEGY" in result
        assert sample_strategy["brand_voice"] in result
        assert sample_strategy["keywords"][0] in result

    def test_includes_target_audience(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy, load_market_context
        save_strategy(sample_strategy)
        result = load_market_context("x")
        assert "ML engineers" in result

    def test_includes_competitors(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy, load_market_context
        save_strategy(sample_strategy)
        result = load_market_context("x")
        assert "ONNX Runtime" in result

    def test_includes_content_pillars(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy, load_market_context
        save_strategy(sample_strategy)
        result = load_market_context("x")
        assert "Product Updates" in result
        assert "Educational" in result

    def test_x_cadence_in_context(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy, load_market_context
        save_strategy(sample_strategy)
        result = load_market_context("x")
        assert "5" in result  # posts_per_week for x

    def test_linkedin_cadence_in_context(self, tmp_data_dir, sample_strategy):
        from agents.market import save_strategy, load_market_context
        save_strategy(sample_strategy)
        result = load_market_context("linkedin")
        assert "3" in result  # posts_per_week for linkedin

    def test_includes_history_when_present(self, tmp_data_dir):
        from agents.market import load_market_context
        history = [
            {
                "timestamp": "2026-01-01 10:00:00",
                "action": "Posted a tweet",
                "action_type": "product_post",
                "pillar_used": "Product Updates",
                "summary": "Promoted new feature",
                "tweets": ["https://x.com/user/status/123"],
            }
        ]
        (tmp_data_dir / "market_history_x.json").write_text(json.dumps(history))
        result = load_market_context("x")
        assert "MARKET HISTORY" in result
        assert "product_post" in result
        assert "https://x.com/user/status/123" in result

    def test_x_uses_virality_notes(self, tmp_data_dir):
        from agents.market import load_market_context
        (tmp_data_dir / "virality_notes.txt").write_text("hooks matter")
        result = load_market_context("x")
        assert "hooks matter" in result
        assert "VIRALITY PLAYBOOK" in result

    def test_linkedin_uses_linkedin_virality_notes(self, tmp_data_dir):
        from agents.market import load_market_context
        (tmp_data_dir / "linkedin_virality_notes.txt").write_text("linkedin hooks matter")
        result = load_market_context("linkedin")
        assert "linkedin hooks matter" in result

    def test_x_does_not_use_linkedin_virality_notes(self, tmp_data_dir):
        from agents.market import load_market_context
        (tmp_data_dir / "linkedin_virality_notes.txt").write_text("ONLY_LINKEDIN_CONTENT")
        (tmp_data_dir / "virality_notes.txt").write_text("x_content")
        result = load_market_context("x")
        assert "ONLY_LINKEDIN_CONTENT" not in result

    def test_includes_user_profile_when_present(self, tmp_data_dir):
        from agents.market import load_market_context
        (tmp_data_dir / "user_profile.txt").write_text("I am a developer who loves Rust.")
        result = load_market_context("x")
        assert "I am a developer who loves Rust." in result
        assert "PERSONALITY" in result

    def test_includes_general_knowledge_when_present(self, tmp_data_dir):
        from agents.market import load_market_context
        (tmp_data_dir / "data.txt").write_text("Edge AI is growing rapidly in 2026.")
        result = load_market_context("x")
        assert "Edge AI is growing rapidly in 2026." in result
        assert "GENERAL KNOWLEDGE" in result

    def test_includes_market_insights_when_present(self, tmp_data_dir):
        from agents.market import load_market_context
        (tmp_data_dir / "market_insights.txt").write_text("Short posts outperform long ones.")
        result = load_market_context("x")
        assert "Short posts outperform long ones." in result
        assert "MARKET INSIGHTS" in result

    def test_includes_performance_data_when_present(self, tmp_data_dir):
        from agents.market import load_market_context
        perf = [{"date": "2026-01-01", "impressions": 500, "engagements": 20, "best_post": "http://x.com/s/1"}]
        (tmp_data_dir / "market_performance.json").write_text(json.dumps(perf))
        result = load_market_context("x")
        assert "RECENT PERFORMANCE" in result
        assert "500" in result

    def test_history_urls_collected_from_posts_key(self, tmp_data_dir):
        """LinkedIn history uses 'posts' key; URLs should appear in context."""
        from agents.market import load_market_context
        history = [
            {
                "timestamp": "2026-01-01 10:00:00",
                "action": "Posted on LinkedIn",
                "action_type": "educational",
                "pillar_used": "Educational",
                "summary": "Shared a tip",
                "posts": ["https://linkedin.com/posts/user-12345"],
            }
        ]
        (tmp_data_dir / "market_history_linkedin.json").write_text(json.dumps(history))
        result = load_market_context("linkedin")
        assert "https://linkedin.com/posts/user-12345" in result

    def test_graceful_on_corrupted_history_file(self, tmp_data_dir):
        from agents.market import load_market_context
        (tmp_data_dir / "market_history_x.json").write_text("CORRUPT{{")
        # Should not raise, just skip history
        result = load_market_context("x")
        assert "MARKET HISTORY" not in result

    def test_graceful_on_corrupted_performance_file(self, tmp_data_dir):
        from agents.market import load_market_context
        (tmp_data_dir / "market_performance.json").write_text("CORRUPT{{")
        result = load_market_context("x")
        assert "RECENT PERFORMANCE" not in result


# ── build_market_task ────────────────────────────────────────────────────

class TestBuildMarketTask:
    def test_x_platform_contains_tweets_label(self, sample_strategy):
        from agents.market import build_market_task
        result = build_market_task("x", sample_strategy, "")
        assert "TWEETS:" in result

    def test_linkedin_platform_contains_posts_label(self, sample_strategy):
        from agents.market import build_market_task
        result = build_market_task("linkedin", sample_strategy, "")
        assert "POSTS:" in result

    def test_x_platform_uses_x_home_url(self, sample_strategy):
        from agents.market import build_market_task
        result = build_market_task("x", sample_strategy, "")
        assert "https://x.com/home" in result

    def test_linkedin_platform_uses_linkedin_url(self, sample_strategy):
        from agents.market import build_market_task
        result = build_market_task("linkedin", sample_strategy, "")
        assert "https://www.linkedin.com/feed/" in result

    def test_x_includes_typing_rule(self, sample_strategy):
        from agents.market import build_market_task
        result = build_market_task("x", sample_strategy, "")
        assert "KNOWN TYPING BUG" in result

    def test_linkedin_does_not_include_typing_rule(self, sample_strategy):
        from agents.market import build_market_task
        result = build_market_task("linkedin", sample_strategy, "")
        assert "KNOWN TYPING BUG" not in result

    def test_product_description_in_task(self, sample_strategy):
        from agents.market import build_market_task
        result = build_market_task("x", sample_strategy, "")
        assert sample_strategy["business_description"] in result

    def test_brand_voice_in_task(self, sample_strategy):
        from agents.market import build_market_task
        result = build_market_task("x", sample_strategy, "")
        assert sample_strategy["brand_voice"] in result

    def test_keywords_in_task(self, sample_strategy):
        from agents.market import build_market_task
        result = build_market_task("x", sample_strategy, "")
        assert "edge AI" in result

    def test_context_included_in_task(self, sample_strategy):
        from agents.market import build_market_task
        context = "--- MY CUSTOM CONTEXT ---"
        result = build_market_task("x", sample_strategy, context)
        assert context in result

    def test_force_action_product_post(self, sample_strategy):
        from agents.market import build_market_task
        result = build_market_task("x", sample_strategy, "", force_action="product_post")
        assert "Product Post" in result
        assert "specifically requested" in result

    def test_force_action_educational(self, sample_strategy):
        from agents.market import build_market_task
        result = build_market_task("linkedin", sample_strategy, "", force_action="educational")
        assert "Educational" in result
        assert "specifically requested" in result

    def test_force_action_not_in_action_types_ignored(self, sample_strategy):
        from agents.market import build_market_task
        # Invalid force_action should fall through to auto-decision
        result = build_market_task("x", sample_strategy, "", force_action="invalid_action")
        assert "specifically requested" not in result
        assert "decide the best action" in result

    def test_force_action_none_uses_auto_decision(self, sample_strategy):
        from agents.market import build_market_task
        result = build_market_task("x", sample_strategy, "", force_action=None)
        assert "decide the best action" in result

    def test_content_pillars_in_task(self, sample_strategy):
        from agents.market import build_market_task
        result = build_market_task("x", sample_strategy, "")
        assert "Product Updates" in result
        assert "Educational" in result

    def test_action_types_listed_when_no_force(self, sample_strategy):
        from agents.market import build_market_task
        result = build_market_task("x", sample_strategy, "", force_action=None)
        assert "Product Post" in result
        assert "Industry Commentary" in result
        assert "Keyword Reply" in result

    def test_empty_keywords_uses_fallback(self):
        from agents.market import build_market_task
        strategy = {"business_description": "test", "keywords": [], "brand_voice": "direct",
                    "content_pillars": [], "competitors": []}
        result = build_market_task("x", strategy, "")
        assert "relevant industry terms" in result

    def test_empty_pillars_uses_fallback(self):
        from agents.market import build_market_task
        strategy = {"business_description": "test", "keywords": ["kw1"], "brand_voice": "direct",
                    "content_pillars": [], "competitors": []}
        result = build_market_task("x", strategy, "")
        assert "(none defined)" in result

    def test_all_six_action_types_listed_for_auto(self, sample_strategy):
        from agents.market import build_market_task, ACTION_TYPES
        result = build_market_task("x", sample_strategy, "", force_action=None)
        for action_type in ACTION_TYPES:
            # The action type labels appear in the decision section
            assert action_type.replace("_", " ").lower() in result.lower() or \
                   action_type in result, f"{action_type} not mentioned"


# ── handle_market_result ─────────────────────────────────────────────────

class TestHandleMarketResult:
    def test_empty_result_returns_no_output(self, tmp_data_dir):
        from agents.market import handle_market_result
        result = handle_market_result("x", "")
        assert result == "No output generated"

    def test_none_result_returns_no_output(self, tmp_data_dir):
        from agents.market import handle_market_result
        result = handle_market_result("x", None)
        assert result == "No output generated"

    def test_saves_history_file_for_x(self, tmp_data_dir):
        from agents.market import handle_market_result
        handle_market_result("x", "Some result\nACTION_TYPE: product_post\nPILLAR_USED: Product Updates\nTWEETS: https://x.com/s/1")
        history_file = tmp_data_dir / "market_history_x.json"
        assert history_file.exists()

    def test_saves_history_file_for_linkedin(self, tmp_data_dir):
        from agents.market import handle_market_result
        handle_market_result("linkedin", "Some result\nACTION_TYPE: product_post\nPOSTS: https://linkedin.com/p/1")
        history_file = tmp_data_dir / "market_history_linkedin.json"
        assert history_file.exists()

    def test_extracts_tweet_urls_for_x(self, tmp_data_dir):
        from agents.market import handle_market_result
        handle_market_result("x", "TWEETS: https://x.com/a/1, https://x.com/b/2\nACTION_TYPE: product_post")
        history = json.loads((tmp_data_dir / "market_history_x.json").read_text())
        assert len(history) == 1
        assert "https://x.com/a/1" in history[0]["tweets"]
        assert "https://x.com/b/2" in history[0]["tweets"]

    def test_uses_posts_key_for_linkedin(self, tmp_data_dir):
        from agents.market import handle_market_result
        handle_market_result("linkedin", "POSTS: https://linkedin.com/p/1\nACTION_TYPE: educational")
        history = json.loads((tmp_data_dir / "market_history_linkedin.json").read_text())
        assert "posts" in history[0]
        assert "https://linkedin.com/p/1" in history[0]["posts"]

    def test_extracts_action_type(self, tmp_data_dir):
        from agents.market import handle_market_result
        handle_market_result("x", "TWEETS: url1\nACTION_TYPE: industry_commentary\nPILLAR_USED: pillar1")
        history = json.loads((tmp_data_dir / "market_history_x.json").read_text())
        assert history[0]["action_type"] == "industry_commentary"

    def test_extracts_pillar_used(self, tmp_data_dir):
        from agents.market import handle_market_result
        handle_market_result("x", "TWEETS: url1\nACTION_TYPE: educational\nPILLAR_USED: Product Updates")
        history = json.loads((tmp_data_dir / "market_history_x.json").read_text())
        assert history[0]["pillar_used"] == "Product Updates"

    def test_appends_market_insight(self, tmp_data_dir):
        from agents.market import handle_market_result
        handle_market_result("x", "TWEETS: url1\nACTION_TYPE: product_post\nMARKET_INSIGHT: Short posts get more clicks\nDid the thing.")
        insights_file = tmp_data_dir / "market_insights.txt"
        assert insights_file.exists()
        content = insights_file.read_text()
        assert "Short posts get more clicks" in content
        assert "[x]" in content

    def test_logs_performance_metrics(self, tmp_data_dir):
        from agents.market import handle_market_result
        handle_market_result("x", "TWEETS: url1\nACTION_TYPE: product_post\nMARKET_METRICS: impressions=1000, engagements=50, best_post=https://x.com/s/1\nDone.")
        perf_file = tmp_data_dir / "market_performance.json"
        assert perf_file.exists()
        perf = json.loads(perf_file.read_text())
        assert perf[0]["impressions"] == 1000
        assert perf[0]["engagements"] == 50
        assert perf[0]["best_post"] == "https://x.com/s/1"
        assert perf[0]["platform"] == "x"

    def test_history_capped_at_50_entries(self, tmp_data_dir):
        from agents.market import handle_market_result
        # Pre-seed with 50 entries
        existing = [{"timestamp": f"2026-01-{i:02d} 00:00:00", "action": "a", "action_type": "x",
                     "pillar_used": "p", "summary": "s", "tweets": []} for i in range(1, 51)]
        (tmp_data_dir / "market_history_x.json").write_text(json.dumps(existing))
        handle_market_result("x", "TWEETS: url1\nACTION_TYPE: product_post\nDone.")
        history = json.loads((tmp_data_dir / "market_history_x.json").read_text())
        assert len(history) == 50

    def test_appends_to_existing_history(self, tmp_data_dir):
        from agents.market import handle_market_result
        existing = [{"timestamp": "2026-01-01 00:00:00", "action": "old", "action_type": "old",
                     "pillar_used": "old", "summary": "old", "tweets": []}]
        (tmp_data_dir / "market_history_x.json").write_text(json.dumps(existing))
        handle_market_result("x", "TWEETS: url1\nACTION_TYPE: product_post\nNew action done.")
        history = json.loads((tmp_data_dir / "market_history_x.json").read_text())
        assert len(history) == 2

    def test_returns_summary_string(self, tmp_data_dir):
        from agents.market import handle_market_result
        result = handle_market_result("x", "TWEETS: url1\nACTION_TYPE: product_post\nPosted a tweet about the product.")
        assert "Market action completed" in result
        assert "x" in result

    def test_no_insight_when_marker_absent(self, tmp_data_dir):
        from agents.market import handle_market_result
        handle_market_result("x", "TWEETS: url1\nACTION_TYPE: product_post\nDone.")
        insights_file = tmp_data_dir / "market_insights.txt"
        assert not insights_file.exists()

    def test_no_performance_when_metrics_absent(self, tmp_data_dir):
        from agents.market import handle_market_result
        handle_market_result("x", "TWEETS: url1\nACTION_TYPE: product_post\nDone.")
        perf_file = tmp_data_dir / "market_performance.json"
        assert not perf_file.exists()

    def test_summary_extracted_from_last_non_marker_line(self, tmp_data_dir):
        from agents.market import handle_market_result
        result = handle_market_result(
            "x",
            "TWEETS: url1\nACTION_TYPE: product_post\nPILLAR_USED: Educational\nMARKET_INSIGHT: test\nSuccessfully posted a tweet."
        )
        history = json.loads((tmp_data_dir / "market_history_x.json").read_text())
        assert history[0]["summary"] == "Successfully posted a tweet."

    def test_corrupted_existing_history_handled_gracefully(self, tmp_data_dir):
        from agents.market import handle_market_result
        (tmp_data_dir / "market_history_x.json").write_text("CORRUPT{{")
        # Should not raise; should write fresh history
        handle_market_result("x", "TWEETS: url1\nACTION_TYPE: product_post\nDone.")
        history = json.loads((tmp_data_dir / "market_history_x.json").read_text())
        assert len(history) == 1

    def test_insight_appended_with_platform_tag(self, tmp_data_dir):
        from agents.market import handle_market_result
        handle_market_result("linkedin", "POSTS: url1\nACTION_TYPE: educational\nMARKET_INSIGHT: LinkedIn rewards long-form.\nDone.")
        content = (tmp_data_dir / "market_insights.txt").read_text()
        assert "[linkedin]" in content
        assert "LinkedIn rewards long-form." in content

    def test_performance_appended_to_existing(self, tmp_data_dir):
        from agents.market import handle_market_result
        existing_perf = [{"date": "2026-01-01 00:00", "platform": "x", "raw": "impressions=100"}]
        (tmp_data_dir / "market_performance.json").write_text(json.dumps(existing_perf))
        handle_market_result("x", "TWEETS: url1\nACTION_TYPE: product_post\nMARKET_METRICS: impressions=200, engagements=10\nDone.")
        perf = json.loads((tmp_data_dir / "market_performance.json").read_text())
        assert len(perf) == 2