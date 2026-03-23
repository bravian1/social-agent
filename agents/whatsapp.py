#!/usr/bin/env python3
"""
WhatsApp Agent — Login, auto-respond to a specific person, or auto-respond to all unread.
"""

import argparse
import asyncio
import logging
import os
import random
from pathlib import Path
from dotenv import load_dotenv

from browser_use import Agent, BrowserSession
from browser_use.llm.google import ChatGoogle

load_dotenv()

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
_NO_KEY_MSG = '❌ GOOGLE_API_KEY is required'


def setup_environment():
	os.environ['BROWSER_USE_SETUP_LOGGING'] = 'false'
	os.environ['BROWSER_USE_LOGGING_LEVEL'] = 'critical'
	logging.getLogger().setLevel(logging.CRITICAL)


def setup_browser() -> BrowserSession:
	USER_DATA_DIR = Path.home() / '.config' / 'social-agent' / 'browser_profile'
	USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
	return BrowserSession(headless=False, user_data_dir=str(USER_DATA_DIR))


async def login_to_whatsapp():
	"""Open WhatsApp Web and wait for the user to scan the QR code."""
	if not GOOGLE_API_KEY:
		print(_NO_KEY_MSG)
		return

	print('Opening WhatsApp Web — please scan the QR code when it appears.')

	task = """
	You are helping a user log into WhatsApp Web:
	1. Navigate to https://web.whatsapp.com
	2. Wait for the page to load completely
	3. If you see a QR code, tell the user to scan it with their phone
	4. Wait patiently until the WhatsApp chat interface appears
	5. Confirm successful login
	"""

	llm = ChatGoogle(model='gemini-flash-latest', temperature=0.3, api_key=GOOGLE_API_KEY)
	browser = setup_browser()
	agent = Agent(task=task, llm=llm, browser=browser)

	try:
		await agent.run()
		print('\n✅ Login complete. Press Enter to close the browser...')
		await asyncio.to_thread(input)
	except Exception as e:
		print(f'❌ Error: {e}')


async def auto_respond_to_person(name: str, session_minutes: int = 120):
	"""
	Open the chat with a specific person and wait for new messages, replying
	in the user's own writing style learned from the conversation history.
	Uses browser-use's wait action to stay alive between checks rather than
	repeatedly opening and closing the browser.
	"""
	if not GOOGLE_API_KEY:
		print(_NO_KEY_MSG)
		return

	print(f'Watching chat with {name} (session up to {session_minutes} min)...')

	task = f"""
	You are managing the WhatsApp conversation with "{name}" on behalf of the user.

	Setup (do once):
	1. Navigate to https://web.whatsapp.com and wait for it to fully load
	2. Open the chat with "{name}"
	3. Study all visible messages I (the user) have sent:
	   - Learn my writing style exactly: sentence length, punctuation, use of emoji,
	     vocabulary, tone, whether I use full sentences or fragments, etc.
	   - If there are no messages from me yet, reply naturally and concisely
	4. Note the exact content of the current last message in the chat

	Monitoring loop (repeat for this session):
	5. Use the wait action to wait 20 seconds
	6. Scroll to the bottom of the chat and check for any new messages from "{name}"
	   that arrived after the last message you noted
	7. If "{name}" sent a new message:
	   - Read it carefully along with the surrounding context
	   - Compose a reply that matches my writing style from step 3
	   - Send it
	   - Update your note of the last message to this new exchange
	8. If no new message, go back to step 5 and keep waiting
	9. Continue until this session ends
	"""

	llm = ChatGoogle(model='gemini-flash-latest', temperature=0.7, api_key=GOOGLE_API_KEY)
	browser = setup_browser()
	# ~10 agent steps per minute of session (20s wait + check + optional reply)
	max_steps = session_minutes * 10

	try:
		agent = Agent(task=task, llm=llm, browser=browser, max_steps=max_steps)
		await agent.run()
		print('✅ Session ended.')
	except Exception as e:
		print(f'❌ Error: {e}')


async def auto_respond_to_unread(filter_name: str = ""):
	"""
	Sweep unread chats once and reply to each where the last message is from
	the other person. Optionally apply a WhatsApp filter tab first (e.g.
	"Favorites", "Unread", "Groups", or a custom list name).
	"""
	if not GOOGLE_API_KEY:
		print(_NO_KEY_MSG)
		return

	label = f'"{filter_name}" filter' if filter_name else 'all chats'
	print(f'Sweeping unread messages ({label})...')

	filter_step = (
		f'2. At the top of the chat list, find and click the "{filter_name}" filter tab '
		f'to narrow the list down. Wait for it to apply.\n'
		if filter_name else
		'2. Stay on the default "All" view.\n'
	)

	task = f"""
	You are helping the user respond to unread WhatsApp messages.

	1. Navigate to https://web.whatsapp.com and wait for it to fully load
	{filter_step}
	3. Find all chats showing unread message indicators (bold name, unread count badge)
	4. For each unread chat:
	   a. Open it
	   b. Read the conversation — study the messages I (the user) have sent to
	      understand my writing style and tone for this specific conversation
	   c. Check if the last message is from the other person (not from me)
	   d. If yes: write a reply that matches how I write in this chat and send it
	   e. If no: skip this chat
	5. Once all visible unread chats are handled, you are done
	"""

	llm = ChatGoogle(model='gemini-flash-latest', temperature=0.7, api_key=GOOGLE_API_KEY)
	browser = setup_browser()

	try:
		agent = Agent(task=task, llm=llm, browser=browser)
		await agent.run()
		print('✅ Sweep complete.')
	except Exception as e:
		print(f'❌ Error: {e}')


async def _restart_loop(coro_fn, label: str):
	"""Restart the coroutine if it exits naturally (e.g. session limit reached)."""
	print(f'Auto-responder → {label} | Press Ctrl+C to stop.\n')
	while True:
		try:
			await coro_fn()
		except KeyboardInterrupt:
			print('\n🛑 Stopped.')
			break
		except Exception as e:
			print(f'❌ Error: {e} — restarting in 5 minutes...')
			await asyncio.sleep(300)


async def _poll_loop(coro_fn, label: str):
	"""Run a sweep function repeatedly on a short interval."""
	print(f'Auto-responder → {label} | Press Ctrl+C to stop.\n')
	while True:
		try:
			await coro_fn()
			wait = 3 + random.randint(-1, 2)
			print(f'⏰ Next sweep in {wait} minutes...')
			await asyncio.sleep(wait * 60)
		except KeyboardInterrupt:
			print('\n🛑 Stopped.')
			break
		except Exception as e:
			print(f'❌ Error: {e} — retrying in 5 minutes...')
			await asyncio.sleep(300)


async def main():
	setup_environment()

	parser = argparse.ArgumentParser(description='WhatsApp Automation')
	parser.add_argument('--login', action='store_true', help='Open WhatsApp Web to scan QR code')
	parser.add_argument('--auto-person', action='store_true', help='Auto-respond to a specific contact')
	parser.add_argument('--name', type=str, default='', help='Contact name for --auto-person')
	parser.add_argument('--session-minutes', type=int, default=120,
	                    help='Session length in minutes before agent restarts (default: 120)')
	parser.add_argument('--auto-unread', action='store_true', help='Auto-respond to all unread messages')
	parser.add_argument('--filter', type=str, default='',
	                    help='WhatsApp filter tab to apply before sweeping '
	                         '(e.g. "Favorites", "Unread", "Groups", or a custom list name)')
	args = parser.parse_args()

	if args.login:
		await login_to_whatsapp()
	elif args.auto_person:
		if not args.name:
			print('❌ --name is required with --auto-person (e.g. --name "John")')
			return
		await _restart_loop(
			lambda: auto_respond_to_person(args.name, args.session_minutes),
			args.name,
		)
	elif args.auto_unread:
		label = f'unread · filter: {args.filter}' if args.filter else 'all unread'
		await _poll_loop(lambda: auto_respond_to_unread(args.filter), label)
	else:
		print('Modes: --login | --auto-person --name "Name" | --auto-unread')


if __name__ == '__main__':
	asyncio.run(main())
