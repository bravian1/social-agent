#!/usr/bin/env python3
"""
Market Scheduler — Periodically runs market mode sessions across X and LinkedIn,
coordinating cadence so content is varied across platforms.
"""

import asyncio
import argparse
import logging
import os
import random
import sys
from datetime import datetime
from dotenv import load_dotenv

from agents import LOGS_DIR

load_dotenv()

LOGS_DIR.mkdir(exist_ok=True)


def setup_logging():
	log_file = LOGS_DIR / 'market_scheduler.log'
	logger = logging.getLogger('market_scheduler')
	logger.setLevel(logging.INFO)

	fh = logging.FileHandler(log_file, encoding='utf-8')
	fh.setFormatter(logging.Formatter('%(asctime)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
	logger.addHandler(fh)

	ch = logging.StreamHandler(sys.stdout)
	ch.setFormatter(logging.Formatter('%(message)s'))
	logger.addHandler(ch)

	return logger


log = setup_logging()


async def market_loop(
	platforms: list[str],
	interval_min: int,
	interval_max: int,
	force_action: str | None = None,
):
	"""Run market sessions on alternating platforms."""
	from agents.market import load_market_strategy

	strategy = load_market_strategy()
	if not strategy:
		log.error('No marketing strategy found. Run: python -m agents.market generate --product "..."')
		return

	log.info(f'Market Scheduler Started')
	log.info(f'   Platforms: {", ".join(platforms)}')
	log.info(f'   Interval: {interval_min}-{interval_max} minutes')
	if force_action:
		log.info(f'   Forced action: {force_action}')
	log.info(f'   Log file: {LOGS_DIR / "market_scheduler.log"}')

	# Weight platform selection by posting cadence
	cadence = strategy.get('posting_cadence', {})
	weights = []
	for p in platforms:
		posts_per_week = cadence.get(p, {}).get('posts_per_week', 3)
		weights.append(posts_per_week)

	run_count = 0

	while True:
		try:
			run_count += 1
			now = datetime.now().strftime('%H:%M:%S')

			# Pick platform weighted by cadence
			platform = random.choices(platforms, weights=weights, k=1)[0]

			log.info(f'[{now}] Starting market session #{run_count} on {platform.upper()}...')

			config = {
				'force_action': force_action,
				'debug': False,
			}

			if platform == 'x':
				from agents.x import run_agent
			else:
				from agents.linkedin import run_agent

			result = await run_agent('market', config)
			log.info(f'   Result: {result}')

			wait = random.randint(interval_min, interval_max)
			log.info(f'Next session in {wait} minutes...')
			await asyncio.sleep(wait * 60)

		except KeyboardInterrupt:
			log.info('Scheduler stopped by user.')
			break
		except Exception as e:
			log.error(f'Error in market session: {e}')
			log.info('   Waiting 5 minutes before retry...')
			await asyncio.sleep(300)


async def main():
	parser = argparse.ArgumentParser(description='Cross-platform Market Scheduler')
	parser.add_argument('--platforms', type=str, default='x,linkedin',
	                    help='Comma-separated platforms to market on (default: x,linkedin)')
	parser.add_argument('--interval-min', type=int, default=120,
	                    help='Minimum minutes between sessions')
	parser.add_argument('--interval-max', type=int, default=360,
	                    help='Maximum minutes between sessions')
	parser.add_argument('--force-action', type=str, default='',
	                    choices=['', 'product_post', 'industry_commentary', 'keyword_reply', 'engagement', 'educational', 'social_proof'],
	                    help='Force a specific action type every session')
	args = parser.parse_args()

	api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
	if not api_key:
		print('Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable')
		return

	platforms = [p.strip() for p in args.platforms.split(',') if p.strip() in ('x', 'linkedin')]
	if not platforms:
		print('No valid platforms specified. Use: x, linkedin')
		return

	await market_loop(
		platforms=platforms,
		interval_min=args.interval_min,
		interval_max=args.interval_max,
		force_action=args.force_action or None,
	)


if __name__ == '__main__':
	asyncio.run(main())
