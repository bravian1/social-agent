# Contributing to Social Agent

Thanks for your interest in contributing! Here's everything you need to get started.

## Getting Started

1. Fork and clone the repo
2. Set up your development environment:

```bash
uv venv --python 3.11
source .venv/bin/activate
uv sync
```

3. Copy `.env.example` to `.env` and add your `GOOGLE_API_KEY`
4. Set up your data files from the examples in `data/`

## Project Structure

```
social-agent/
├── agents/             # Platform agent modules
│   ├── x.py            # X (Twitter) agent
│   ├── linkedin.py     # LinkedIn agent
│   ├── whatsapp.py     # WhatsApp agent
│   └── research.py     # Domain research module
├── schedulers/         # Periodic scheduler wrappers
│   ├── x_scheduler.py
│   └── linkedin_scheduler.py
├── data/               # User data (gitignored — use .example files as templates)
├── logs/               # Runtime logs (gitignored)
└── app.py              # Streamlit dashboard
```

## Adding a New Platform

Each platform agent follows a consistent pattern. To add a new one:

1. Create `agents/<platform>.py` with these functions:

```python
def setup_environment(debug: bool): ...
def load_context() -> str: ...
def build_task(mode: str, config: dict) -> str: ...
def setup_browser() -> BrowserSession: ...
def handle_agent_result(mode: str, result: str) -> str: ...
async def run_agent(mode: str, config: dict) -> str: ...
```

Use `from agents import DATA_DIR` for data file paths.

2. If it supports an "active" mode, add `schedulers/<platform>_scheduler.py` mirroring the existing schedulers.

3. Add the platform to the Streamlit dashboard in `app.py`.

4. Document the new modes in `README.md`.

## Code Guidelines

- Use `pathlib.Path` for all file paths
- Load data files from `DATA_DIR` (imported from `agents`)
- Handle missing files gracefully — agents should degrade without crashing
- Keep LLM temperatures consistent: `0.7` for creative tasks, `0.1` for analytical ones
- Suppress browser-use logging in non-debug mode (see `setup_environment()`)

## Pull Requests

- One feature or fix per PR
- Update `README.md` if you add new modes or change CLI arguments
- Test your changes against at least one platform before submitting
- Do not commit personal data files (`user_profile.txt`, `*.json` histories, etc.)

## Reporting Issues

Please include:
- Python version (`python --version`)
- browser-use version (from `uv pip show browser-use`)
- Platform and mode you were using
- Full error message or unexpected behaviour
