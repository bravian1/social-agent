import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
LOGS_DIR = PROJECT_ROOT / 'logs'

# Default LiteLLM model string. Override with the LLM_MODEL env var.
DEFAULT_LLM_MODEL = 'gemini/gemini-flash-latest'

# Dedicated persistent browser profile (used when not reusing system Chrome).
BROWSER_PROFILE_DIR = Path.home() / '.config' / 'social-agent' / 'browser_profile'


def _env_flag(name: str) -> bool:
	"""Return True for truthy env values (1/true/yes/on)."""
	return os.getenv(name, '').strip().lower() in ('1', 'true', 'yes', 'on')


def build_browser_session(headless: bool = False):
	"""Build a BrowserSession, choosing the profile strategy from the environment.

	Set USE_SYSTEM_CHROME=true to reuse your existing, already-logged-in Chrome
	(no separate login needed). Otherwise a dedicated persistent profile is used.

	  USE_SYSTEM_CHROME        Reuse the real Chrome profile when truthy.
	  CHROME_PROFILE_DIRECTORY Profile subdir for system Chrome (e.g. "Default",
	                           "Profile 1"). Auto-detected if unset.
	  CHROME_EXECUTABLE_PATH   Explicit Chrome binary (overrides auto-detection).
	  CHROME_USER_DATA_DIR     Explicit Chrome user-data dir (overrides auto-detect).

	Note: close all Chrome windows first when reusing the system profile —
	browser-use launches Chrome in debug mode and can conflict with running ones.
	"""
	from browser_use import BrowserSession

	if _env_flag('USE_SYSTEM_CHROME'):
		profile = os.getenv('CHROME_PROFILE_DIRECTORY') or None
		exec_path = os.getenv('CHROME_EXECUTABLE_PATH')
		user_dir = os.getenv('CHROME_USER_DATA_DIR')
		# Explicit paths take precedence; otherwise auto-detect the system install.
		if exec_path or user_dir:
			kwargs = {'headless': headless}
			if exec_path:
				kwargs['executable_path'] = exec_path
			if user_dir:
				kwargs['user_data_dir'] = user_dir
			if profile:
				kwargs['profile_directory'] = profile
			return BrowserSession(**kwargs)
		return BrowserSession.from_system_chrome(profile_directory=profile, headless=headless)

	# Default: dedicated persistent profile. The Chrome user_data_dir natively
	# persists cookies/localStorage across runs, so the login survives. We do NOT
	# also pass storage_state — combining the two makes browser-use forcibly
	# overwrite the profile's cookies from the storage file.
	BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
	return BrowserSession(
		headless=headless,
		user_data_dir=str(BROWSER_PROFILE_DIR),
	)


def get_llm_api_key() -> str | None:
	"""Resolve the LLM API key from the environment.

	Prefers the provider-agnostic LLM_API_KEY, falling back to the legacy
	GOOGLE_API_KEY / GEMINI_API_KEY for backwards compatibility.
	"""
	return (
		os.getenv('LLM_API_KEY')
		or os.getenv('GOOGLE_API_KEY')
		or os.getenv('GEMINI_API_KEY')
	)


def _build_chat(model: str, temperature: float, api_key: str | None, api_base: str | None):
	"""Construct a ChatLiteLLM with the given routing."""
	from browser_use.llm.litellm import ChatLiteLLM

	return ChatLiteLLM(
		model=model,
		api_key=api_key,
		api_base=api_base or None,
		temperature=temperature,
	)


def get_llm(temperature: float = 0.7):
	"""Build the primary browser-use LLM from environment config via LiteLLM.

	All provider routing comes from the environment so any LiteLLM-supported
	provider can be swapped in without code changes:

	  LLM_MODEL     LiteLLM model string (default: gemini/gemini-flash-latest),
	                e.g. "openai/gpt-5", "anthropic/claude-sonnet-4-6".
	  LLM_API_KEY   API key (falls back to GOOGLE_API_KEY / GEMINI_API_KEY).
	  LLM_BASE_URL  Optional custom endpoint for OpenAI-compatible providers.
	"""
	return _build_chat(
		os.getenv('LLM_MODEL', DEFAULT_LLM_MODEL),
		temperature,
		get_llm_api_key(),
		os.getenv('LLM_BASE_URL'),
	)


def get_fallback_llm(temperature: float = 0.7):
	"""Build the backup LLM used when the primary fails, or None if unset.

	browser-use switches to this only after the primary exhausts its own
	retries, on rate-limit / auth / payment / server errors. Opt in by setting
	LLM_FALLBACK_MODEL; key/endpoint default to the primary's so a same-provider
	fallback needs only the model name.

	  LLM_FALLBACK_MODEL     LiteLLM model string for the backup (enables fallback).
	  LLM_FALLBACK_API_KEY   Optional key (defaults to the primary key).
	  LLM_FALLBACK_BASE_URL  Optional endpoint (defaults to LLM_BASE_URL).
	"""
	model = os.getenv('LLM_FALLBACK_MODEL')
	if not model:
		return None
	return _build_chat(
		model,
		temperature,
		os.getenv('LLM_FALLBACK_API_KEY') or get_llm_api_key(),
		os.getenv('LLM_FALLBACK_BASE_URL') or os.getenv('LLM_BASE_URL'),
	)


def get_extraction_llm():
	"""Build a separate, cheaper LLM for page content extraction, or None.

	Extraction only needs to pull text from a page, so a small/fast model saves
	cost. When unset, browser-use uses the primary LLM. Opt in with
	LLM_EXTRACTION_MODEL.

	  LLM_EXTRACTION_MODEL     LiteLLM model string for extraction (enables it).
	  LLM_EXTRACTION_API_KEY   Optional key (defaults to the primary key).
	  LLM_EXTRACTION_BASE_URL  Optional endpoint (defaults to LLM_BASE_URL).
	"""
	model = os.getenv('LLM_EXTRACTION_MODEL')
	if not model:
		return None
	return _build_chat(
		model,
		0.0,
		os.getenv('LLM_EXTRACTION_API_KEY') or get_llm_api_key(),
		os.getenv('LLM_EXTRACTION_BASE_URL') or os.getenv('LLM_BASE_URL'),
	)
