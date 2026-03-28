#!/usr/bin/env python3
"""
Market Mode — Shared cross-platform marketing logic.
Generates strategies, builds session prompts, and loads marketing context
for both X and LinkedIn agents.
"""

import argparse
import asyncio
import json
import os
import random
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from agents import DATA_DIR

load_dotenv()

ACTION_TYPES = [
	"product_post",
	"industry_commentary",
	"keyword_reply",
	"engagement",
	"educational",
	"social_proof",
]

ACTION_LABELS = {
	"product_post": "Product Post",
	"industry_commentary": "Industry Commentary",
	"keyword_reply": "Keyword Reply",
	"engagement": "Engagement",
	"educational": "Educational",
	"social_proof": "Social Proof",
}


# ── Strategy generation ──────────────────────────────────────────────────

async def generate_strategy(api_key: str, business_description: str, max_retries: int = 3) -> dict:
	"""Use Gemini with google_search to research the business and produce a marketing strategy.

	Validates that the model actually used Google Search (grounding) and retries if not.
	"""
	from google import genai
	from google.genai.types import GenerateContentConfig, Tool, GoogleSearch

	client = genai.Client(api_key=api_key)
	model_id = "gemini-3-flash-preview"
	tools = [Tool(google_search=GoogleSearch())]

	current_date = datetime.now().strftime("%B %d, %Y")

	prompt = f"""
IMPORTANT: You MUST use Google Search for EVERY factual claim in your response.
Do NOT rely on your training data. Search the web first, then answer based on what you find.

You are a social media strategist. A client has described their business below.
Your job is to research it thoroughly using Google Search and produce a marketing strategy.

Current date: {current_date}

BUSINESS DESCRIPTION:
"{business_description}"

MANDATORY RESEARCH STEPS — you MUST perform ALL of these searches before writing anything:
1. Search for the exact product/business name to understand what it does and who uses it.
2. Search for "[product space] competitors {current_date[:4]}" to find current competitors.
3. Search for "[product space] trending topics {current_date[:4]}" to find what people are discussing right now.
4. Search for "[product space] tools {current_date[:4]}" to find the latest tools and platforms.
5. Search for "[product space] hashtags twitter" to find keywords people actually use.

AFTER completing all searches, produce your output as a JSON object.

CRITICAL: Every company name, tool name, model name, and keyword in your output MUST come from
your search results. If you cannot find something via search, do not guess or make it up.

OUTPUT FORMAT — return ONLY a valid JSON object (no markdown, no code fences, no explanation):
{{
  "business_description": "<the original description, cleaned up>",
  "brand_voice": "<2-3 sentences describing the ideal tone>",
  "target_audience": ["<segment 1>", "<segment 2>", "<segment 3>", "<segment 4>"],
  "keywords": ["<keyword1>", "<keyword2>", "<keyword3>", "<keyword4>", "<keyword5>", "<keyword6>", "<keyword7>", "<keyword8>"],
  "competitors": ["<competitor1>", "<competitor2>", "<competitor3>"],
  "content_pillars": [
    {{"name": "Product Updates", "description": "<specific to THIS product based on search results>"}},
    {{"name": "Industry Commentary", "description": "<based on current trends you found via search>"}},
    {{"name": "Social Proof", "description": "<types of proof relevant to THIS product>"}},
    {{"name": "Educational", "description": "<tutorials/tips that make sense based on what users are searching for>"}}
  ],
  "posting_cadence": {{
    "x": {{"posts_per_week": 5, "replies_per_session": 3}},
    "linkedin": {{"posts_per_week": 3, "comments_per_session": 2}}
  }},
  "platforms": ["x", "linkedin"],
  "generated_at": "{datetime.now().isoformat()}",
  "last_modified": "{datetime.now().isoformat()}"
}}
"""

	for attempt in range(1, max_retries + 1):
		print(f"  Attempt {attempt}/{max_retries}...")

		response = await client.aio.models.generate_content(
			model=model_id,
			contents=prompt,
			config=GenerateContentConfig(
				tools=tools,
				temperature=0.4,
			)
		)

		# Check grounding metadata to verify search was actually used
		grounded = False
		search_queries = []
		sources = []

		candidate = response.candidates[0] if response.candidates else None
		if candidate and candidate.grounding_metadata:
			meta = candidate.grounding_metadata
			if meta.web_search_queries:
				search_queries = list(meta.web_search_queries)
			if meta.grounding_chunks:
				sources = [
					{"title": c.web.title, "url": c.web.uri}
					for c in meta.grounding_chunks
					if c.web
				]
			# Consider it grounded if at least 2 search queries were made
			grounded = len(search_queries) >= 2

		if grounded:
			print(f"  Grounding verified: {len(search_queries)} searches, {len(sources)} sources")
			for q in search_queries[:5]:
				print(f"    Searched: {q}")
			for s in sources[:5]:
				print(f"    Source: {s['title']} — {s['url']}")
		else:
			print(f"  WARNING: Response was NOT grounded (no search queries detected)")
			if attempt < max_retries:
				print(f"  Retrying...")
				continue
			else:
				print(f"  Max retries reached. Using ungrounded response (may contain hallucinations).")

		result = response.text.strip()
		# Strip markdown code fences if present
		if result.startswith('```'):
			result = re.sub(r'^```(?:json)?\s*', '', result)
			result = re.sub(r'\s*```$', '', result)

		strategy = json.loads(result)

		# Attach grounding metadata to strategy for transparency
		strategy['_grounding'] = {
			'search_queries': search_queries,
			'sources': [s['url'] for s in sources],
			'grounded': grounded,
		}

		return strategy

	# Should not reach here, but just in case
	raise RuntimeError("Failed to generate strategy after all retries")


def save_strategy(strategy: dict):
	"""Save strategy to data/market_strategy.json."""
	DATA_DIR.mkdir(exist_ok=True)
	path = DATA_DIR / 'market_strategy.json'
	strategy['last_modified'] = datetime.now().isoformat()
	with open(path, 'w', encoding='utf-8') as f:
		json.dump(strategy, f, indent=2, ensure_ascii=False)
	return path


def derive_research_domain(strategy: dict) -> str:
	"""Derive a research domain string from the strategy for use with research.py.

	Combines target audience context and keywords into a domain description
	that research.py can use to populate data.txt with relevant knowledge.
	"""
	desc = strategy.get('business_description', '')
	keywords = strategy.get('keywords', [])
	audience = strategy.get('target_audience', [])

	# Build a concise domain from the business context
	# e.g. "Handmade Knitwear" -> "Handmade Knitwear, Fashion, and Etsy Selling"
	# e.g. "Edge ML CLI tool" -> "Edge AI, MLOps, and On-device Inference"
	parts = []
	if keywords:
		parts.extend(keywords[:3])
	if audience:
		# Add the space/industry the audience is in
		parts.append(audience[0])

	if parts:
		return ', '.join(parts)
	# Fallback to a trimmed version of the business description
	return desc[:80] if desc else "General Business and Marketing"


async def run_domain_research(api_key: str, domain: str):
	"""Run research.py for the given domain and save results to data.txt."""
	from agents.research import perform_research

	result = await perform_research(api_key, domain)
	if result:
		data_file = DATA_DIR / 'data.txt'
		data_file.write_text(result, encoding='utf-8')
		print(f'Domain knowledge saved to {data_file}')
	else:
		print('Warning: Research returned no results. data.txt not populated.')


def load_market_strategy() -> dict | None:
	"""Load strategy from data/market_strategy.json. Returns None if not found."""
	path = DATA_DIR / 'market_strategy.json'
	if not path.exists():
		return None
	try:
		with open(path, 'r', encoding='utf-8') as f:
			return json.load(f)
	except (json.JSONDecodeError, IOError):
		return None


# ── Context loading ──────────────────────────────────────────────────────

def load_market_context(platform: str) -> str:
	"""Build context string from strategy, history, profile, and virality notes."""
	context = ""

	# Strategy
	strategy = load_market_strategy()
	if strategy:
		context += f"\n--- MARKETING STRATEGY ---\n"
		context += f"Brand Voice: {strategy.get('brand_voice', 'N/A')}\n"
		context += f"Target Audience: {', '.join(strategy.get('target_audience', []))}\n"
		context += f"Keywords: {', '.join(strategy.get('keywords', []))}\n"
		context += f"Competitors: {', '.join(strategy.get('competitors', []))}\n"
		pillars = strategy.get('content_pillars', [])
		if pillars:
			context += "Content Pillars:\n"
			for p in pillars:
				context += f"  - {p['name']}: {p['description']}\n"
		cadence = strategy.get('posting_cadence', {}).get(platform, {})
		if cadence:
			context += f"Cadence ({platform}): {cadence.get('posts_per_week', '?')} posts/week, {cadence.get('replies_per_session', cadence.get('comments_per_session', '?'))} replies/session\n"

	# Market history (platform-specific)
	history_file = DATA_DIR / f'market_history_{platform}.json'
	if history_file.exists():
		try:
			with open(history_file, 'r') as f:
				history = json.load(f)
			recent = [f"[{e['timestamp']}] type={e.get('action_type', '?')} pillar={e.get('pillar_used', '?')} — {e.get('summary', e.get('action', ''))[:200]}" for e in history[-10:]]
			# Track which pillars and action types were used recently
			recent_pillars = [e.get('pillar_used', '') for e in history[-10:] if e.get('pillar_used')]
			recent_actions = [e.get('action_type', '') for e in history[-10:] if e.get('action_type')]
			all_urls: set = set()
			for entry in history:
				all_urls.update(entry.get('tweets', entry.get('posts', [])))
			urls_block = '\n'.join(all_urls) if all_urls else '(none yet)'
			context += (
				f"\n--- MARKET HISTORY ({platform.upper()}) ---\n"
				f"Posts/tweets from market sessions (do NOT engage with these again):\n"
				f"{urls_block}\n\n"
				f"Recent pillars used: {', '.join(recent_pillars) if recent_pillars else '(none yet)'}\n"
				f"Recent action types: {', '.join(recent_actions) if recent_actions else '(none yet)'}\n\n"
				f"Last {len(recent)} sessions:\n" + "\n".join(recent) + "\n"
			)
		except Exception:
			pass

	# User profile
	profile_file = DATA_DIR / 'user_profile.txt'
	if profile_file.exists():
		try:
			content = profile_file.read_text(encoding='utf-8').strip()
			if content:
				context += f"\n--- MY PERSONALITY & OPINIONS ---\n{content[:1500]}\n"
		except Exception:
			pass

	# General knowledge
	data_file = DATA_DIR / 'data.txt'
	if data_file.exists():
		try:
			content = data_file.read_text(encoding='utf-8').strip()
			if content:
				context += f"\n--- GENERAL KNOWLEDGE & TRENDS ---\n{content[:10000]}\n"
		except Exception:
			pass

	# Market insights
	insights_file = DATA_DIR / 'market_insights.txt'
	if insights_file.exists():
		try:
			content = insights_file.read_text(encoding='utf-8').strip()
			if content:
				context += f"\n--- MARKET INSIGHTS (Patterns you've observed) ---\n{content[-2000:]}\n"
		except Exception:
			pass

	# Market performance
	perf_file = DATA_DIR / 'market_performance.json'
	if perf_file.exists():
		try:
			with open(perf_file, 'r') as f:
				perf = json.load(f)
			recent_perf = perf[-5:] if isinstance(perf, list) else []
			if recent_perf:
				context += "\n--- RECENT PERFORMANCE ---\n"
				for p in recent_perf:
					context += f"[{p.get('date', '?')}] impressions={p.get('impressions', '?')} engagements={p.get('engagements', '?')} best_post={p.get('best_post', 'N/A')}\n"
		except Exception:
			pass

	# Platform-specific virality notes
	if platform == 'x':
		virality_file = DATA_DIR / 'virality_notes.txt'
	else:
		virality_file = DATA_DIR / 'linkedin_virality_notes.txt'
	if virality_file.exists():
		try:
			content = virality_file.read_text(encoding='utf-8').strip()
			if content:
				context += f"\n--- VIRALITY PLAYBOOK ({platform.upper()}) ---\n{content[-2000:]}\n"
		except Exception:
			pass

	return context


# ── Prompt building ──────────────────────────────────────────────────────

def build_market_task(platform: str, strategy: dict, context: str, force_action: str | None = None) -> str:
	"""Build the multi-phase market session prompt."""

	product = strategy.get('business_description', 'the product')
	keywords = strategy.get('keywords', [])
	brand_voice = strategy.get('brand_voice', 'professional but authentic')
	pillars = strategy.get('content_pillars', [])
	competitors = strategy.get('competitors', [])

	keywords_str = ', '.join(keywords) if keywords else 'relevant industry terms'
	pillars_str = '\n'.join([f"  - {p['name']}: {p['description']}" for p in pillars]) if pillars else '  (none defined)'
	competitors_str = ', '.join(competitors) if competitors else '(none defined)'

	# Randomize session character
	check_performance = random.random() < 0.3
	check_competitors = random.random() < 0.25

	# Platform-specific config
	if platform == 'x':
		home_url = "https://x.com/home"
		search_url = "https://x.com/search?q="
		compose_action = "Click the tweet composition area and draft a tweet"
		reply_term = "reply"
		post_term = "tweet"
		output_label = "TWEETS"
		typing_rule = "- KNOWN TYPING BUG: When typing on X, the first letter you type gets duplicated (e.g., 'HHello' instead of 'Hello'). To prevent this, ALWAYS start your drafted text with a single space character (e.g., ' Hello'), OR explicitly verify and delete the duplicated first letter before posting."
	else:
		home_url = "https://www.linkedin.com/feed/"
		search_url = "https://www.linkedin.com/search/results/content/?keywords="
		compose_action = "Click 'Start a post' to open the post composer"
		reply_term = "comment"
		post_term = "post"
		output_label = "POSTS"
		typing_rule = ""

	# Force action override
	if force_action and force_action in ACTION_TYPES:
		action_decision = f"""
		The user has specifically requested this action type: {ACTION_LABELS[force_action]}.
		You MUST perform this action type this session. Do not override the user's choice."""
	else:
		action_decision = f"""
		Based on the strategy, history, and performance data, decide the best action for this session.
		Consider:
		- Which content pillar hasn't been covered recently? Rotate through them.
		- Which action type hasn't been used recently? Vary your approach.
		- If performance data shows a type is working well, lean into it occasionally.

		Action types available:
		1. Product Post — original {post_term} highlighting a feature, update, or use case
		2. Industry Commentary — {post_term} tying the product to a trending topic or news
		3. Keyword Reply — search for "{keywords_str}" and {reply_term} to relevant conversations naturally
		4. Engagement — like/retweet/react to {post_term}s from target audience for visibility
		5. Educational — tutorial, tip, or how-to {post_term} demonstrating product value
		6. Social Proof — share a user story, testimonial, or metric"""

	return f"""
		You are a world-class Social Media Manager. You manage the {platform.upper()} account for this product:

		PRODUCT: {product}
		BRAND VOICE: {brand_voice}
		KEYWORDS TO MONITOR: {keywords_str}
		CONTENT PILLARS:
{pillars_str}

		{context}

		PHASE 1 — STRATEGY REVIEW:
		Read the marketing strategy and history above carefully. Note which pillars and action types
		have been used recently. Your goal is to vary content and maximize coverage.

		{"PHASE 2 — PERFORMANCE CHECK:" if check_performance else "PHASE 2 — SKIP PERFORMANCE CHECK (not this session):"}
		{"Go to your profile page. Check how recent marketing posts performed (likes, replies, impressions if visible)." if check_performance else "Skip — go straight to deciding your action."}
		{"Report: MARKET_METRICS: impressions=<number>, engagements=<number>, best_post=<url>" if check_performance else ""}

		PHASE 3 — DECIDE ACTION:
		{action_decision}

		PHASE 4 — EXECUTE:
		Based on your chosen action:

		IF Product Post / Industry Commentary / Educational / Social Proof:
		1. Go to {home_url}
		2. {compose_action}
		3. Write content that:
		   - Matches the brand voice exactly
		   - Sounds human and authentic, NOT corporate or AI-generated
		   - Is concise and punchy (1-3 sentences for {platform.upper()})
		   - Relates to the chosen content pillar
		4. Publish it

		IF Keyword Reply:
		1. Go to {search_url}<pick a keyword from the list>
		2. Find a recent, relevant conversation
		3. {reply_term.capitalize()} with something that:
		   - Adds genuine value to the conversation
		   - Naturally relates to your product without being spammy
		   - Sounds like a helpful expert, not a marketer
		4. Engage with 1-3 conversations total

		IF Engagement:
		1. Go to {home_url} or search for target audience keywords
		2. Find posts from people in the target audience
		3. Like, retweet/share, or react to 3-5 relevant posts
		4. This is about visibility and relationship building — no hard selling

		{"PHASE 5 — COMPETITIVE OBSERVATION:" if check_competitors else ""}
		{"Browse one competitor account: " + competitors_str + ". Note what content they posted recently and what got engagement." if check_competitors else ""}

		CRITICAL RULES:
		- Be authentic and helpful. NEVER be spammy or salesy.
		- Match the brand voice from the strategy.
		- Never mention you are an AI or automated.
		- Check MARKET HISTORY — never engage with the same post/tweet twice.
		{typing_rule}
		- After finishing, output these lines (each on its own line):
		  {output_label}: url1, url2, url3
		  ACTION_TYPE: <one of: product_post, industry_commentary, keyword_reply, engagement, educational, social_proof>
		  PILLAR_USED: <which content pillar this session covered>
		  MARKET_INSIGHT: <one pattern you observed about what works in this product's space>
		  Then a one-sentence summary of what you did.
		"""


def handle_market_result(platform: str, result: str) -> str:
	"""Process market mode output — extract markers and save history. Used by both x.py and linkedin.py."""
	if not result:
		return "No output generated"

	history_file = DATA_DIR / f'market_history_{platform}.json'
	history_data = []
	if history_file.exists():
		try:
			with open(history_file, 'r') as f:
				history_data = json.load(f)
		except Exception:
			pass

	# Extract output markers
	url_key = 'TWEETS' if platform == 'x' else 'POSTS'
	urls = []
	url_match = re.search(rf'{url_key}:\s*(.+)', result)
	if url_match:
		urls = [u.strip() for u in url_match.group(1).split(',') if u.strip()]

	action_type = ''
	action_match = re.search(r'ACTION_TYPE:\s*(\S+)', result)
	if action_match:
		action_type = action_match.group(1).strip()

	pillar_used = ''
	pillar_match = re.search(r'PILLAR_USED:\s*(.+)', result)
	if pillar_match:
		pillar_used = pillar_match.group(1).strip()

	# Build summary from last line (fallback to full result)
	lines = [l.strip() for l in result.strip().splitlines() if l.strip()]
	summary = ''
	for line in reversed(lines):
		if not any(line.startswith(prefix) for prefix in [url_key + ':', 'ACTION_TYPE:', 'PILLAR_USED:', 'MARKET_INSIGHT:', 'MARKET_METRICS:']):
			summary = line
			break

	history_data.append({
		"timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
		"action": result,
		"action_type": action_type,
		"pillar_used": pillar_used,
		"summary": summary,
		"tweets" if platform == 'x' else "posts": urls,
	})

	with open(history_file, 'w') as f:
		json.dump(history_data[-50:], f, indent=2)

	# Append market insight
	insight_match = re.search(r'MARKET_INSIGHT:\s*(.+)', result)
	if insight_match:
		insight = insight_match.group(1).strip()
		insights_file = DATA_DIR / 'market_insights.txt'
		with open(insights_file, 'a', encoding='utf-8') as f:
			f.write(f"[{datetime.now().strftime('%Y-%m-%d')}] [{platform}] {insight}\n")

	# Log performance metrics
	metrics_match = re.search(r'MARKET_METRICS:\s*(.+)', result)
	if metrics_match:
		metrics_str = metrics_match.group(1).strip()
		perf_file = DATA_DIR / 'market_performance.json'
		perf_data = []
		if perf_file.exists():
			try:
				perf_data = json.loads(perf_file.read_text())
			except Exception:
				pass
		perf_entry = {"date": datetime.now().strftime('%Y-%m-%d %H:%M'), "platform": platform, "raw": metrics_str}
		# Parse impressions and engagements
		imp_match = re.search(r'impressions=(\d+)', metrics_str)
		eng_match = re.search(r'engagements=(\d+)', metrics_str)
		best_match = re.search(r'best_post=(\S+)', metrics_str)
		if imp_match:
			perf_entry['impressions'] = int(imp_match.group(1))
		if eng_match:
			perf_entry['engagements'] = int(eng_match.group(1))
		if best_match:
			perf_entry['best_post'] = best_match.group(1)
		perf_data.append(perf_entry)
		perf_file.write_text(json.dumps(perf_data[-100:], indent=2))

	return f"Market action completed ({platform}): {summary or result[:200]}"


# ── CLI ──────────────────────────────────────────────────────────────────

async def main():
	parser = argparse.ArgumentParser(description='Market Mode — Strategy Generator')
	sub = parser.add_subparsers(dest='command')

	gen_parser = sub.add_parser('generate', help='Generate a marketing strategy')
	gen_parser.add_argument('--product', type=str, required=True, help='Business/product description')

	sub.add_parser('show', help='Show current strategy')

	args = parser.parse_args()

	if args.command == 'generate':
		api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
		if not api_key:
			print('Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable')
			return

		print(f'Researching and generating strategy...')
		strategy = await generate_strategy(api_key, args.product)
		path = save_strategy(strategy)
		print(f'Strategy saved to {path}')
		print(json.dumps(strategy, indent=2))

		# Auto-populate domain knowledge if data.txt is empty or missing
		data_file = DATA_DIR / 'data.txt'
		if not data_file.exists() or not data_file.read_text(encoding='utf-8').strip():
			domain = derive_research_domain(strategy)
			print(f'\ndata.txt is empty — auto-populating domain knowledge...')
			print(f'Research domain: "{domain}"')
			await run_domain_research(api_key, domain)

	elif args.command == 'show':
		strategy = load_market_strategy()
		if strategy:
			print(json.dumps(strategy, indent=2))
		else:
			print('No strategy found. Run: python -m agents.market generate --product "your product"')

	else:
		parser.print_help()


if __name__ == '__main__':
	asyncio.run(main())
