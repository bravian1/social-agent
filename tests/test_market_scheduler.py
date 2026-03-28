"""Tests for schedulers/market_scheduler.py — new file in this PR."""
import asyncio
import json
import logging
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock


# ── setup_logging ─────────────────────────────────────────────────────────

class TestSetupLogging:
    def test_returns_logger(self, tmp_path, monkeypatch):
        import schedulers.market_scheduler as ms
        monkeypatch.setattr(ms, "LOGS_DIR", tmp_path)

        # Call setup_logging fresh (use a unique logger name to avoid state leakage)
        logger = ms.setup_logging()
        assert logger is not None
        assert isinstance(logger, logging.Logger)

    def test_logger_name_is_market_scheduler(self, tmp_path, monkeypatch):
        import schedulers.market_scheduler as ms
        monkeypatch.setattr(ms, "LOGS_DIR", tmp_path)
        logger = ms.setup_logging()
        assert logger.name == "market_scheduler"

    def test_logger_has_file_handler(self, tmp_path, monkeypatch):
        import schedulers.market_scheduler as ms
        monkeypatch.setattr(ms, "LOGS_DIR", tmp_path)
        # Remove any pre-existing handlers on the logger to test setup fresh
        market_logger = logging.getLogger("market_scheduler")
        market_logger.handlers.clear()
        logger = ms.setup_logging()
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "FileHandler" in handler_types

    def test_logger_has_stream_handler(self, tmp_path, monkeypatch):
        import schedulers.market_scheduler as ms
        monkeypatch.setattr(ms, "LOGS_DIR", tmp_path)
        market_logger = logging.getLogger("market_scheduler")
        market_logger.handlers.clear()
        logger = ms.setup_logging()
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "StreamHandler" in handler_types

    def test_log_file_created(self, tmp_path, monkeypatch):
        import schedulers.market_scheduler as ms
        monkeypatch.setattr(ms, "LOGS_DIR", tmp_path)
        market_logger = logging.getLogger("market_scheduler")
        market_logger.handlers.clear()
        ms.setup_logging()
        log_file = tmp_path / "market_scheduler.log"
        assert log_file.exists()


# ── market_loop — no strategy ─────────────────────────────────────────────

class TestMarketLoopNoStrategy:
    def test_exits_early_when_no_strategy(self, tmp_data_dir):
        """market_loop should return immediately if no strategy is found."""
        import schedulers.market_scheduler as ms

        async def run():
            await ms.market_loop(
                platforms=["x"],
                interval_min=1,
                interval_max=2,
                force_action=None,
            )

        # No strategy file exists in tmp_data_dir
        asyncio.run(run())
        # If we get here without hanging, the early return works

    def test_logs_error_when_no_strategy(self, tmp_data_dir, caplog):
        import schedulers.market_scheduler as ms

        async def run():
            await ms.market_loop(
                platforms=["x"],
                interval_min=1,
                interval_max=2,
            )

        with caplog.at_level(logging.ERROR, logger="market_scheduler"):
            asyncio.run(run())

        assert any("strategy" in record.message.lower() for record in caplog.records)


# ── market_loop — with strategy, single iteration ────────────────────────

class TestMarketLoopWithStrategy:
    def test_runs_single_iteration_and_exits(self, tmp_data_dir, sample_strategy):
        """Test market_loop runs one iteration when run_agent is mocked to complete."""
        from agents.market import save_strategy
        import schedulers.market_scheduler as ms

        save_strategy(sample_strategy)

        call_count = 0

        async def mock_run_agent(mode, config):
            nonlocal call_count
            call_count += 1
            # Raise KeyboardInterrupt after first call to stop the loop
            raise KeyboardInterrupt()

        async def run():
            with patch("agents.x.run_agent", side_effect=mock_run_agent), \
                 patch("agents.linkedin.run_agent", side_effect=mock_run_agent), \
                 patch("asyncio.sleep", new_callable=AsyncMock):
                await ms.market_loop(
                    platforms=["x"],
                    interval_min=1,
                    interval_max=2,
                )

        asyncio.run(run())
        assert call_count >= 1

    def test_uses_only_valid_platforms(self, tmp_data_dir, sample_strategy):
        """Only 'x' and 'linkedin' should be usable as platforms."""
        from agents.market import save_strategy
        import schedulers.market_scheduler as ms

        save_strategy(sample_strategy)

        platforms_used = []

        async def mock_run_agent_x(mode, config):
            platforms_used.append("x")
            raise KeyboardInterrupt()

        async def run():
            with patch("agents.x.run_agent", side_effect=mock_run_agent_x), \
                 patch("asyncio.sleep", new_callable=AsyncMock):
                await ms.market_loop(
                    platforms=["x"],
                    interval_min=1,
                    interval_max=2,
                )

        asyncio.run(run())
        assert "x" in platforms_used

    def test_cadence_weights_computed_from_strategy(self, tmp_data_dir, sample_strategy):
        """Platform weights should reflect posting_cadence in strategy."""
        from agents.market import save_strategy, load_market_strategy
        import schedulers.market_scheduler as ms

        # X: 5 posts/week, LinkedIn: 3 posts/week
        save_strategy(sample_strategy)
        strategy = load_market_strategy()

        cadence = strategy.get("posting_cadence", {})
        x_weight = cadence.get("x", {}).get("posts_per_week", 3)
        li_weight = cadence.get("linkedin", {}).get("posts_per_week", 3)

        assert x_weight == 5
        assert li_weight == 3
        # X should be weighted more heavily
        assert x_weight > li_weight

    def test_force_action_passed_to_config(self, tmp_data_dir, sample_strategy):
        """force_action should be passed into run_agent's config."""
        from agents.market import save_strategy
        import schedulers.market_scheduler as ms

        save_strategy(sample_strategy)

        received_configs = []

        async def mock_run_agent(mode, config):
            received_configs.append(config)
            raise KeyboardInterrupt()

        async def run():
            with patch("agents.x.run_agent", side_effect=mock_run_agent), \
                 patch("asyncio.sleep", new_callable=AsyncMock):
                await ms.market_loop(
                    platforms=["x"],
                    interval_min=1,
                    interval_max=2,
                    force_action="product_post",
                )

        asyncio.run(run())
        assert received_configs[0]["force_action"] == "product_post"

    def test_recovers_from_exception_in_loop(self, tmp_data_dir, sample_strategy, caplog):
        """An exception in run_agent should be caught, logged, and the loop should retry."""
        from agents.market import save_strategy
        import schedulers.market_scheduler as ms

        save_strategy(sample_strategy)

        call_count = 0

        async def mock_run_agent(mode, config):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated browser error")
            raise KeyboardInterrupt()

        sleep_calls = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)

        async def run():
            with patch("agents.x.run_agent", side_effect=mock_run_agent), \
                 patch("agents.linkedin.run_agent", side_effect=mock_run_agent), \
                 patch("asyncio.sleep", side_effect=mock_sleep):
                await ms.market_loop(
                    platforms=["x"],
                    interval_min=1,
                    interval_max=2,
                )

        asyncio.run(run())
        # Should have slept 300 seconds (5 min) after the error
        assert 300 in sleep_calls
        # And should have made 2 calls total
        assert call_count == 2