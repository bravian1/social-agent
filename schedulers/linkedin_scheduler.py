#!/usr/bin/env python3
"""
LinkedIn Active Scheduler - Periodically runs the LinkedIn agent in 'active' mode.
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
	log_file = LOGS_DIR / 'linkedin_scheduler.log'
	logger = logging.getLogger('linkedin_scheduler')
	logger.setLevel(logging.INFO)

	fh = logging.FileHandler(log_file, encoding='utf-8')
	fh.setFormatter(logging.Formatter('%(asctime)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
	logger.addHandler(fh)

	ch = logging.StreamHandler(sys.stdout)
	ch.setFormatter(logging.Formatter('%(message)s'))
	logger.addHandler(ch)

	return logger


log = setup_logging()


async def active_loop(theme: str, interval_min: int, interval_max: int, duration_min: int, duration_max: int):
	"""Run the LinkedIn agent in active mode on a schedule."""
	from agents.linkedin import run_agent

	log.info('🕐 LinkedIn Scheduler Started')
	log.info(f'   Theme: "{theme}"')
	log.info(f'   Interval: {interval_min}–{interval_max} minutes (random each session)')
	log.info(f'   Session duration: {duration_min}–{duration_max} minutes (random each session)')
	log.info(f'   Log file: {LOGS_DIR / "linkedin_scheduler.log"}')

	run_count = 0

	while True:
		try:
			run_count += 1
			now = datetime.now().strftime('%H:%M:%S')
			duration = random.randint(duration_min, duration_max)
			log.info(f'🔄 [{now}] Starting LinkedIn session #{run_count} (duration: {duration} min)...')

			config = {
				'theme': theme,
				'duration_minutes': duration,
				'debug': False,
			}

			result = await run_agent('active', config)
			log.info(f'   Result: {result}')

			wait = random.randint(interval_min, interval_max)
			log.info(f'⏰ Next session in {wait} minutes...')
			await asyncio.sleep(wait * 60)

		except KeyboardInterrupt:
			log.info('🛑 Scheduler stopped by user.')
			break
		except Exception as e:
			log.error(f'❌ Error in LinkedIn session: {e}')
			log.info('   Waiting 5 minutes before retry...')
			await asyncio.sleep(300)


async def main():
	parser = argparse.ArgumentParser(description='LinkedIn Active Scheduler')
	parser.add_argument('--theme', type=str, default='software development',
	                    help='Theme to focus on while being active')
	parser.add_argument('--interval-min', type=int, default=60,
	                    help='Minimum minutes between sessions')
	parser.add_argument('--interval-max', type=int, default=120,
	                    help='Maximum minutes between sessions')
	parser.add_argument('--duration-min', type=int, default=5,
	                    help='Minimum minutes per session')
	parser.add_argument('--duration-max', type=int, default=15,
	                    help='Maximum minutes per session')
	args = parser.parse_args()

	api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
	if not api_key:
		print('❌ Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable')
		return

	await active_loop(args.theme, args.interval_min, args.interval_max, args.duration_min, args.duration_max)


if __name__ == '__main__':
	asyncio.run(main())
