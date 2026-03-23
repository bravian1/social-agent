"""
Social Agent — Streamlit Dashboard
"""

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
ENV_FILE = PROJECT_ROOT / ".env"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Social Agent", layout="wide")
st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] { background-color: #0e0e0e; }
    [data-testid="stSidebar"]          { background-color: #141414; }
    h1, h2, h3, label, p              { color: #e8e8e8 !important; }
    .stButton>button {
        background-color: #1f1f1f;
        color: #e8e8e8;
        border: 1px solid #333;
        border-radius: 6px;
    }
    .stButton>button:hover { background-color: #2a2a2a; border-color: #555; }
    div[data-testid="stTabs"] button { color: #aaa; }
    div[data-testid="stTabs"] button[aria-selected="true"] { color: #e8e8e8; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state ─────────────────────────────────────────────────────────────
if "processes" not in st.session_state:
    st.session_state.processes = {}


# ── Setup checks ──────────────────────────────────────────────────────────────
def get_api_key() -> str:
    """Return the API key from environment or .env file."""
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
    if not key and ENV_FILE.exists():
        text = ENV_FILE.read_text()
        m = re.search(r"^(?:GOOGLE|GEMINI)_API_KEY=(.+)$", text, re.MULTILINE)
        if m:
            key = m.group(1).strip()
    return key


def write_api_key(key: str):
    """Write GOOGLE_API_KEY to .env, creating or updating the file."""
    env_text = ENV_FILE.read_text() if ENV_FILE.exists() else ""
    if re.search(r"^GOOGLE_API_KEY=", env_text, re.MULTILINE):
        env_text = re.sub(r"^GOOGLE_API_KEY=.*$", f"GOOGLE_API_KEY={key}", env_text, flags=re.MULTILINE)
    elif re.search(r"^GEMINI_API_KEY=", env_text, re.MULTILINE):
        env_text = re.sub(r"^GEMINI_API_KEY=.*$", f"GOOGLE_API_KEY={key}", env_text, flags=re.MULTILINE)
    else:
        env_text = env_text.rstrip("\n") + f"\nGOOGLE_API_KEY={key}\n"
    ENV_FILE.write_text(env_text)
    os.environ["GOOGLE_API_KEY"] = key


def missing_files() -> list[str]:
    """Return list of important data files that don't exist yet."""
    required = ["user_profile.txt", "user_requests.txt"]
    return [f for f in required if not (DATA_DIR / f).exists()]


# ── Process helpers ───────────────────────────────────────────────────────────
def start_process(key: str, cmd: list[str], config: dict):
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(PROJECT_ROOT),
    )
    st.session_state.processes[key] = {
        "proc": proc,
        "config": config,
        "started_at": datetime.now(),
        "pid": proc.pid,
    }


def stop_process(key: str):
    entry = st.session_state.processes.get(key)
    if entry:
        proc = entry["proc"]
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        del st.session_state.processes[key]


def clean_dead_processes():
    dead = [k for k, v in st.session_state.processes.items() if v["proc"].poll() is not None]
    for k in dead:
        del st.session_state.processes[k]


def is_running(key: str) -> bool:
    entry = st.session_state.processes.get(key)
    return entry is not None and entry["proc"].poll() is None


def elapsed(key: str) -> str:
    entry = st.session_state.processes.get(key)
    if not entry:
        return ""
    secs = int((datetime.now() - entry["started_at"]).total_seconds())
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"


# ── Data file helpers ─────────────────────────────────────────────────────────
def read_data_file(filename: str, default: str = "") -> str:
    path = DATA_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else default


def save_data_file(filename: str, content: str):
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / filename).write_text(content, encoding="utf-8")


def log_tail(log_filename: str, lines: int = 25) -> str:
    path = LOGS_DIR / log_filename
    if not path.exists():
        return "(no log yet)"
    text = path.read_text(encoding="utf-8")
    return "\n".join(text.strip().splitlines()[-lines:])


# ── Running services bar ──────────────────────────────────────────────────────
def render_running_services():
    clean_dead_processes()
    st.markdown("### Running Services")
    if not st.session_state.processes:
        st.caption("No services running.")
        st.divider()
        return
    for key, entry in list(st.session_state.processes.items()):
        col1, col2, col3 = st.columns([3, 5, 1])
        with col1:
            st.markdown(f"**{key.replace('_', ' ').title()}**")
        with col2:
            cfg = entry["config"]
            details = f"PID {entry['pid']} · {elapsed(key)}"
            if "theme" in cfg:
                details += f" · theme: \"{cfg['theme']}\""
            if "interval_min" in cfg:
                details += f" · every {cfg['interval_min']}–{cfg['interval_max']}m"
            st.caption(details)
        with col3:
            if st.button("Stop", key=f"stop_{key}"):
                stop_process(key)
                st.rerun()
    st.divider()


# ── Scheduler config widget ───────────────────────────────────────────────────
def scheduler_config(prefix: str) -> dict:
    c1, c2 = st.columns(2)
    with c1:
        interval_min = st.slider("Interval min (minutes)", 15, 180, 60, key=f"{prefix}_imin")
        duration_min = st.slider("Session duration min (minutes)", 3, 30, 5, key=f"{prefix}_dmin")
    with c2:
        interval_max = st.slider("Interval max (minutes)", 30, 360, 120, key=f"{prefix}_imax")
        duration_max = st.slider("Session duration max (minutes)", 5, 60, 15, key=f"{prefix}_dmax")
    return {
        "interval_min": interval_min,
        "interval_max": interval_max,
        "duration_min": duration_min,
        "duration_max": duration_max,
    }


# ── X tab ─────────────────────────────────────────────────────────────────────
def render_x_tab():
    MODES = ["active", "post", "reply", "scrape", "replies", "market", "research", "custom", "login"]
    mode = st.radio("Mode", MODES, horizontal=True, key="x_mode")

    config: dict = {}

    if mode == "active":
        config["theme"] = st.text_input("Theme", "tech and AI", key="x_active_theme")
        config["duration_minutes"] = st.slider("Session duration (minutes)", 3, 30, 10, key="x_active_dur")

    elif mode == "post":
        config["theme"] = st.text_input("Theme", "developer tools", key="x_post_theme")

    elif mode == "reply":
        config["url"] = st.text_input("Tweet URL", key="x_reply_url")
        config["theme"] = st.text_input("Theme", "", key="x_reply_theme")

    elif mode in ("scrape", "replies"):
        config["count"] = st.number_input("Count", 5, 50, 10, key="x_scrape_count")
        if mode == "replies":
            config["url"] = st.text_input("Tweet URL", key="x_replies_url")

    elif mode == "market":
        config["product"] = st.text_area("Product description", key="x_market_product", height=80)
        config["image"] = st.text_input("Image path (optional)", key="x_market_image")

    elif mode == "research":
        config["domain"] = st.text_input("Domain", "AI and Software Development", key="x_research_domain")

    elif mode == "custom":
        config["custom_prompt"] = st.text_area("Custom instructions", key="x_custom_prompt", height=100)

    # Run Once
    if st.button("Run Once", key="x_run_once", disabled=is_running("x_once")):
        cmd = [sys.executable, "-m", "agents.x", mode]
        if config.get("theme"):
            cmd += ["--theme", config["theme"]]
        if config.get("url"):
            cmd += ["--url", config["url"]]
        if config.get("count"):
            cmd += ["--count", str(config["count"])]
        if config.get("duration_minutes"):
            cmd += ["--duration", str(config["duration_minutes"])]
        if config.get("product"):
            cmd += ["--product", config["product"]]
        if config.get("image"):
            cmd += ["--image", config["image"]]
        if config.get("custom_prompt"):
            cmd += ["--custom-prompt", config["custom_prompt"]]
        if config.get("domain"):
            cmd += ["--domain", config["domain"]]
        start_process("x_once", cmd, config)
        st.success(f"Started X {mode} (PID {st.session_state.processes['x_once']['pid']})")

    # Scheduler (active mode only)
    if mode == "active":
        st.divider()
        st.markdown("#### Scheduler")
        theme = st.text_input("Scheduler theme", "tech and AI", key="x_sched_theme")
        sched_cfg = scheduler_config("x_sched")
        sched_key = "x_scheduler"

        if is_running(sched_key):
            st.success(f"Running · {elapsed(sched_key)}")
            entry = st.session_state.processes[sched_key]
            c = entry["config"]
            st.caption(
                f"Theme: \"{c.get('theme')}\" | "
                f"Interval: {c.get('interval_min')}–{c.get('interval_max')} min | "
                f"Duration: {c.get('duration_min')}–{c.get('duration_max')} min | "
                f"PID: {entry['pid']}"
            )
            if st.button("Stop Scheduler", key="x_sched_stop"):
                stop_process(sched_key)
                st.rerun()
        else:
            if st.button("Start Scheduler", key="x_sched_start"):
                cmd = [
                    sys.executable, "-m", "schedulers.x_scheduler",
                    "--theme", theme,
                    "--interval-min", str(sched_cfg["interval_min"]),
                    "--interval-max", str(sched_cfg["interval_max"]),
                    "--duration-min", str(sched_cfg["duration_min"]),
                    "--duration-max", str(sched_cfg["duration_max"]),
                ]
                full_cfg = {**sched_cfg, "theme": theme}
                start_process(sched_key, cmd, full_cfg)
                st.rerun()

        with st.expander("Scheduler log"):
            st.code(log_tail("scheduler.log"), language="text")

    # Data editors
    st.divider()
    st.markdown("#### Data Files")
    c1, c2 = st.columns(2)
    with c1:
        req_content = st.text_area(
            "user_requests.txt", read_data_file("user_requests.txt"), height=160, key="x_req"
        )
        if st.button("Save Requests", key="x_save_req"):
            save_data_file("user_requests.txt", req_content)
            st.success("Saved")
    with c2:
        profile_content = st.text_area(
            "user_profile.txt", read_data_file("user_profile.txt"), height=160, key="x_profile"
        )
        if st.button("Save Profile", key="x_save_profile"):
            save_data_file("user_profile.txt", profile_content)
            st.success("Saved")


# ── LinkedIn tab ──────────────────────────────────────────────────────────────
def render_linkedin_tab():
    MODES = ["active", "post", "comment", "scrape", "custom", "login"]
    mode = st.radio("Mode", MODES, horizontal=True, key="li_mode")

    config: dict = {}

    if mode == "active":
        config["theme"] = st.text_input("Theme", "software development", key="li_active_theme")
        config["duration_minutes"] = st.slider("Session duration (minutes)", 3, 30, 10, key="li_active_dur")

    elif mode == "post":
        config["theme"] = st.text_input("Theme", "software development", key="li_post_theme")

    elif mode == "comment":
        config["url"] = st.text_input("Post URL", key="li_comment_url")
        config["theme"] = st.text_input("Theme", "", key="li_comment_theme")

    elif mode == "scrape":
        pass

    elif mode == "custom":
        config["custom_prompt"] = st.text_area("Custom instructions", key="li_custom_prompt", height=100)

    if st.button("Run Once", key="li_run_once", disabled=is_running("li_once")):
        cmd = [sys.executable, "-m", "agents.linkedin", mode]
        if config.get("theme"):
            cmd += ["--theme", config["theme"]]
        if config.get("url"):
            cmd += ["--url", config["url"]]
        if config.get("duration_minutes"):
            cmd += ["--duration", str(config["duration_minutes"])]
        if config.get("custom_prompt"):
            cmd += ["--custom-prompt", config["custom_prompt"]]
        start_process("li_once", cmd, config)
        st.success(f"Started LinkedIn {mode} (PID {st.session_state.processes['li_once']['pid']})")

    if mode == "active":
        st.divider()
        st.markdown("#### Scheduler")
        theme = st.text_input("Scheduler theme", "software development", key="li_sched_theme")
        sched_cfg = scheduler_config("li_sched")
        sched_key = "linkedin_scheduler"

        if is_running(sched_key):
            st.success(f"Running · {elapsed(sched_key)}")
            entry = st.session_state.processes[sched_key]
            c = entry["config"]
            st.caption(
                f"Theme: \"{c.get('theme')}\" | "
                f"Interval: {c.get('interval_min')}–{c.get('interval_max')} min | "
                f"Duration: {c.get('duration_min')}–{c.get('duration_max')} min | "
                f"PID: {entry['pid']}"
            )
            if st.button("Stop Scheduler", key="li_sched_stop"):
                stop_process(sched_key)
                st.rerun()
        else:
            if st.button("Start Scheduler", key="li_sched_start"):
                cmd = [
                    sys.executable, "-m", "schedulers.linkedin_scheduler",
                    "--theme", theme,
                    "--interval-min", str(sched_cfg["interval_min"]),
                    "--interval-max", str(sched_cfg["interval_max"]),
                    "--duration-min", str(sched_cfg["duration_min"]),
                    "--duration-max", str(sched_cfg["duration_max"]),
                ]
                full_cfg = {**sched_cfg, "theme": theme}
                start_process(sched_key, cmd, full_cfg)
                st.rerun()

        with st.expander("Scheduler log"):
            st.code(log_tail("linkedin_scheduler.log"), language="text")

    st.divider()
    st.markdown("#### Data Files")
    c1, c2 = st.columns(2)
    with c1:
        strategy_content = st.text_area(
            "post_strategy.txt", read_data_file("post_strategy.txt"), height=160, key="li_strategy"
        )
        if st.button("Save Strategy", key="li_save_strategy"):
            save_data_file("post_strategy.txt", strategy_content)
            st.success("Saved")
    with c2:
        req_content = st.text_area(
            "user_requests.txt", read_data_file("user_requests.txt"), height=160, key="li_req"
        )
        if st.button("Save Requests", key="li_save_req"):
            save_data_file("user_requests.txt", req_content)
            st.success("Saved")


# ── WhatsApp tab ──────────────────────────────────────────────────────────────
def render_whatsapp_tab():
    MODES = ["auto-person", "auto-unread", "login"]
    mode = st.radio("Mode", MODES, horizontal=True, key="wa_mode")

    if mode == "login":
        st.info("Opens WhatsApp Web in Chrome so you can scan the QR code.")
        if st.button("Open WhatsApp Login"):
            start_process("wa_login", [sys.executable, "-m", "agents.whatsapp", "--login"], {})
            st.success("Browser opening...")

    elif mode == "auto-person":
        st.info(
            "Keeps the chat open and replies the moment a new message arrives — "
            "no polling, no delay. Learns your reply style from the conversation history itself. "
            "Tip: start multiple instances with different names to watch several contacts at once."
        )
        name = st.text_input("Contact name", placeholder='e.g. "John"', key="wa_person_name")
        session_min = st.slider(
            "Session length (minutes) before auto-restart",
            15, 480, 120, key="wa_session_min",
            help="The agent watches the chat for this long, then restarts automatically.",
        )
        sched_key = f"wa_person_{name.strip().lower().replace(' ', '_')}" if name.strip() else "wa_person"

        if is_running(sched_key):
            st.success(f"Watching {name} · {elapsed(sched_key)}")
            if st.button("Stop", key="wa_person_stop"):
                stop_process(sched_key)
                st.rerun()
        else:
            if st.button("Start", key="wa_person_start"):
                if not name.strip():
                    st.warning("Enter a contact name first")
                else:
                    start_process(
                        sched_key,
                        [
                            sys.executable, "-m", "agents.whatsapp",
                            "--auto-person", "--name", name.strip(),
                            "--session-minutes", str(session_min),
                        ],
                        {"name": name.strip(), "session_minutes": session_min},
                    )
                    st.rerun()

    elif mode == "auto-unread":
        st.warning(
            "**Auto-unread replies to every unread message in your WhatsApp.** "
            "This is aggressive and works best for business accounts. "
            "For personal use, **auto-person** with a list of specific contacts is strongly recommended — "
            "it gives you control over who the AI replies to."
        )
        wa_filter = st.text_input(
            "Filter tab (optional)",
            placeholder='e.g. Favorites, Groups, or a custom list name',
            key="wa_unread_filter",
            help="WhatsApp's filter tabs at the top of the chat list — All, Favorites, Unread, "
                 "Groups, or any custom list you created with the + button. "
                 "Leave blank to sweep all chats.",
        )
        sched_key = "wa_unread"

        if is_running(sched_key):
            entry = st.session_state.processes[sched_key]
            f = entry["config"].get("filter")
            st.success(f"Running · {elapsed(sched_key)}" + (f' · filter: "{f}"' if f else ""))
            if st.button("Stop", key="wa_unread_stop"):
                stop_process(sched_key)
                st.rerun()
        else:
            if st.button("Start", key="wa_unread_start"):
                cmd = [sys.executable, "-m", "agents.whatsapp", "--auto-unread"]
                if wa_filter.strip():
                    cmd += ["--filter", wa_filter.strip()]
                start_process(sched_key, cmd, {"filter": wa_filter.strip()})
                st.rerun()


# ── Settings tab ──────────────────────────────────────────────────────────────

PROFILE_PLACEHOLDER = """\
Career: Software Developer
Default tone: positive and open-minded
Style:
  - Reference code and tech naturally in conversation
  - Engage in friendly debates
  - Light sarcasm for bad ideas, genuine enthusiasm for good ones
  - Vary response lengths — short takes and longer threads both work
  - Be authentic, not performative

Opinions:
  - [Your hot takes — e.g. "Very frustrated with X company's Y product"]
  - [e.g. "Excited about Z technology, think it will change everything"]

Reactions:
  - Good ideas: genuine awe and enthusiasm
  - Wrong ideas: light, friendly sarcasm
  - General: curious, engaged, willing to learn\
"""

REQUESTS_PLACEHOLDER = """\
# Add one item per line — the agent picks one per active session, posts it, then removes it.
# Leave this blank if you want the agent to post freely based on trending topics.
#
# Examples:
# Just shipped a feature that cuts our API response time by 60% — here's how
# Hot take: most "AI wrappers" aren't solving the right problems
# Thread idea: 5 things I wish someone told me before building an MCP server\
"""

STRATEGY_PLACEHOLDER = """\
# Your LinkedIn content strategy — the agent uses this when deciding what to post.

Content pillars:
  1. [Your main topic, e.g. "AI and developer tools"]
  2. [Secondary topic, e.g. "Career pivot / backstory"]
  3. [Third topic, e.g. "Product building / lessons learned"]

Post cadence: 3x per week, daily comments

Tone: Professional but conversational. No corporate speak. Share real opinions.

What to avoid:
  - Generic AI hype without substance
  - Engagement-bait questions
  - Diminishing language ("just", "only", "little")\
"""


def render_settings_tab():
    # ── API Key ──
    st.markdown("### API Key")
    current_key = get_api_key()
    masked = f"{current_key[:8]}{'*' * (len(current_key) - 8)}" if len(current_key) > 8 else ("set" if current_key else "")
    if current_key:
        st.success(f"GOOGLE_API_KEY is set  ({masked})")
    else:
        st.error("GOOGLE_API_KEY is not set")

    new_key = st.text_input(
        "Google API Key",
        type="password",
        placeholder="AIza...",
        help="Get your key at https://aistudio.google.com/app/apikey",
        key="settings_api_key",
    )
    if st.button("Save API Key", key="settings_save_key"):
        if new_key.strip():
            write_api_key(new_key.strip())
            st.success("API key saved to .env")
            st.rerun()
        else:
            st.warning("Key cannot be empty")

    st.divider()

    # ── Persona setup ──
    st.markdown("### Your Profile")
    st.caption("These files tell the agent who you are so it posts and replies in your voice.")

    profile_val = read_data_file("user_profile.txt", PROFILE_PLACEHOLDER)
    profile_edited = st.text_area(
        "user_profile.txt — your persona, tone, and opinions",
        profile_val,
        height=240,
        key="settings_profile",
    )
    if st.button("Save Profile", key="settings_save_profile"):
        save_data_file("user_profile.txt", profile_edited)
        st.success("Saved user_profile.txt")

    st.markdown("")
    requests_val = read_data_file("user_requests.txt", REQUESTS_PLACEHOLDER)
    requests_edited = st.text_area(
        "user_requests.txt — content queue (one item per line)",
        requests_val,
        height=160,
        key="settings_requests",
    )
    if st.button("Save Requests", key="settings_save_requests"):
        save_data_file("user_requests.txt", requests_edited)
        st.success("Saved user_requests.txt")

    st.markdown("")
    strategy_val = read_data_file("post_strategy.txt", STRATEGY_PLACEHOLDER)
    strategy_edited = st.text_area(
        "post_strategy.txt — LinkedIn content strategy",
        strategy_val,
        height=200,
        key="settings_strategy",
    )
    if st.button("Save Strategy", key="settings_save_strategy"):
        save_data_file("post_strategy.txt", strategy_edited)
        st.success("Saved post_strategy.txt")

    st.divider()

    # ── Update Data ──
    st.markdown("### Update Data")
    st.caption("Run these once to build up the agent's style references and knowledge base.")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            "**Scrape X feed**",
            help="Scrolls your X feed and saves examples of how people in your field write posts. "
                 "The agent uses this to match the style and tone of real tweets.",
        )
        count_x = st.number_input("Tweets to collect", 5, 50, 15, key="upd_x_count")
        if st.button("Run scrape", key="upd_x_scrape", disabled=is_running("upd_x_scrape")):
            cmd = [sys.executable, "-m", "agents.x", "scrape", "--count", str(count_x)]
            start_process("upd_x_scrape", cmd, {"count": count_x})
            st.success("Scraping X feed…")

    with col2:
        st.markdown(
            "**Scrape X replies**",
            help="Collects reply examples from a specific tweet thread. "
                 "Teaches the agent how people respond and engage in your field — "
                 "useful for making replies feel natural and contextual.",
        )
        reply_url = st.text_input("Tweet URL", key="upd_replies_url", placeholder="https://x.com/...")
        count_r = st.number_input("Replies to collect", 5, 50, 15, key="upd_replies_count")
        if st.button("Run scrape", key="upd_x_replies", disabled=is_running("upd_x_replies")):
            if reply_url.strip():
                cmd = [sys.executable, "-m", "agents.x", "replies", "--url", reply_url.strip(), "--count", str(count_r)]
                start_process("upd_x_replies", cmd, {"url": reply_url, "count": count_r})
                st.success("Scraping replies…")
            else:
                st.warning("Enter a tweet URL first")

    with col3:
        st.markdown(
            "**Update research**",
            help="Searches the web for the latest news, releases, and trends in your domain. "
                 "The agent loads this as background knowledge so its posts and replies stay current. "
                 "Run this weekly or whenever you want a fresh knowledge base.",
        )
        domain = st.text_input("Domain", "AI and Software Development", key="upd_research_domain")
        if st.button("Run research", key="upd_research", disabled=is_running("upd_research")):
            cmd = [sys.executable, "-m", "agents.x", "research", "--domain", domain]
            start_process("upd_research", cmd, {"domain": domain})
            st.success("Researching…")


# ── Setup banner ──────────────────────────────────────────────────────────────
def render_setup_banner():
    issues = []
    if not get_api_key():
        issues.append("**GOOGLE_API_KEY** is not set")
    missing = missing_files()
    if missing:
        issues.append(f"Missing data files: {', '.join(missing)}")

    if issues:
        msg = "Setup needed — " + " · ".join(issues) + "  →  go to the **Settings** tab to fix this."
        st.warning(msg)


# ── Main layout ───────────────────────────────────────────────────────────────
st.title("Social Agent")
st.caption("AI-powered social media automation · X · LinkedIn · WhatsApp")

render_setup_banner()
st.divider()
render_running_services()

tab_x, tab_li, tab_wa, tab_settings = st.tabs(["X", "LinkedIn", "WhatsApp", "Settings"])

with tab_x:
    render_x_tab()

with tab_li:
    render_linkedin_tab()

with tab_wa:
    render_whatsapp_tab()

with tab_settings:
    render_settings_tab()
