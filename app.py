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
st.set_page_config(page_title="Social Agent", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

    <style>
    :root {
        --bg:           #0c0c0c;
        --sidebar-bg:   #0f0f0f;
        --surface:      #141414;
        --surface-hi:   #1c1c1c;
        --border:       rgba(255,255,255,0.07);
        --border-hi:    rgba(255,255,255,0.13);
        --text:         #e0e0e0;
        --text-sub:     #848484;
        --text-muted:   #3e3e3e;
        --accent:       #3b82f6;
        --accent-bg:    rgba(59,130,246,0.1);
        --accent-ring:  rgba(59,130,246,0.25);
        --green:        #22c55e;
        --green-bg:     rgba(34,197,94,0.08);
        --amber:        #f59e0b;
        --amber-bg:     rgba(245,158,11,0.08);
        --red:          #ef4444;
        --sans:         'Outfit', system-ui, sans-serif;
        --mono:         'JetBrains Mono', 'Fira Mono', monospace;
        --r:            6px;
        --r-sm:         4px;
        --ease:         cubic-bezier(0.16, 1, 0.3, 1);
        --t:            0.18s;
    }

    /* ── Global reset ─────────────────────────────────── */
    html, body,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="block-container"],
    .main .block-container {
        background: var(--bg) !important;
        font-family: var(--sans) !important;
    }

    /* Keep header alive so the sidebar toggle button stays accessible */
    [data-testid="stHeader"] {
        background: var(--bg) !important;
        border-bottom: 1px solid var(--border) !important;
        height: 2.75rem !important;
    }
    /* Hide Streamlit branding inside the header, keep the sidebar toggle */
    [data-testid="stToolbarActions"],
    [data-testid="stMainMenuButton"],
    [data-testid="stDecoration"],
    .stDeployButton { display: none !important; }
    /* Style the sidebar toggle button in the header */
    [data-testid="stSidebarNavItems"],
    [data-testid="stSidebarCollapseButton"] button,
    header [data-testid="baseButton-header"] {
        background: transparent !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--r-sm) !important;
        color: var(--text-muted) !important;
    }
    header [data-testid="baseButton-header"]:hover {
        background: var(--surface-hi) !important;
        color: var(--text-sub) !important;
        border-color: var(--border-hi) !important;
    }

    * { font-family: var(--sans) !important; box-sizing: border-box; }
    .material-symbols-rounded, .material-icons, [data-testid="stIconMaterial"], [class*="stIcon"] {
        font-family: "Material Symbols Rounded", "Material Icons", sans-serif !important;
    }
    code, pre, samp, kbd, [data-testid="stCode"] * { font-family: var(--mono) !important; }

    /* ── Sidebar ──────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: var(--sidebar-bg) !important;
        border-right: 1px solid var(--border) !important;
        padding-top: 0 !important;
        transition: width 0.25s var(--ease), transform 0.25s var(--ease) !important;
    }
    section[data-testid="stSidebar"] > div {
        padding: 0 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0 !important;
        padding: 0 !important;
    }

    /* ── Sidebar collapse / expand button ─────────────── */
    [data-testid="stSidebarCollapseButton"] button {
        background: transparent !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--r-sm) !important;
        color: var(--text-muted) !important;
        transition: background var(--t) var(--ease), border-color var(--t) var(--ease), color var(--t) var(--ease) !important;
    }
    [data-testid="stSidebarCollapseButton"] button:hover {
        background: var(--surface-hi) !important;
        border-color: var(--border-hi) !important;
        color: var(--text-sub) !important;
    }
    [data-testid="stSidebarCollapsedControl"] {
        background: var(--bg) !important;
    }
    [data-testid="stSidebarCollapsedControl"] button {
        background: var(--surface) !important;
        border: 1px solid var(--border-hi) !important;
        border-radius: var(--r-sm) !important;
        color: var(--text-sub) !important;
        transition: background var(--t) var(--ease), border-color var(--t) var(--ease) !important;
    }
    [data-testid="stSidebarCollapsedControl"] button:hover {
        background: var(--surface-hi) !important;
        border-color: rgba(255,255,255,0.2) !important;
    }

    /* Sidebar brand */
    .sidebar-brand {
        padding: 1.5rem 1.25rem 1rem;
        border-bottom: 1px solid var(--border);
        margin-bottom: 0.5rem;
    }
    .sidebar-brand-name {
        font-size: 0.9375rem;
        font-weight: 700;
        color: var(--text);
        letter-spacing: -0.02em;
        display: block;
        line-height: 1;
    }
    .sidebar-brand-tag {
        font-size: 0.6875rem;
        color: var(--text-muted);
        letter-spacing: 0.07em;
        text-transform: uppercase;
        margin-top: 0.3rem;
        display: block;
    }

    /* Sidebar nav — style the radio as a nav menu */
    section[data-testid="stSidebar"] .stRadio { padding: 0 0.625rem; }
    section[data-testid="stSidebar"] .stRadio > label { display: none !important; }
    section[data-testid="stSidebar"] .stRadio [role="radiogroup"] {
        display: flex !important;
        flex-direction: column !important;
        gap: 1px !important;
    }
    /* Each nav item label */
    section[data-testid="stSidebar"] .stRadio [role="radiogroup"] label {
        padding: 0.5rem 0.625rem !important;
        border-radius: var(--r-sm) !important;
        cursor: pointer !important;
        border: none !important;
        background: transparent !important;
        transition: background var(--t) var(--ease) !important;
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        margin: 0 !important;
    }
    section[data-testid="stSidebar"] .stRadio [role="radiogroup"] label:hover {
        background: var(--surface-hi) !important;
    }
    /* Active nav item */
    section[data-testid="stSidebar"] .stRadio [role="radiogroup"] label:has(input:checked) {
        background: var(--accent-bg) !important;
    }
    /* Hide the BaseUI radio circle — it's a div[data-baseweb], not a real input */
    section[data-testid="stSidebar"] .stRadio [data-baseweb="radio"] {
        display: none !important;
    }
    /* Nav label text — VISIBLE, styled */
    section[data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"] {
        display: block !important;
    }
    section[data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"] p {
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        color: var(--text-sub) !important;
        margin: 0 !important;
        padding: 0 !important;
        display: block !important;
    }
    section[data-testid="stSidebar"] .stRadio [role="radiogroup"] label:hover [data-testid="stMarkdownContainer"] p {
        color: var(--text) !important;
    }
    section[data-testid="stSidebar"] .stRadio [role="radiogroup"] label:has(input:checked) [data-testid="stMarkdownContainer"] p {
        color: var(--accent) !important;
    }

    /* Sidebar section label */
    .sidebar-section {
        font-size: 0.625rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--text-muted);
        padding: 0 1.25rem;
        margin: 1rem 0 0.4rem;
        display: block;
    }

    /* Compact running service */
    .svc-item {
        display: flex;
        align-items: center;
        padding: 0.45rem 1.25rem;
        gap: 0.5rem;
    }
    .svc-dot {
        width: 5px; height: 5px;
        border-radius: 50%;
        background: var(--green);
        flex-shrink: 0;
        animation: pulse-dot 2s ease-in-out infinite;
    }
    .svc-label {
        font-size: 0.75rem;
        color: var(--text-sub);
        flex: 1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .svc-time {
        font-size: 0.675rem;
        color: var(--text-muted);
        font-family: var(--mono);
        white-space: nowrap;
    }
    @keyframes pulse-dot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50%       { opacity: 0.3; transform: scale(0.7); }
    }

    /* Sidebar bottom status */
    .sidebar-footer {
        padding: 0.9rem 1.25rem;
        border-top: 1px solid var(--border);
        margin-top: auto;
    }
    .api-status {
        font-size: 0.675rem;
        font-family: var(--mono);
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }
    .api-dot-ok  { width: 5px; height: 5px; border-radius: 50%; background: var(--green); flex-shrink: 0; }
    .api-dot-err { width: 5px; height: 5px; border-radius: 50%; background: var(--red); flex-shrink: 0; }

    /* Sidebar divider */
    section[data-testid="stSidebar"] hr {
        margin: 0.5rem 1.25rem !important;
        border-color: var(--border) !important;
    }

    /* Sidebar stop buttons — small */
    section[data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        color: var(--text-muted) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--r-sm) !important;
        font-size: 0.6875rem !important;
        font-weight: 500 !important;
        padding: 0.15rem 0.5rem !important;
        letter-spacing: 0.02em !important;
        transition: all var(--t) var(--ease) !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: var(--surface-hi) !important;
        color: var(--red) !important;
        border-color: var(--red) !important;
    }
    section[data-testid="stSidebar"] .stButton > button:active {
        transform: scale(0.97) !important;
    }

    /* ── Main content ─────────────────────────────────── */
    .main .block-container {
        padding: 2rem 2.5rem 3rem !important;
        max-width: 960px !important;
    }

    /* Page header */
    .page-header {
        margin-bottom: 1.75rem;
        padding-bottom: 1.25rem;
        border-bottom: 1px solid var(--border);
    }
    .page-title {
        font-size: 1.375rem;
        font-weight: 700;
        color: var(--text);
        letter-spacing: -0.025em;
        line-height: 1;
        margin: 0;
    }
    .page-subtitle {
        font-size: 0.75rem;
        color: var(--text-muted);
        margin-top: 0.3rem;
    }

    /* ── Typography ───────────────────────────────────── */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text) !important;
        letter-spacing: -0.022em !important;
    }
    h1 { font-size: 1.375rem !important; font-weight: 700 !important; }
    h2 { font-size: 1.0625rem !important; font-weight: 600 !important; }
    h3 { font-size: 0.9375rem !important; font-weight: 600 !important; }
    p, li, span, div, label { color: var(--text-sub) !important; }
    strong, b { color: var(--text) !important; font-weight: 600 !important; }

    /* Section label */
    .section-label {
        font-size: 0.65rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--text-muted);
        margin: 0 0 0.75rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--border);
        display: block;
    }

    /* ── Tabs (mode selector inside a page) ───────────── */
    div[data-testid="stTabs"] [role="tablist"] {
        border-bottom: 1px solid var(--border) !important;
        gap: 0 !important;
        margin-bottom: 1.25rem !important;
    }
    div[data-testid="stTabs"] button[role="tab"] {
        background: transparent !important;
        color: var(--text-muted) !important;
        font-size: 0.775rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.04em !important;
        text-transform: uppercase !important;
        padding: 0.5rem 1rem !important;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        transition: color var(--t) var(--ease), border-color var(--t) var(--ease) !important;
    }
    div[data-testid="stTabs"] button[role="tab"]:hover {
        color: var(--text-sub) !important;
    }
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        color: var(--text) !important;
        border-bottom-color: var(--accent) !important;
    }

    /* ── Buttons ──────────────────────────────────────── */
    .stButton > button {
        background: var(--surface-hi) !important;
        color: var(--text) !important;
        border: 1px solid var(--border-hi) !important;
        border-radius: var(--r-sm) !important;
        font-family: var(--sans) !important;
        font-size: 0.8125rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.01em !important;
        padding: 0.4rem 0.9rem !important;
        transition:
            background var(--t) var(--ease),
            border-color var(--t) var(--ease),
            transform 0.1s var(--ease),
            box-shadow var(--t) var(--ease) !important;
    }
    .stButton > button:hover {
        background: #242424 !important;
        border-color: rgba(255,255,255,0.2) !important;
        box-shadow: 0 2px 12px rgba(0,0,0,0.5) !important;
    }
    .stButton > button:active {
        transform: translateY(1px) scale(0.985) !important;
        box-shadow: none !important;
    }
    .stButton > button:disabled {
        opacity: 0.3 !important;
        cursor: not-allowed !important;
        transform: none !important;
    }

    /* ── Inputs ───────────────────────────────────────── */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        background: var(--surface) !important;
        border: 1px solid var(--border-hi) !important;
        border-radius: var(--r-sm) !important;
        color: var(--text) !important;
        font-size: 0.875rem !important;
        transition: border-color var(--t) var(--ease), box-shadow var(--t) var(--ease) !important;
    }
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px var(--accent-ring) !important;
        outline: none !important;
    }
    .stTextInput > div > div > input::placeholder,
    .stNumberInput > div > div > input::placeholder { color: var(--text-muted) !important; }

    /* ── Text Area ────────────────────────────────────── */
    .stTextArea > div > div > textarea {
        background: var(--surface) !important;
        border: 1px solid var(--border-hi) !important;
        border-radius: var(--r) !important;
        color: var(--text) !important;
        font-size: 0.8125rem !important;
        line-height: 1.65 !important;
        transition: border-color var(--t) var(--ease), box-shadow var(--t) var(--ease) !important;
    }
    .stTextArea > div > div > textarea:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px var(--accent-ring) !important;
        outline: none !important;
    }

    /* ── Radio (mode selector in main area) ───────────── */
    .stRadio [role="radiogroup"] { gap: 0.3rem !important; }
    .stRadio label {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--r-sm) !important;
        padding: 0.3rem 0.7rem !important;
        font-size: 0.775rem !important;
        color: var(--text-sub) !important;
        transition: all var(--t) var(--ease) !important;
        cursor: pointer !important;
    }
    .stRadio label:has(input:checked) {
        background: var(--accent-bg) !important;
        border-color: var(--accent) !important;
        color: var(--accent) !important;
    }

    /* ── Divider ──────────────────────────────────────── */
    hr { border-color: var(--border) !important; margin: 1.25rem 0 !important; }

    /* ── Alerts ───────────────────────────────────────── */
    [data-testid="stAlert"] {
        background: var(--surface) !important;
        border-radius: var(--r) !important;
        font-size: 0.8rem !important;
        padding: 0.65rem 1rem !important;
    }
    [data-testid="stAlert"] p { font-size: 0.8rem !important; }
    div[data-testid="stAlert"][class*="success"] {
        border-left: 2px solid var(--green) !important;
        background: var(--green-bg) !important;
    }
    div[data-testid="stAlert"][class*="warning"] {
        border-left: 2px solid var(--amber) !important;
        background: var(--amber-bg) !important;
    }
    div[data-testid="stAlert"][class*="error"]  { border-left: 2px solid var(--red) !important; }
    div[data-testid="stAlert"][class*="info"]   {
        border-left: 2px solid var(--accent) !important;
        background: var(--accent-bg) !important;
    }

    /* ── Captions / meta ──────────────────────────────── */
    [data-testid="stCaptionContainer"] p, .stCaption, small {
        color: var(--text-muted) !important;
        font-size: 0.7rem !important;
        font-family: var(--mono) !important;
    }

    /* ── Code blocks ──────────────────────────────────── */
    [data-testid="stCode"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--r) !important;
    }
    [data-testid="stCode"] code, [data-testid="stCode"] pre {
        font-size: 0.7rem !important;
        color: #6b7a8d !important;
    }

    /* ── Expander ─────────────────────────────────────── */
    [data-testid="stExpander"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--r) !important;
    }
    [data-testid="stExpander"] summary {
        font-size: 0.775rem !important;
        font-weight: 500 !important;
        color: var(--text-sub) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state ─────────────────────────────────────────────────────────────
if "processes" not in st.session_state:
    st.session_state.processes = {}


# ── Setup checks ──────────────────────────────────────────────────────────────
def get_api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
    if not key and ENV_FILE.exists():
        text = ENV_FILE.read_text()
        m = re.search(r"^(?:GOOGLE|GEMINI)_API_KEY=(.+)$", text, re.MULTILINE)
        if m:
            key = m.group(1).strip()
    return key


def write_api_key(key: str):
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
    return f"{h}h {m}m" if h else f"{m}m {s}s"


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


# ── X page ────────────────────────────────────────────────────────────────────
def render_x_page():
    st.markdown(
        '<div class="page-header">'
        '<p class="page-title">X</p>'
        '<p class="page-subtitle">Twitter / X automation</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    MODES = ["active", "post", "reply", "scrape", "replies", "market", "research", "custom", "login"]
    mode = st.radio("Mode", MODES, horizontal=True, key="x_mode")
    st.markdown("")

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

    if st.button("Run Once", key="x_run_once", disabled=is_running("x_once")):
        cmd = [sys.executable, "-m", "agents.x", mode]
        if config.get("theme"):            cmd += ["--theme", config["theme"]]
        if config.get("url"):              cmd += ["--url", config["url"]]
        if config.get("count"):            cmd += ["--count", str(config["count"])]
        if config.get("duration_minutes"): cmd += ["--duration", str(config["duration_minutes"])]
        if config.get("product"):          cmd += ["--product", config["product"]]
        if config.get("image"):            cmd += ["--image", config["image"]]
        if config.get("custom_prompt"):    cmd += ["--custom-prompt", config["custom_prompt"]]
        if config.get("domain"):           cmd += ["--domain", config["domain"]]
        start_process("x_once", cmd, config)
        st.rerun()

    if mode == "active":
        st.divider()
        st.markdown('<span class="section-label">Scheduler</span>', unsafe_allow_html=True)
        theme = st.text_input("Theme", "tech and AI", key="x_sched_theme")
        sched_cfg = scheduler_config("x_sched")
        sched_key = "x_scheduler"

        if is_running(sched_key):
            entry = st.session_state.processes[sched_key]
            c = entry["config"]
            st.success(
                f"Running  ·  {elapsed(sched_key)}  ·  "
                f"theme: \"{c.get('theme')}\"  ·  "
                f"every {c.get('interval_min')}–{c.get('interval_max')} min  ·  "
                f"PID {entry['pid']}"
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
                start_process(sched_key, cmd, {**sched_cfg, "theme": theme})
                st.rerun()

        with st.expander("Scheduler log"):
            st.code(log_tail("scheduler.log"), language="text")

    st.divider()
    st.markdown('<span class="section-label">Data Files</span>', unsafe_allow_html=True)
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


# ── LinkedIn page ─────────────────────────────────────────────────────────────
def render_linkedin_page():
    st.markdown(
        '<div class="page-header">'
        '<p class="page-title">LinkedIn</p>'
        '<p class="page-subtitle">LinkedIn automation</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    MODES = ["active", "post", "comment", "scrape", "custom", "login"]
    mode = st.radio("Mode", MODES, horizontal=True, key="li_mode")
    st.markdown("")

    config: dict = {}

    if mode == "active":
        config["theme"] = st.text_input("Theme", "software development", key="li_active_theme")
        config["duration_minutes"] = st.slider("Session duration (minutes)", 3, 30, 10, key="li_active_dur")
    elif mode == "post":
        config["theme"] = st.text_input("Theme", "software development", key="li_post_theme")
    elif mode == "comment":
        config["url"] = st.text_input("Post URL", key="li_comment_url")
        config["theme"] = st.text_input("Theme", "", key="li_comment_theme")
    elif mode == "custom":
        config["custom_prompt"] = st.text_area("Custom instructions", key="li_custom_prompt", height=100)

    if st.button("Run Once", key="li_run_once", disabled=is_running("li_once")):
        cmd = [sys.executable, "-m", "agents.linkedin", mode]
        if config.get("theme"):            cmd += ["--theme", config["theme"]]
        if config.get("url"):              cmd += ["--url", config["url"]]
        if config.get("duration_minutes"): cmd += ["--duration", str(config["duration_minutes"])]
        if config.get("custom_prompt"):    cmd += ["--custom-prompt", config["custom_prompt"]]
        start_process("li_once", cmd, config)
        st.rerun()

    if mode == "active":
        st.divider()
        st.markdown('<span class="section-label">Scheduler</span>', unsafe_allow_html=True)
        theme = st.text_input("Theme", "software development", key="li_sched_theme")
        sched_cfg = scheduler_config("li_sched")
        sched_key = "linkedin_scheduler"

        if is_running(sched_key):
            entry = st.session_state.processes[sched_key]
            c = entry["config"]
            st.success(
                f"Running  ·  {elapsed(sched_key)}  ·  "
                f"theme: \"{c.get('theme')}\"  ·  "
                f"every {c.get('interval_min')}–{c.get('interval_max')} min  ·  "
                f"PID {entry['pid']}"
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
                start_process(sched_key, cmd, {**sched_cfg, "theme": theme})
                st.rerun()

        with st.expander("Scheduler log"):
            st.code(log_tail("linkedin_scheduler.log"), language="text")

    st.divider()
    st.markdown('<span class="section-label">Data Files</span>', unsafe_allow_html=True)
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


# ── WhatsApp page ─────────────────────────────────────────────────────────────
def render_whatsapp_page():
    st.markdown(
        '<div class="page-header">'
        '<p class="page-title">WhatsApp</p>'
        '<p class="page-subtitle">WhatsApp auto-responder</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    MODES = ["auto-person", "auto-unread", "login"]
    mode = st.radio("Mode", MODES, horizontal=True, key="wa_mode")
    st.markdown("")

    if mode == "login":
        st.info("Opens WhatsApp Web in Chrome so you can scan the QR code.")
        if st.button("Open WhatsApp Login"):
            start_process("wa_login", [sys.executable, "-m", "agents.whatsapp", "--login"], {})
            st.rerun()

    elif mode == "auto-person":
        st.info(
            "Keeps the chat open and replies the moment a new message arrives. "
            "Learns your reply style from the conversation history. "
            "Start multiple instances to watch several contacts at once."
        )
        name = st.text_input("Contact name", placeholder="e.g. John", key="wa_person_name")
        session_min = st.slider(
            "Session length before auto-restart (minutes)", 15, 480, 120, key="wa_session_min",
            help="The agent watches the chat for this long, then restarts automatically.",
        )
        sched_key = f"wa_person_{name.strip().lower().replace(' ', '_')}" if name.strip() else "wa_person"

        if is_running(sched_key):
            st.success(f"Watching {name}  ·  {elapsed(sched_key)}")
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
                        [sys.executable, "-m", "agents.whatsapp",
                         "--auto-person", "--name", name.strip(),
                         "--session-minutes", str(session_min)],
                        {"name": name.strip(), "session_minutes": session_min},
                    )
                    st.rerun()

    elif mode == "auto-unread":
        st.warning(
            "**Replies to every unread message in your WhatsApp.** "
            "Best suited for business accounts. For personal use, create a WhatsApp list "
            "and enter the filter name below so the agent only replies to people in that list."
        )
        wa_filter = st.text_input(
            "Filter tab (optional)",
            placeholder="e.g. Favorites, Groups, or a custom list name",
            key="wa_unread_filter",
            help="WhatsApp filter tabs at the top of the chat list. Leave blank to sweep all chats.",
        )
        sched_key = "wa_unread"

        if is_running(sched_key):
            entry = st.session_state.processes[sched_key]
            f = entry["config"].get("filter")
            st.success(f"Running  ·  {elapsed(sched_key)}" + (f'  ·  filter: "{f}"' if f else ""))
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


# ── Settings page ─────────────────────────────────────────────────────────────

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
# Leave blank if you want the agent to post freely based on trending topics.
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


def render_settings_page():
    st.markdown(
        '<div class="page-header">'
        '<p class="page-title">Settings</p>'
        '<p class="page-subtitle">API key, persona, and data management</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    tab_api, tab_profile, tab_data = st.tabs(["API Key", "Profile", "Update Data"])

    with tab_api:
        current_key = get_api_key()
        masked = f"{current_key[:8]}{'*' * (len(current_key) - 8)}" if len(current_key) > 8 else ("set" if current_key else "")
        if current_key:
            st.success(f"GOOGLE_API_KEY is set  ({masked})")
        else:
            st.error("GOOGLE_API_KEY is not set")

        new_key = st.text_input(
            "Google API Key", type="password", placeholder="AIza...",
            help="Get your key at https://aistudio.google.com/app/apikey",
            key="settings_api_key",
        )
        if st.button("Save API Key", key="settings_save_key"):
            if new_key.strip():
                write_api_key(new_key.strip())
                st.success("Saved to .env")
                st.rerun()
            else:
                st.warning("Key cannot be empty")

    with tab_profile:
        st.caption("These files tell the agent who you are so it posts and replies in your voice.")
        st.markdown("")

        profile_val = read_data_file("user_profile.txt", PROFILE_PLACEHOLDER)
        profile_edited = st.text_area(
            "user_profile.txt — persona, tone, opinions",
            profile_val, height=240, key="settings_profile",
        )
        if st.button("Save Profile", key="settings_save_profile"):
            save_data_file("user_profile.txt", profile_edited)
            st.success("Saved user_profile.txt")

        st.markdown("")
        requests_val = read_data_file("user_requests.txt", REQUESTS_PLACEHOLDER)
        requests_edited = st.text_area(
            "user_requests.txt — content queue",
            requests_val, height=160, key="settings_requests",
        )
        if st.button("Save Requests", key="settings_save_requests"):
            save_data_file("user_requests.txt", requests_edited)
            st.success("Saved user_requests.txt")

        st.markdown("")
        strategy_val = read_data_file("post_strategy.txt", STRATEGY_PLACEHOLDER)
        strategy_edited = st.text_area(
            "post_strategy.txt — LinkedIn content strategy",
            strategy_val, height=200, key="settings_strategy",
        )
        if st.button("Save Strategy", key="settings_save_strategy"):
            save_data_file("post_strategy.txt", strategy_edited)
            st.success("Saved post_strategy.txt")

    with tab_data:
        st.caption("Build the agent's style references and knowledge base. Run these once to get started.")
        st.markdown("")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**Scrape X feed**")
            st.caption("Collects tweet examples for style matching.")
            count_x = st.number_input("Tweets to collect", 5, 50, 15, key="upd_x_count")
            if st.button("Run scrape", key="upd_x_scrape", disabled=is_running("upd_x_scrape")):
                start_process("upd_x_scrape", [sys.executable, "-m", "agents.x", "scrape", "--count", str(count_x)], {"count": count_x})
                st.rerun()

        with col2:
            st.markdown("**Scrape X replies**")
            st.caption("Collects reply examples from a thread.")
            reply_url = st.text_input("Tweet URL", key="upd_replies_url", placeholder="https://x.com/...")
            count_r = st.number_input("Replies to collect", 5, 50, 15, key="upd_replies_count")
            if st.button("Run scrape", key="upd_x_replies", disabled=is_running("upd_x_replies")):
                if reply_url.strip():
                    start_process("upd_x_replies", [sys.executable, "-m", "agents.x", "replies", "--url", reply_url.strip(), "--count", str(count_r)], {"url": reply_url, "count": count_r})
                    st.rerun()
                else:
                    st.warning("Enter a tweet URL first")

        with col3:
            st.markdown("**Update research**")
            st.caption("Fetches latest trends for your domain.")
            domain = st.text_input("Domain", "AI and Software Development", key="upd_research_domain")
            if st.button("Run research", key="upd_research", disabled=is_running("upd_research")):
                start_process("upd_research", [sys.executable, "-m", "agents.x", "research", "--domain", domain], {"domain": domain})
                st.rerun()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Brand
    st.markdown(
        '<div class="sidebar-brand">'
        '<span class="sidebar-brand-name">Social Agent</span>'
        '<span class="sidebar-brand-tag">X · LinkedIn · WhatsApp</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Navigation
    page = st.radio(
        "nav",
        ["X", "LinkedIn", "WhatsApp", "Settings"],
        label_visibility="collapsed",
        key="main_nav",
    )

    # Running services
    clean_dead_processes()
    if st.session_state.processes:
        st.markdown('<span class="sidebar-section">Running</span>', unsafe_allow_html=True)
        for key, entry in list(st.session_state.processes.items()):
            label = key.replace("_", " ").title()
            t = elapsed(key)
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(
                    f'<div class="svc-item">'
                    f'<span class="svc-dot"></span>'
                    f'<span class="svc-label">{label}</span>'
                    f'<span class="svc-time">{t}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with c2:
                if st.button("stop", key=f"sb_stop_{key}"):
                    stop_process(key)
                    st.rerun()

    # API status at bottom
    st.markdown(
        '<div style="position:relative;margin-top:2rem">'
        '<hr style="border-color:rgba(255,255,255,0.07);margin:0 1.25rem 0.75rem">'
        '</div>',
        unsafe_allow_html=True,
    )
    api_ok = bool(get_api_key())
    dot_cls = "api-dot-ok" if api_ok else "api-dot-err"
    api_txt = "API key configured" if api_ok else "No API key"
    st.markdown(
        f'<div class="sidebar-footer">'
        f'<div class="api-status">'
        f'<span class="{dot_cls}"></span>'
        f'<span style="color:var(--text-muted);font-family:var(--mono);font-size:0.675rem">{api_txt}</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


# ── Main content ──────────────────────────────────────────────────────────────
issues = []
if not get_api_key():
    issues.append("**GOOGLE_API_KEY** is not set")
missing = missing_files()
if missing:
    issues.append(f"Missing: {', '.join(missing)}")
if issues:
    st.warning(" · ".join(issues) + "  →  go to **Settings** to fix this.")

if page == "X":
    render_x_page()
elif page == "LinkedIn":
    render_linkedin_page()
elif page == "WhatsApp":
    render_whatsapp_page()
elif page == "Settings":
    render_settings_page()
