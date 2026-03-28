#!/usr/bin/env python3
"""
X.com Social Media Agent - Dynamic task builder for posting, replying, and engaging.
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

# Load environment variables
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
	"""Load style and research context from JSON files."""
	context = ""
	try:
		tweets_file = DATA_DIR / 'tweets.json'
		if tweets_file.exists():
			with open(tweets_file, 'r') as f:
				context += f"\n--- STYLE REFERENCE (How real humans tweet) ---\n{f.read()[:1500]}\n"

		comments_file = DATA_DIR / 'comments.json'
		if comments_file.exists():
			with open(comments_file, 'r') as f:
				context += f"\n--- REPLY STYLE REFERENCE (How humans reply) ---\n{f.read()[:1500]}\n"

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

		virality_file = DATA_DIR / 'virality_notes.txt'
		if virality_file.exists():
			content = virality_file.read_text(encoding='utf-8').strip()
			if content:
				context += f"\n--- VIRALITY PLAYBOOK (Patterns you've observed that drive engagement on X) ---\n{content[-3000:]}\n"

		market_history_file = DATA_DIR / 'market_history.json'
		if market_history_file.exists():
			with open(market_history_file, 'r') as f:
				context += f"\n--- MARKET HISTORY (What you have done so far for this product) ---\n{f.read()[:2000]}\n"

		active_history_file = DATA_DIR / 'active_history.json'
		if active_history_file.exists():
			with open(active_history_file, 'r') as f:
				history = json.load(f)
			# Collect all tweet IDs/URLs you've already replied to
			all_tweets: set = set()
			for entry in history:
				all_tweets.update(entry.get('tweets', []))
			recent = [f"[{e['timestamp']}] {e['action'][:300]}" for e in history[-10:]]
			tweets_block = '\n'.join(all_tweets) if all_tweets else '(none yet)'
			context += (
				f"\n--- ACTIVE MODE HISTORY ---\n"
				f"Tweets/threads you have already replied to (NEVER reply to these again):\n"
				f"{tweets_block}\n\n"
				f"Last {len(recent)} sessions:\n" + "\n".join(recent) + "\n"
			)
	except Exception:
		pass
	return context


def build_task(mode: str, config: dict) -> str:
	"""Dynamically build the agent task prompt based on mode and user config."""
	theme = config.get('theme', '')
	url = config.get('url', '')
	count = config.get('count', 10)
	context = load_context()

	theme_instruction = f'Topic/Theme to focus on: "{theme}"' if theme else 'Pick an interesting tech or AI topic.'
	typing_rule = "- KNOWN TYPING BUG: When typing on X, the first letter you type gets duplicated (e.g., 'HHello' instead of 'Hello'). To prevent this, ALWAYS start your drafted text with a single space character (e.g., ' Hello'), OR explicitly verify and delete the duplicated first letter before posting."

	if mode == 'scrape':
		return f"""
		1. Go to https://x.com/home
		2. Wait for the feed to load
		3. Scroll down slowly to load more content
		4. Extract data for at least {count} tweets from the feed
		5. For each tweet, capture:
		   - author (the handle or display name)
		   - content (the text of the tweet)
		   - timestamp (or how long ago it was posted)
		   - engagement (likes, retweets, etc. if visible)
		6. Format the final output as a valid JSON list of objects
		"""

	elif mode == 'replies':
		start_url = url if url else "https://x.com/home"
		return f"""
		1. Go to {start_url}
		2. If not already on a specific tweet page, find the first tweet in the feed and click it
		3. Extract the main tweet content and its author
		4. Scroll down slowly to load comments/replies
		5. Extract at least {count} replies, capturing:
		   - reply_author, reply_content, timestamp
		6. Format as JSON: {{"original_tweet": {{author, content}}, "replies": [...]}}
		"""

	elif mode == 'post':
		return f"""
		You are a human social media user. Study the style references below to understand
		how real people write tweets — casual, concise, authentic. Then draft and post a tweet.

		{context}

		INSTRUCTIONS:
		{theme_instruction}

		1. Go to https://x.com/home
		2. Click the tweet composition area (or the "Post" button)
		3. Draft a tweet that:
		   - Sounds completely human and natural (NOT robotic or corporate)
		   - Is about the theme above
		   - Matches the tone from the style references (short, punchy, authentic)
		   - Uses your personality and opinions from the context if relevant
		   - Uses the "General Knowledge" context if it provides useful specifics
		4. Type the tweet and click "Post" to publish it

		CRITICAL RULES:
		{typing_rule}
		"""

	elif mode == 'reply':
		target = f"Go to {url}" if url else "Go to https://x.com/home and click on an interesting tweet related to the theme"
		return f"""
		You are a human social media user. Study the style references below to understand
		how people reply to tweets — helpful, witty, conversational. Then reply to a tweet.

		{context}

		INSTRUCTIONS:
		{theme_instruction}

		1. {target}
		2. Read the tweet carefully
		3. Click the reply area
		4. Draft a reply that:
		   - Sounds completely human (NOT like an AI or bot)
		   - Is relevant to both the tweet and the theme
		   - Uses info from "General Knowledge" if it adds value
		   - Matches reply style references (concise, authentic, adds to the conversation)
		5. Click "Reply" / "Post" to publish
		
		CRITICAL RULES:
		{typing_rule}
		"""

	elif mode == 'active':
		# Derive own username from tweet URLs logged in history
		own_username = None
		active_history_file = DATA_DIR / 'active_history.json'
		if active_history_file.exists():
			try:
				history = json.loads(active_history_file.read_text())
				for entry in reversed(history):
					for url in entry.get('tweets', []):
						m = re.match(r'https://x\.com/([^/]+)/status/', url)
						if m:
							own_username = m.group(1)
							break
					if own_username:
						break
			except Exception:
				pass

		# Randomize session character so no two runs look alike
		check_notifications = random.random() < 0.0001   # ~40% of sessions
		check_profile_stats = random.random() < 0.25  # ~25% of sessions
		engagement_count = random.randint(1, 5)
		scroll_style = random.choice([
			"scroll slowly, pausing on things that catch your eye",
			"scroll quickly at first, then slow down when something grabs you",
			"scroll a lot before stopping — you're picky today",
			"stop fairly early — you're not in the mood to browse much",
		])
		engage_style = random.choice([
			"You feel like being talkative — leave thoughtful replies where it makes sense.",
			"You're mostly just lurking. Mostly likes and retweets, one reply at most.",
			"You're in a quick-hit mood — short punchy replies only if something is genuinely interesting.",
			"You feel opinionated today — push back or add a take if you disagree or have something to add.",
			"You're passive today — scroll a lot, engage only if something really stands out.",
		])
		username_line = f"Your username is @{own_username}. " if own_username else "Check the profile icon or URL bar to confirm your own username before engaging. "
		return f"""
		This is your X (Twitter) account. You manage it like a real person would. Act completely natural.
		{username_line}Never reply to your own posts — if a notification is from yourself, skip it.

		{context}

		TODAY'S SESSION CHARACTER:
		- {engage_style}
		- When scrolling: {scroll_style}
		- Max new feed interactions this session: {engagement_count}

		{"PHASE 1 — CHECK NOTIFICATIONS:" if check_notifications else "PHASE 1 — SKIP NOTIFICATIONS (not in the mood today):"}
		{"1. Go to https://x.com/notifications" if check_notifications else "1. Skip notifications entirely this session. Go straight to the feed."}
		{"2. Scan for replies to YOUR posts or mentions. Ignore likes and retweets." if check_notifications else ""}
		{"3. For each reply/mention worth looking at:" if check_notifications else ""}
		{"   a. Click into the tweet to open the full thread. Read the entire conversation — what you originally posted, what they replied, any follow-up messages since." if check_notifications else ""}
		{"   b. Only after reading the full context, decide if replying makes sense. Don't force a reply if the thread is already resolved or stale." if check_notifications else ""}
		{"   c. CRITICAL: Check ACTIVE MODE HISTORY — if this tweet's URL is already there, you've already replied in this thread. Skip it." if check_notifications else ""}
		{"4. Handle at most 1 notifications. Don't spend the whole session here." if check_notifications else ""}

		PHASE 2 — BROWSE THE FEED:
		1. Go to https://x.com/home and start scrolling.
		2. When you find something worth engaging with:
		   - Check "ACTIVE MODE HISTORY" tweet list — if this tweet's URL is already there, skip it.
		   - Engaging with the same person on a different tweet is totally fine.
		   - Don't engage with posts about AI.
		   - Engage in whatever way fits your session character (reply, like, retweet, quote).
		   - Sometimes reply to a comment inside a thread instead of the main tweet.
		3. After each interaction, click Home twice to refresh the feed.
		4. Stop once you've hit your max interactions, or if nothing stands out.

		PHASE 3 — DECIDE WHETHER TO POST:
		After browsing, decide on your own whether to post an original tweet this session.
		- If "USER REQUESTS" has anything listed, pick ONE and post about it in your own voice. It MUST be posted — don't skip it.
		- If there are no user requests, post only if something from the feed or the latest news genuinely inspired a thought. Otherwise skip it.
		- Keep posts short, opinionated, and human. No threads. No hashtag spam.

		{"PHASE 4 — CHECK YOUR PROFILE STATS:" if check_profile_stats else ""}
		{"Go to your profile page. Note your current follower count and how recent posts are performing (likes, replies, impressions if visible). You will report this at the end." if check_profile_stats else ""}

		PHASE 5 — VIRALITY OBSERVATION (do this throughout the session):
		While browsing, pay attention to what's getting outsized engagement relative to follower count.
		Note patterns: what kind of hook did it use? What was the structure? Was it a hot take, a story, a question, a contrarian view?
		You will report one sharp insight from this session at the end.

		INTERACTION RULES:
		- TOPIC FILTER: Only engage with tweets about general software development, project updates, or developer experiences.
		- GROK: On some occasions (only when it fits perfectly), playfully invoke @grok with biting sarcasm or curiosity.

		CRITICAL RULES:
		- Never mention you are an AI or automated. Be completely natural. Avoid emojis.
		- NEVER reply to the same tweet twice. The tweet URL list is your memory — trust it.
		{typing_rule}
		- After finishing, output these lines (each on its own line):
		  TWEETS: url1, url2, url3
		  REQUEST_DONE: <exact request text>  (only if you posted about a user request)
		  {"FOLLOWERS: <number>" if check_profile_stats else ""}
		  VIRALITY_INSIGHT: <one concrete pattern you observed — what made a specific tweet blow up and why>
		  Then a one-sentence summary of what you did.
		"""

	elif mode == 'market':
		from agents.market import load_market_strategy, load_market_context, build_market_task
		strategy = load_market_strategy()
		if not strategy:
			return """
			ERROR: No marketing strategy found. Please generate one first from the Marketing page
			in the dashboard, or run: python -m agents.market generate --product "your product"
			Go to https://x.com/home and do nothing. Report: "No strategy configured."
			"""
		market_context = load_market_context("x")
		force_action = config.get('force_action', None)
		image_path = config.get('image', '')
		image_instruction = f"\nAn image for the product is located at: {image_path}. If you decide to make a new post, use this image." if image_path else ""
		return build_market_task("x", strategy, market_context, force_action) + image_instruction

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
		return """
		You are helping a user log into their X (Twitter) account. Follow these steps:

		1. Navigate to https://x.com/login
		2. Wait for the page to load completely.
		3. Pause and wait patiently for the user to enter their credentials and log in.
		4. Do not attempt to input anything yourself. Just wait.
		5. Once you clearly see the X home feed indicating a successful login, confirm it.
		"""

	else:
		raise ValueError(f"Unknown mode: {mode}")


def setup_browser() -> BrowserSession:
	"""Return a BrowserSession instance configured with a dedicated profile for the agent."""
	USER_DATA_DIR = Path.home() / '.config' / 'social-agent' / 'browser_profile'
	USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

	# Storage state file for cookies
	STORAGE_STATE_FILE = USER_DATA_DIR / 'storage_state.json'
	

	
	browser_session = BrowserSession(
			headless=False,  # Show browser
			user_data_dir=str(USER_DATA_DIR),  # Use persistent profile directory
			storage_state=str(STORAGE_STATE_FILE) if STORAGE_STATE_FILE.exists() else None,  # Use saved cookies/session
		)
	return browser_session


def handle_agent_result(mode: str, result: str) -> str:
	if not result:
		return "❌ No output generated"

	# Save output for scrape/replies modes
	if mode in ['scrape', 'replies']:
		output_file = DATA_DIR / ('tweets.json' if mode == 'scrape' else 'comments.json')
		
		# Try to parse new result as JSON
		new_data = result
		try:
			clean_result = result.strip()
			if clean_result.startswith('```json'):
				clean_result = clean_result[7:-3].strip()
			elif clean_result.startswith('```'):
				clean_result = clean_result[3:-3].strip()
			new_data = json.loads(clean_result)
		except Exception:
			pass  # Keep as string if not JSON

		existing_data = []
		if output_file.exists():
			try:
				with open(output_file, 'r', encoding='utf-8') as f:
					content = json.load(f)
					if isinstance(content, list):
						existing_data = content
					else:
						existing_data = [content]
			except Exception:
				pass  # Start fresh if invalid JSON or empty

		if isinstance(new_data, list):
			existing_data.extend(new_data)
		else:
			existing_data.append(new_data)

		with open(output_file, 'w', encoding='utf-8') as f:
			json.dump(existing_data, f, indent=2, ensure_ascii=False)
			
		return f"✅ Saved to {output_file}"

	# Market mode uses shared handler
	if mode == 'market':
		from agents.market import handle_market_result
		return f"✅ {handle_market_result('x', result)}"

	# Save history for active mode
	if mode == 'active':
		history_file = DATA_DIR / 'active_history.json'
		history_data = []
		if history_file.exists():
			try:
				with open(history_file, 'r') as f:
					history_data = json.load(f)
			except Exception:
				pass
		
		# Extract tweet URLs the agent reported engaging with
		tweets = []
		tweet_match = re.search(r'TWEETS:\s*(.+)', result)
		if tweet_match:
			tweets = [u.strip() for u in tweet_match.group(1).split(',') if u.strip()]

		history_data.append({
			"timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			"action": result,
			"tweets": tweets,
		})

		with open(history_file, 'w') as f:
			json.dump(history_data[-50:], f, indent=2)

		if mode == 'active':
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
				insight = insight_match.group(1).strip()
				virality_file = DATA_DIR / 'virality_notes.txt'
				with open(virality_file, 'a', encoding='utf-8') as f:
					f.write(f"[{datetime.now().strftime('%Y-%m-%d')}] {insight}\n")

			# Log follower count
			followers_match = re.search(r'FOLLOWERS:\s*(\d[\d,]*)', result)
			if followers_match:
				count = int(followers_match.group(1).replace(',', ''))
				growth_file = DATA_DIR / 'growth_log.json'
				growth_data = []
				if growth_file.exists():
					try:
						growth_data = json.loads(growth_file.read_text())
					except Exception:
						pass
				growth_data.append({"date": datetime.now().strftime('%Y-%m-%d %H:%M'), "followers": count})
				growth_file.write_text(json.dumps(growth_data, indent=2))

		return f"✅ {mode.capitalize()} action completed: {result}"

	if mode == 'custom':
		return f"✅ Custom task completed.\n\nOutput:\n{result}"

	if mode in ['post', 'reply', 'login']:
		return f"✅ {mode.capitalize()} completed successfully"

	return result


async def run_agent(mode: str, config: dict) -> str:
	"""Main entry point: run the X agent in the specified mode."""
	debug = config.get('debug', False)
	setup_environment(debug)

	api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
	if not api_key:
		return "❌ Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable"

	# Research is handled separately (no browser needed)
	if mode == 'research':
		from agents.research import perform_research
		result = await perform_research(api_key, config.get('count', 10))
		return result if result else "❌ Research failed"

	task = build_task(mode, config)

	# Higher temperature for creative tasks
	temp = 0.7 if mode in ['post', 'reply', 'active', 'market'] else 0.1

	try:
		llm = ChatGoogle(model='gemini-flash-latest', temperature=temp, api_key=api_key)
		browser = setup_browser()
		agent = Agent(task=task, llm=llm, browser_session=browser)

		print(f'\n🚀 Starting [{mode}] task... (Close all Chrome windows first)')
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
	parser = argparse.ArgumentParser(description='X.com Social Media Agent')
	parser.add_argument('mode', choices=['scrape', 'replies', 'post', 'reply', 'active', 'research', 'custom', 'market', 'login'],
	                    nargs='?', default='scrape', help='Agent mode')
	parser.add_argument('--theme', type=str, default='coding projects', help='Topic/theme to focus on')
	parser.add_argument('--url', type=str, default='', help='Target tweet URL')
	parser.add_argument('--count', type=int, default=10, help='Number of items')
	parser.add_argument('--duration', type=int, default=15, help='Active mode duration in minutes')
	parser.add_argument('--custom-prompt', type=str, default='', help='Instructions for custom mode')
	parser.add_argument('--product', type=str, default='', help='Product description for market mode')
	parser.add_argument('--image', type=str, default='', help='Image path for market mode')
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
		'image': args.image,
		'force_action': args.force_action or None,
		'debug': args.debug,
	}

	result = await run_agent(args.mode, config)
	print(result)


if __name__ == '__main__':
	asyncio.run(main())
