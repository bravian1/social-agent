# Social Agent

AI-powered social media automation for X (Twitter), LinkedIn, and WhatsApp using [browser-use](https://github.com/browser-use/browser-use) + Google Gemini.

The agent manages your social media presence by browsing the actual platforms in a real Chrome browser — posting, replying, engaging with feeds, and running on a schedule — all while maintaining your authentic voice and persona.

## Features

- **X (Twitter):** Scrape feed, post, reply, active engagement sessions, product marketing, research, custom tasks
- **LinkedIn:** Scrape profile, post, comment, active engagement sessions, custom tasks
- **WhatsApp:** Login via QR code, auto-respond to specific contacts or custom lists
- **Schedulers:** Run X and LinkedIn active modes on randomized intervals for natural-looking patterns
- **Research Engine:** Generate a domain knowledge base using Gemini + Google Search
- **Streamlit Dashboard:** Visual control panel — set up your API key and persona, start/stop schedulers, run one-off tasks, update style references

## Prerequisites

- Python 3.11+
- Google Chrome installed
- A [Google API key](https://aistudio.google.com/app/apikey) (Gemini)
- [uv](https://github.com/astral-sh/uv)

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/your-username/social-agent.git
cd social-agent
uv sync
```

### 2. Launch the dashboard

```bash
uv run streamlit run app.py
```

If anything isn't configured yet, the dashboard will show a banner at the top telling you exactly what's missing.

### 3. Set up in the Settings tab

Open the **Settings** section in the dashboard to:
- Paste your `GOOGLE_API_KEY` (saved directly to `.env`)
- Fill in your persona, content queue, and LinkedIn strategy — the files are created automatically
- Run **Scrape X feed** and **Scrape X replies** to give the agent style references
- Run **Update research** to load the latest news into the agent's knowledge base

### 4. Log in to platforms (first time only)

Use the **login** mode in each platform's section in the dashboard, or via CLI:

```bash
uv run python -m agents.x login
uv run python -m agents.linkedin login
```

The browser will open — log in normally. Your session is saved and reused.

## Usage

### Dashboard

`uv run streamlit run app.py` — the recommended way to use the agent. Navigate between platforms using the sidebar:

| Section | What it does |
|---------|-------------|
| **X** | Run any X mode, start/stop the scheduler, edit your content queue |
| **LinkedIn** | Same for LinkedIn |
| **WhatsApp** | Start the auto-responder or open the login browser |
| **Settings** | Set your API key, configure your persona files, scrape style references, update research |

A banner at the top warns you if the API key or required files are missing.

### CLI

Each platform agent can also be run directly:

```bash
# X (Twitter)
uv run python -m agents.x active --theme "AI and software"       # Browse and engage naturally
uv run python -m agents.x post --theme "developer tools"          # Post a tweet
uv run python -m agents.x reply --url <tweet_url> --theme "AI"   # Reply to a tweet
uv run python -m agents.x scrape --count 15                       # Extract feed tweets
uv run python -m agents.x research --domain "AI and Software Development"
uv run python -m agents.x market --product "My product description"
uv run python -m agents.x custom --custom-prompt "Your instructions here"

# LinkedIn
uv run python -m agents.linkedin active --theme "software development"
uv run python -m agents.linkedin post --theme "MCP and AI agents"
uv run python -m agents.linkedin comment --url <post_url> --theme "dev tools"

# WhatsApp
uv run python -m agents.whatsapp --login                          # Open browser to scan QR code
uv run python -m agents.whatsapp --auto-person --name "John"      # Watch a specific contact
uv run python -m agents.whatsapp --auto-unread                    # Sweep all unread
uv run python -m agents.whatsapp --auto-unread --filter "Favorites"  # Sweep a specific list

# Schedulers (run active mode periodically)
uv run python -m schedulers.x_scheduler --theme "tech" --interval-min 60 --interval-max 120
uv run python -m schedulers.linkedin_scheduler --theme "software development"
```

### The `user_requests.txt` workflow

Drop lines into `data/user_requests.txt` for things you want posted:

```
Just shipped a feature that cuts API response time by 60% — here's how
Hot take: most "AI wrappers" aren't solving the right problems
```

During each **active** session, the agent picks one, posts it in your voice, and removes it from the file. This is how you queue content without scheduling exact times.

### Research mode

Generates a comprehensive, current knowledge base for your domain using Gemini + Google Search. Run it periodically to keep the agent's context fresh:

```bash
uv run python -m agents.x research --domain "AI and Software Development"
```

The output is saved to `data/` and automatically loaded into all agent prompts.

## Configuration

### data/ files reference

| File | Purpose | Created by |
|------|---------|------------|
| `user_profile.txt` | Your persona, tone, and opinions | Settings tab (or manual) |
| `user_requests.txt` | Content queue — one item per line | Settings tab (or manual) |
| `data.txt` | Domain knowledge base | Research mode |
| `tweets.json` | X tweet style references | Settings → Scrape X feed |
| `comments.json` | X reply style references | Settings → Scrape X replies |
| `linkedin_profile.txt` | Your LinkedIn profile summary | LinkedIn scrape mode |
| `post_strategy.txt` | LinkedIn growth strategy | Settings tab (or manual) |
| `active_history.json` | X sessions history (prevents duplicate replies) | X active mode |
| `linkedin_history.json` | LinkedIn sessions history | LinkedIn active mode |
| `virality_notes.txt` | Engagement patterns you've observed on X | X active mode |
| `growth_log.json` | Follower count timeline | X active mode |

### Environment variables

| Variable | Required | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes | Google Gemini API key |

## Architecture

Each platform follows the same pattern:

```
load_context()        # Load persona, history, knowledge base
  ↓
build_task()          # Construct the LLM prompt for the selected mode
  ↓
setup_browser()       # Launch Chrome with a persistent profile (login saved)
  ↓
Agent.run()           # browser-use runs the task autonomously
  ↓
handle_agent_result() # Save output, update history, clean up
```

Schedulers wrap the `active` mode in a randomized loop, waiting between sessions to simulate natural usage.

## License

MIT — see [LICENSE](LICENSE)
