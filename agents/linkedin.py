#!/usr/bin/env python3
"""
LinkedIn Social Media Agent - Dynamic task builder for posting, commenting, and engaging.
"""

import argparse
import asyncio
import json
import logging
import os
import random
import re
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

from browser_use import Agent, BrowserSession
from browser_use.llm.google import ChatGoogle
from agents import DATA_DIR

load_dotenv()


def setup_environment(debug: bool):
	if not debug:
		os.environ['BROWSER_USE_SETUP_LOGGING'] = 'false'
		os.environ['BROWSER_USE_LOGGING_LEVEL'] = 'critical'
		logging.getLogger().setLevel(logging.CRITICAL)
	else:
		os.environ['BROWSER_USE_SETUP_LOGGING'] = 'true'
		os.environ['BROWSER_USE_LOGGING_LEVEL'] = 'info'


def load_context() -> str:
	"""Load style and research context for LinkedIn."""
	context = ""
	try:
		linkedin_posts_file = DATA_DIR / 'linkedin_posts.json'
		if linkedin_posts_file.exists():
			with open(linkedin_posts_file, 'r') as f:
				context += f"\n--- LINKEDIN STYLE REFERENCE (How professionals post on LinkedIn) ---\n{f.read()[:2000]}\n"

		data_file = DATA_DIR / 'data.txt'
		if data_file.exists():
			with open(data_file, 'r', encoding='utf-8') as f:
				context += f"\n--- GENERAL KNOWLEDGE & 2026 TRENDS (Domain Knowledge) ---\n{f.read()[:15000]}\n"

		profile_file = DATA_DIR / 'user_profile.txt'
		if profile_file.exists():
			with open(profile_file, 'r') as f:
				context += f"\n--- MY PERSONALITY & OPINIONS (Take these stances when relevant) ---\n{f.read()[:1500]}\n"

		requests_file = DATA_DIR / 'user_requests.txt'
		if requests_file.exists():
			content = requests_file.read_text(encoding='utf-8').strip()
			if content:
				context += f"\n--- USER REQUESTS (Things the user wants posted or discussed) ---\n{content}\n"

		profile_file = DATA_DIR / 'linkedin_profile.txt'
		if profile_file.exists():
			content = profile_file.read_text(encoding='utf-8').strip()
			if content:
				context += f"\n--- MY LINKEDIN PROFILE (Factual summary of who I am on LinkedIn) ---\n{content}\n"

		strategy_file = DATA_DIR / 'post_strategy.txt'
		if strategy_file.exists():
			content = strategy_file.read_text(encoding='utf-8').strip()
			if content:
				context += f"\n--- POST STRATEGY (Growth and engagement strategy for this account) ---\n{content}\n"

		virality_file = DATA_DIR / 'linkedin_virality_notes.txt'
		if virality_file.exists():
			content = virality_file.read_text(encoding='utf-8').strip()
			if content:
				context += f"\n--- VIRALITY PLAYBOOK (Patterns you've observed that drive engagement on LinkedIn) ---\n{content[-3000:]}\n"

		history_file = DATA_DIR / 'linkedin_history.json'
		if history_file.exists():
			with open(history_file, 'r') as f:
				history = json.load(f)
			all_posts: set = set()
			for entry in history:
				all_posts.update(entry.get('posts', []))
			recent = [f"[{e['timestamp']}] {e['action'][:300]}" for e in history[-10:]]
			posts_block = '\n'.join(all_posts) if all_posts else '(none yet)'
			context += (
				f"\n--- LINKEDIN HISTORY ---\n"
				f"Posts/threads you have already engaged with (NEVER engage with these again):\n"
				f"{posts_block}\n\n"
				f"Last {len(recent)} sessions:\n" + "\n".join(recent) + "\n"
			)
	except Exception:
		pass
	return context


def build_task(mode: str, config: dict) -> str:
	"""Dynamically build the agent task prompt based on mode and config."""
	theme = config.get('theme', '')
	url = config.get('url', '')
	context = load_context()

	theme_instruction = f'Topic/Theme to focus on: "{theme}"' if theme else 'Pick an interesting software development or tech topic.'

	if mode == 'scrape':
		return """
		Go to https://www.linkedin.com/in/me/ and scroll the page from top to bottom exactly once.
		While scrolling, collect what you see in each section.
		Then go to the activity tab and look at the first 5 posts.
		After that, write the summary below and you are finished. Do not go back to the profile.

		Only write what you literally read on the page. If a section is missing, say "Not present".
		Do not invent, infer, or add anything not explicitly written on the profile.

		Write the summary in this format:

		## Headline
		## Connections / Followers
		## About
		## Featured
		## Experience
		## Education
		## Skills
		## Recent Posts (first 5 — topic and engagement numbers)
		## First Impression (2-3 sentences on what this profile communicates at a glance)
		"""

	elif mode == 'post':
		return f"""
		You are a software developer with a real LinkedIn presence. You write authentic, professional posts
		that feel personal — not corporate fluff. Study the style references below, then craft and publish a post.

		{context}

		INSTRUCTIONS:
		{theme_instruction}

		1. Go to https://www.linkedin.com/feed/
		2. Click "Start a post" to open the post composer
		3. Draft a post that:
		   - Sounds like a real developer sharing a genuine thought or experience
		   - Is relevant to the theme above
		   - Is 2-5 sentences max — LinkedIn rewards concise, punchy posts
		   - Can include a short line break for readability but no walls of text
		   - Uses the "General Knowledge" context if it provides a useful specific example
		   - No hashtag spam (1-2 max if truly relevant)
		4. Publish the post

		CRITICAL RULES:
		- Do NOT sound like a recruiter, marketer, or LinkedIn influencer
		- No "I'm excited to announce" or "Thrilled to share" openers
		- No emojis unless they genuinely fit
		- After posting, output: POST_URL: <url of the published post if visible>
		"""

	elif mode == 'comment':
		target = f"Go to {url}" if url else "Go to https://www.linkedin.com/feed/ and find an interesting post related to the theme"
		return f"""
		You are a software developer engaging authentically on LinkedIn.

		{context}

		INSTRUCTIONS:
		{theme_instruction}

		1. {target}
		2. Read the post carefully and understand the full context
		3. Click the comment field
		4. Write a comment that:
		   - Adds genuine value — a real take, a useful addition, or a thoughtful question
		   - Sounds like a developer, not a LinkedIn bot
		   - Is 1-3 sentences — concise and direct
		   - Does NOT start with "Great post!" or "Thanks for sharing!"
		5. Post the comment

		CRITICAL RULES:
		- Be authentic. Disagree if you disagree. Add specifics if you have them.
		- No emojis unless they genuinely fit
		"""

	elif mode == 'active':
		# Derive own profile slug from post URLs logged in history
		own_profile = None
		history_file = DATA_DIR / 'linkedin_history.json'
		if history_file.exists():
			try:
				history = json.loads(history_file.read_text())
				for entry in reversed(history):
					for post_url in entry.get('posts', []):
						# LinkedIn post URLs: linkedin.com/posts/<slug>-... or feed/update/urn:li:activity:...
						m = re.search(r'linkedin\.com/in/([^/?]+)', post_url)
						if not m:
							m = re.search(r'linkedin\.com/posts/([^-]+)', post_url)
						if m:
							own_profile = m.group(1)
							break
					if own_profile:
						break
			except Exception:
				pass

		# Randomize session character
		check_notifications = random.random() < 0.4
		check_profile_stats = random.random() < 0.25
		engagement_count = random.randint(1, 4)
		scroll_style = random.choice([
			"scroll slowly, pausing on things that catch your eye",
			"scroll quickly at first, then slow down when something grabs you",
			"scroll a lot before stopping — you're picky today",
			"stop fairly early — you're not in the mood to browse much",
		])
		engage_style = random.choice([
			"You feel like being talkative — leave thoughtful comments where it makes sense.",
			"You're mostly just lurking. Mostly reactions (like/insightful), one comment at most.",
			"You're in a quick-hit mood — short punchy comments only if something is genuinely interesting.",
			"You feel opinionated today — push back or add your take if you disagree or have something to add.",
			"You're passive today — scroll a lot, engage only if something really stands out.",
		])
		profile_line = f"Your LinkedIn profile slug is '{own_profile}'. " if own_profile else "Check the profile icon or URL to confirm your own profile before engaging. "

		return f"""
		This is your LinkedIn account. You manage it like a real professional would. Act completely natural.
		{profile_line}Never comment on your own posts — if a notification is from yourself, skip it.

		{context}

		TODAY'S SESSION CHARACTER:
		- {engage_style}
		- When scrolling: {scroll_style}
		- Max new feed interactions this session: {engagement_count}

		{"PHASE 1 — CHECK NOTIFICATIONS:" if check_notifications else "PHASE 1 — SKIP NOTIFICATIONS (not in the mood today):"}
		{"1. Go to https://www.linkedin.com/notifications/" if check_notifications else "1. Skip notifications entirely this session. Go straight to the feed."}
		{"2. Scan for comments on YOUR posts or mentions. Ignore plain reactions." if check_notifications else ""}
		{"3. For each comment worth looking at:" if check_notifications else ""}
		{"   a. Click into the post to open the full thread. Read the full conversation — your original post, their comment, any replies." if check_notifications else ""}
		{"   b. Only after reading the full context, decide if replying makes sense." if check_notifications else ""}
		{"   c. CRITICAL: Check LINKEDIN HISTORY — if this post's URL is already there, you've already engaged here. Skip it." if check_notifications else ""}
		{"4. Handle at most 2 notifications. Don't spend the whole session here." if check_notifications else ""}

		PHASE 2 — BROWSE THE FEED:
		1. Go to https://www.linkedin.com/feed/ and start scrolling.
		2. When you find something worth engaging with:
		   - Check "LINKEDIN HISTORY" post list — if this post's URL is already there, skip it.
		   - Engaging with the same person on a different post is totally fine.
		   - Engage in whatever way fits your session character (comment, react, share).
		   - Sometimes reply to a comment on a post instead of the post itself.
		3. After each interaction, scroll on or return to feed.
		4. Stop once you've hit your max interactions, or if nothing stands out.

		PHASE 3 — DECIDE WHETHER TO POST:
		After browsing, decide on your own whether to publish an original post this session.
		- If "USER REQUESTS" has anything listed, pick ONE and post about it in your own voice. It MUST be posted — don't skip it.
		- If there are no user requests, post only if something from the feed genuinely inspired a thought. Otherwise skip it.
		- LinkedIn posts can be slightly longer than tweets but stay concise. No hashtag spam.

		{"PHASE 4 — CHECK YOUR PROFILE STATS:" if check_profile_stats else ""}
		{"Go to your profile page. Note your current connection/follower count and how recent posts performed." if check_profile_stats else ""}

		PHASE 5 — VIRALITY OBSERVATION (do this throughout the session):
		While browsing, pay attention to what's getting outsized engagement relative to follower count.
		Note patterns: hook type, post length, format (story vs list vs hot take), topic angle.
		You will report one sharp insight from this session at the end.

		INTERACTION RULES:
		- TOPIC FILTER: Only engage with posts about software development, tech, developer tools, or professional growth.
		- Be direct and specific. Generic LinkedIn engagement ("Great insight!") is worse than saying nothing.

		CRITICAL RULES:
		- Never mention you are an AI or automated. Be completely natural.
		- NEVER engage with the same post twice. The post URL list is your memory — trust it.
		- After finishing, output these lines (each on its own line):
		  POSTS: url1, url2, url3
		  REQUEST_DONE: <exact request text>  (only if you posted about a user request)
		  {"CONNECTIONS: <number>" if check_profile_stats else ""}
		  VIRALITY_INSIGHT: <one concrete pattern you observed — what made a specific post blow up and why>
		  Then a one-sentence summary of what you did.
		"""

	elif mode == 'market':
		from agents.market import load_market_strategy, load_market_context, build_market_task
		strategy = load_market_strategy()
		if not strategy:
			return """
			ERROR: No marketing strategy found. Please generate one first from the Marketing page
			in the dashboard, or run: python -m agents.market generate --product "your product"
			Go to https://www.linkedin.com/feed/ and do nothing. Report: "No strategy configured."
			"""
		market_context = load_market_context("linkedin")
		force_action = config.get('force_action', None)
		return build_market_task("linkedin", strategy, market_context, force_action)

	elif mode == 'custom':
		custom_prompt = config.get('custom_prompt', '')
		return f"""
		You are a digital agent controlling a browser.
		Follow the user's custom instructions below carefully.

		{context}

		INSTRUCTIONS:
		{custom_prompt}
		"""

	elif mode == 'login':
		# Check if user_profile.txt needs to be populated
		profile_file = DATA_DIR / 'user_profile.txt'
		profile_exists = profile_file.exists() and profile_file.read_text(encoding='utf-8').strip()

		# Check if linkedin_profile.txt needs to be populated
		li_profile_file = DATA_DIR / 'linkedin_profile.txt'
		li_profile_exists = li_profile_file.exists() and li_profile_file.read_text(encoding='utf-8').strip()

		profile_step = ""
		if not profile_exists or not li_profile_exists:
			profile_step = """
		AFTER LOGIN — QUICK PROFILE SCAN:
		Since this is the first time, do a quick scan of the user's profile. Keep it simple.

		6. Go to https://www.linkedin.com/in/me/
		7. Read ONLY what is visible on the page without clicking anything:
		   - Name and headline (at the top)
		   - Location and connections count
		   - About section (if present — many people don't have one, that's fine)
		   - Top skills (if visible)
		8. Scroll down to the Activity section. Read the preview text of the first 2-4 posts
		   that are visible WITHOUT clicking "Show all" or opening any post.
		   Just read the preview snippets as they appear on the page.
		9. That's it. Do NOT click into any post. Do NOT navigate away. Just read what you see.

		If the profile is sparse (no About, no posts, etc.) that is completely normal.
		Just note what IS there and move on.

		Output what you found in EXACTLY this format:

		PROFILE_DATA_START
		Name: <name from the header>
		Headline: <headline under the name>
		Handle: <the URL slug, e.g. "nyatorobravian" from linkedin.com/in/nyatorobravian>
		Location: <if visible>
		Connections: <number if visible>

		About: <copy the About text if present, otherwise write "Not provided">

		Skills: <list top skills if visible, otherwise "Not listed">

		Recent posts (preview snippets):
		  - <first post preview text, first 1-2 sentences as shown>
		  - <second post preview if visible>
		  - <third if visible>
		  (If no posts visible, write "No recent posts")
		PROFILE_DATA_END
		"""

		return f"""
		You are helping a user log into their LinkedIn account. Follow these steps:

		1. Navigate to https://www.linkedin.com/login
		2. Wait for the page to load completely.
		3. Pause and wait patiently for the user to enter their credentials and log in.
		4. Do not attempt to input anything yourself. Just wait.
		5. Once you clearly see the LinkedIn feed indicating a successful login, confirm it.
		{profile_step}
		"""

	else:
		raise ValueError(f"Unknown mode: {mode}")


def setup_browser() -> BrowserSession:
	"""Return a BrowserSession with a dedicated persistent profile for LinkedIn."""
	USER_DATA_DIR = Path.home() / '.config' / 'social-agent' / 'browser_profile'
	USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

	STORAGE_STATE_FILE = USER_DATA_DIR / 'storage_state.json'

	return BrowserSession(
		headless=False,
		user_data_dir=str(USER_DATA_DIR),
		storage_state=str(STORAGE_STATE_FILE) if STORAGE_STATE_FILE.exists() else None,
	)


def _build_user_profile_from_scan(raw_scan: str) -> str:
	"""Build a user_profile.txt from a raw LinkedIn profile scan, with sensible defaults."""
	# Extract what we can from the scan
	name = ''
	headline = ''
	handle = ''
	about = ''
	posts_section = ''

	for line in raw_scan.splitlines():
		line_stripped = line.strip()
		if line_stripped.startswith('Name:'):
			name = line_stripped[5:].strip()
		elif line_stripped.startswith('Headline:'):
			headline = line_stripped[9:].strip()
		elif line_stripped.startswith('Handle:'):
			handle = line_stripped[7:].strip()
		elif line_stripped.startswith('About:'):
			about = line_stripped[6:].strip()

	# Extract post previews
	in_posts = False
	post_previews = []
	for line in raw_scan.splitlines():
		if 'Recent posts' in line:
			in_posts = True
			continue
		if in_posts and line.strip().startswith('- '):
			preview = line.strip()[2:].strip()
			if preview and 'No recent posts' not in preview:
				post_previews.append(preview)

	# Build the profile with defaults
	role = headline if headline else 'Professional'
	if about and about != 'Not provided':
		about_line = f"\nAbout: {about}"
	else:
		about_line = ''

	# Default tone — human, not AI-sounding
	profile = f"""Name: {name}
Handle: {handle}
Career: {role}
{about_line}

Default tone: conversational and direct. Write like a real person sharing their actual thoughts — not a LinkedIn influencer or a corporate account.

Style:
  - Write short, punchy posts (2-4 sentences). Get to the point.
  - No "I'm thrilled to announce" or "Excited to share" openers
  - No emoji spam. One emoji max if it genuinely fits.
  - No hashtag walls. 1-2 hashtags max, only if truly relevant.
  - Share opinions and experiences, not platitudes
  - Use plain language. If you wouldn't say it out loud, don't post it.

NEVER use these AI giveaway patterns:
  - "X is not just Y, it is Z" (the diminishment pattern)
  - "In today's rapidly evolving landscape..."
  - "Let's dive in" / "Here's the thing" / "Hot take:"
  - Numbered lists with bold headers in every post
  - "I'm passionate about..." / "I firmly believe..."
  - Ending with a question to "drive engagement"
  - Any phrase that sounds like it came from a template
"""

	# Add post observations if we have them
	if post_previews:
		profile += "\nRecent post topics (for context on what this person posts about):\n"
		for p in post_previews[:4]:
			profile += f"  - {p[:150]}\n"

	return profile.strip()


def handle_agent_result(mode: str, result: str) -> str:
	if not result:
		return "❌ No output generated"

	if mode == 'scrape':
		profile_file = DATA_DIR / 'linkedin_profile.txt'
		profile_file.write_text(result, encoding='utf-8')
		return f"✅ Profile summary saved to {profile_file}"

	if mode == 'active':
		history_file = DATA_DIR / 'linkedin_history.json'
		history_data = []
		if history_file.exists():
			try:
				history_data = json.loads(history_file.read_text())
			except Exception:
				pass

		posts = []
		posts_match = re.search(r'POSTS:\s*(.+)', result)
		if posts_match:
			posts = [u.strip() for u in posts_match.group(1).split(',') if u.strip()]

		history_data.append({
			"timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			"action": result,
			"posts": posts,
		})
		history_file.write_text(json.dumps(history_data[-50:], indent=2))

		# Remove completed user requests
		done_match = re.search(r'REQUEST_DONE:\s*(.+)', result)
		if done_match:
			done_text = done_match.group(1).strip()
			requests_file = DATA_DIR / 'user_requests.txt'
			if requests_file.exists():
				lines = requests_file.read_text(encoding='utf-8').splitlines()
				remaining = [l for l in lines if l.strip() and l.strip() != done_text]
				requests_file.write_text('\n'.join(remaining) + ('\n' if remaining else ''), encoding='utf-8')

		# Append virality insight
		insight_match = re.search(r'VIRALITY_INSIGHT:\s*(.+)', result)
		if insight_match:
			virality_file = DATA_DIR / 'linkedin_virality_notes.txt'
			with open(virality_file, 'a', encoding='utf-8') as f:
				f.write(f"[{datetime.now().strftime('%Y-%m-%d')}] {insight_match.group(1).strip()}\n")

		# Log connection count
		connections_match = re.search(r'CONNECTIONS:\s*(\d[\d,]*)', result)
		if connections_match:
			count = int(connections_match.group(1).replace(',', ''))
			growth_file = DATA_DIR / 'linkedin_growth_log.json'
			growth_data = []
			if growth_file.exists():
				try:
					growth_data = json.loads(growth_file.read_text())
				except Exception:
					pass
			growth_data.append({"date": datetime.now().strftime('%Y-%m-%d %H:%M'), "connections": count})
			growth_file.write_text(json.dumps(growth_data, indent=2))

		return f"✅ Active action completed: {result}"

	if mode == 'market':
		from agents.market import handle_market_result
		return f"✅ {handle_market_result('linkedin', result)}"

	if mode == 'custom':
		return f"✅ Custom task completed.\n\nOutput:\n{result}"

	if mode == 'login':
		profile_match = re.search(r'PROFILE_DATA_START\s*\n(.*?)\nPROFILE_DATA_END', result, re.DOTALL)
		if profile_match:
			raw_profile = profile_match.group(1).strip()

			# Always save raw scan to linkedin_profile.txt
			li_profile_file = DATA_DIR / 'linkedin_profile.txt'
			li_profile_file.write_text(raw_profile, encoding='utf-8')

			# Build user_profile.txt with defaults if empty
			user_profile_file = DATA_DIR / 'user_profile.txt'
			if not user_profile_file.exists() or not user_profile_file.read_text(encoding='utf-8').strip():
				user_profile = _build_user_profile_from_scan(raw_profile)
				user_profile_file.write_text(user_profile, encoding='utf-8')

			return f"✅ Login completed. Profile scanned and saved"
		return f"✅ Login completed successfully"

	if mode in ['post', 'comment']:
		return f"✅ {mode.capitalize()} completed successfully"

	return result


async def run_agent(mode: str, config: dict) -> str:
	"""Main entry point: run the LinkedIn agent in the specified mode."""
	debug = config.get('debug', False)
	setup_environment(debug)

	api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
	if not api_key:
		return "❌ Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable"

	task = build_task(mode, config)
	temp = 0.7 if mode in ['post', 'comment', 'active', 'market'] else 0.1

	try:
		llm = ChatGoogle(model='gemini-flash-latest', temperature=temp, api_key=api_key)
		browser = setup_browser()
		agent = Agent(task=task, llm=llm, browser_session=browser)

		print(f'\n🚀 Starting LinkedIn [{mode}] task... (Close all Chrome windows first)')
		history = await agent.run()
		result = history.final_result()

		return handle_agent_result(mode, result)

	except Exception as e:
		msg = f"❌ Error: {str(e)}"
		if 'locked' in str(e).lower() or 'resource' in str(e).lower():
			msg += "\n💡 TIP: Close all Chrome windows before running."
		return msg


# ── CLI Entry Point ──────────────────────────────────────────────────────
async def main():
	parser = argparse.ArgumentParser(description='LinkedIn Social Media Agent')
	parser.add_argument('mode', choices=['scrape', 'post', 'comment', 'active', 'market', 'custom', 'login'],
	                    nargs='?', default='active', help='Agent mode')
	parser.add_argument('--theme', type=str, default='software development', help='Topic/theme to focus on')
	parser.add_argument('--url', type=str, default='', help='Target post URL')
	parser.add_argument('--count', type=int, default=10, help='Number of items to scrape')
	parser.add_argument('--duration', type=int, default=15, help='Active mode duration in minutes')
	parser.add_argument('--custom-prompt', type=str, default='', help='Instructions for custom mode')
	parser.add_argument('--product', type=str, default='', help='Product description for market mode')
	parser.add_argument('--force-action', type=str, default='', choices=['', 'product_post', 'industry_commentary', 'keyword_reply', 'engagement', 'educational', 'social_proof'],
	                    help='Force a specific action type for market mode')
	parser.add_argument('--debug', action='store_true', help='Debug mode')
	args = parser.parse_args()

	config = {
		'theme': args.theme,
		'url': args.url,
		'count': args.count,
		'duration_minutes': args.duration,
		'custom_prompt': args.custom_prompt,
		'product': args.product,
		'force_action': args.force_action or None,
		'debug': args.debug,
	}

	result = await run_agent(args.mode, config)
	print(result)


if __name__ == '__main__':
	asyncio.run(main())
