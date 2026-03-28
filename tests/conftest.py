"""Shared test fixtures and configuration."""
import sys
import types
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock


def _install_browser_use_stub():
    """Install lightweight stubs for browser_use so agents can be imported without the package."""
    if "browser_use" in sys.modules:
        return

    browser_use = types.ModuleType("browser_use")
    browser_use.Agent = MagicMock()
    browser_use.BrowserSession = MagicMock()
    sys.modules["browser_use"] = browser_use

    llm_pkg = types.ModuleType("browser_use.llm")
    sys.modules["browser_use.llm"] = llm_pkg

    llm_google = types.ModuleType("browser_use.llm.google")
    llm_google.ChatGoogle = MagicMock()
    sys.modules["browser_use.llm.google"] = llm_google


_install_browser_use_stub()


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Provide a temporary DATA_DIR and patch it in all relevant modules."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    monkeypatch.setattr("agents.DATA_DIR", data_dir)
    monkeypatch.setattr("agents.market.DATA_DIR", data_dir)
    # linkedin and x import DATA_DIR at module level — patch via the module namespace
    import agents.linkedin
    import agents.x
    monkeypatch.setattr(agents.linkedin, "DATA_DIR", data_dir)
    monkeypatch.setattr(agents.x, "DATA_DIR", data_dir)

    return data_dir


@pytest.fixture
def sample_strategy():
    """Return a minimal valid marketing strategy dict."""
    return {
        "business_description": "An open-source CLI tool for edge ML deployment",
        "brand_voice": "Technical and direct. No fluff.",
        "target_audience": ["ML engineers", "DevOps teams", "Edge computing researchers"],
        "keywords": ["edge AI", "MLOps", "on-device inference", "TinyML"],
        "competitors": ["ONNX Runtime", "TensorFlow Lite"],
        "content_pillars": [
            {"name": "Product Updates", "description": "New releases and features"},
            {"name": "Educational", "description": "How-to guides for edge deployment"},
        ],
        "posting_cadence": {
            "x": {"posts_per_week": 5, "replies_per_session": 3},
            "linkedin": {"posts_per_week": 3, "comments_per_session": 2},
        },
        "platforms": ["x", "linkedin"],
        "generated_at": "2026-01-01T00:00:00",
        "last_modified": "2026-01-01T00:00:00",
    }