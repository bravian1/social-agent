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

# ---------------------------------------------------------------------------
# JavaScript MutationObserver injected into the WhatsApp Web page.
# It watches #main for new incoming message nodes and signals Python via the
# CDP Runtime.addBinding mechanism (window.__waNewMsg).
# ---------------------------------------------------------------------------
_OBSERVER_JS = """
(function() {
    if (window.__waObserverActive) return;
    window.__waObserverActive = true;

    var seen = new Set();

    function seedSeen(root) {
        root.querySelectorAll('[data-id]').forEach(function(el) {
            seen.add(el.dataset.id);
        });
    }

    function checkForIncoming(node) {
        if (node.nodeType !== Node.ELEMENT_NODE) return;
        var candidates = [node].concat(Array.from(node.querySelectorAll('[data-id]')));
        for (var i = 0; i < candidates.length; i++) {
            var el = candidates[i];
            var dataId = el.dataset && el.dataset.id;
            if (!dataId || seen.has(dataId)) continue;
            if (el.querySelector('.message-in') || el.classList.contains('message-in')) {
                seen.add(dataId);
                try {
                    window.__waNewMsg(JSON.stringify({dataId: dataId, ts: Date.now()}));
                } catch(e) {
                    setTimeout(function() {
                        try {
                            window.__waNewMsg(JSON.stringify({dataId: dataId, ts: Date.now()}));
                        } catch(_) {}
                    }, 100);
                }
                return;
            }
        }
    }

    function attach() {
        var root = document.querySelector('#main') || document.body;
        seedSeen(root);
        var obs = new MutationObserver(function(mutations) {
            mutations.forEach(function(m) {
                m.addedNodes.forEach(function(n) { checkForIncoming(n); });
            });
        });
        obs.observe(root, {childList: true, subtree: true});
        window.__waObserver = obs;
    }

    if (document.querySelector('#main')) {
        attach();
    } else {
        var waitObs = new MutationObserver(function() {
            if (document.querySelector('#main')) {
                waitObs.disconnect();
                attach();
            }
        });
        waitObs.observe(document.body, {childList: true, subtree: true});
    }
})();
"""


def setup_environment():
    os.environ['BROWSER_USE_SETUP_LOGGING'] = 'false'
    os.environ['BROWSER_USE_LOGGING_LEVEL'] = 'critical'
    logging.getLogger().setLevel(logging.CRITICAL)


def setup_browser() -> BrowserSession:
    USER_DATA_DIR = Path.home() / '.config' / 'social-agent' / 'browser_profile'
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return BrowserSession(headless=False, user_data_dir=str(USER_DATA_DIR))


def _setup_agent_task(name: str) -> str:
    return f"""
You are setting up to manage the WhatsApp conversation with "{name}" on behalf of the user.

1. Navigate to https://web.whatsapp.com and wait for it to fully load
2. Open the chat with "{name}"
3. Study all visible messages the user has sent:
   - Learn their writing style exactly: sentence length, punctuation, use of emoji,
     vocabulary, tone, whether they use full sentences or fragments, etc.
   - If there are no messages from the user yet, prepare to reply naturally and concisely
4. Confirm the chat is open and ready. Do not send any messages yet.
"""


def _build_reply_task(name: str) -> str:
    return f"""
A new message from "{name}" has just arrived in the open WhatsApp chat.

1. Read the last few messages for context
2. Check if the last message is actually from "{name}" (not from the user)
3. If yes: compose a reply that exactly matches the user's writing style from the
   conversation history and send it
4. If no: do nothing — the user sent the last message
5. Do not navigate away or open other chats
"""


async def _inject_observer(cdp_session, new_msg_event: asyncio.Event) -> None:
    """Register the CDP binding and inject the MutationObserver into the page."""
    await cdp_session.cdp_client.send.Runtime.addBinding(
        {'name': '__waNewMsg'},
        session_id=cdp_session.session_id,
    )

    def _on_binding_called(event_data, session_id):
        if event_data.get('name') != '__waNewMsg':
            return
        new_msg_event.set()

    cdp_session.cdp_client.register.Runtime.bindingCalled(_on_binding_called)

    await cdp_session.cdp_client.send.Runtime.evaluate(
        {'expression': _OBSERVER_JS, 'returnByValue': False},
        session_id=cdp_session.session_id,
    )


async def _ensure_observer_active(cdp_session, new_msg_event: asyncio.Event) -> bool:
    """Verify the observer is still running; re-inject if not. Returns True if active."""
    try:
        result = await cdp_session.cdp_client.send.Runtime.evaluate(
            {'expression': '!!window.__waObserverActive', 'returnByValue': True},
            session_id=cdp_session.session_id,
        )
        active = result.get('result', {}).get('value', False)
        if not active:
            print('Observer was reset, re-injecting...')
            await _inject_observer(cdp_session, new_msg_event)
        return True
    except Exception as e:
        print(f'⚠️ Could not verify observer: {e}')
        return False


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
    Open the chat with a specific person and respond to new messages using a
    DOM MutationObserver — no LLM polling. The agent wakes only when a real
    incoming message is detected by JavaScript, then replies once and goes back
    to sleep. Falls back to 30-second polling if the observer cannot be injected.
    """
    if not GOOGLE_API_KEY:
        print(_NO_KEY_MSG)
        return

    print(f'Watching chat with {name} (event-driven, session up to {session_minutes} min)...')

    llm = ChatGoogle(model='gemini-flash-latest', temperature=0.7, api_key=GOOGLE_API_KEY)
    USER_DATA_DIR = Path.home() / '.config' / 'social-agent' / 'browser_profile'
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    browser = BrowserSession(headless=False, user_data_dir=str(USER_DATA_DIR), keep_alive=True)

    # Phase 1: one-time setup — navigate, open chat, learn writing style
    setup_agent = Agent(task=_setup_agent_task(name), llm=llm, browser=browser, max_steps=20)
    try:
        await setup_agent.run()
    except Exception as e:
        print(f'❌ Setup failed: {e}')
        return

    # Phase 2: inject MutationObserver via CDP
    new_msg_event = asyncio.Event()
    cdp_session = None
    observer_ok = False

    for attempt in range(3):
        try:
            cdp_session = await browser.get_or_create_cdp_session()
            await _inject_observer(cdp_session, new_msg_event)
            observer_ok = True
            print('✅ MutationObserver active — waiting for messages...')
            break
        except Exception as e:
            wait = 2 ** (attempt + 1)
            print(f'⚠️ Observer injection attempt {attempt + 1} failed ({e}), retrying in {wait}s...')
            await asyncio.sleep(wait)

    if not observer_ok:
        print('⚠️ Observer unavailable — falling back to 30s polling.')

    # Phase 3: event-driven reply loop
    session_end = asyncio.get_event_loop().time() + session_minutes * 60

    while True:
        remaining = session_end - asyncio.get_event_loop().time()
        if remaining <= 0:
            print(f'⏰ Session limit reached for {name}.')
            break

        try:
            if observer_ok:
                # Block until JS signals a new incoming message (or session expires)
                await asyncio.wait_for(new_msg_event.wait(), timeout=remaining)
            else:
                # Polling fallback: check every 30 seconds
                await asyncio.sleep(min(remaining, 30))
        except asyncio.TimeoutError:
            print(f'⏰ Session ended for {name}.')
            break

        new_msg_event.clear()

        # Debounce: collect any rapid follow-up messages before replying
        await asyncio.sleep(1.5)
        new_msg_event.clear()

        reply_agent = Agent(
            task=_build_reply_task(name),
            llm=llm,
            browser=browser,
            max_steps=15,
        )
        try:
            await reply_agent.run()
        except Exception as e:
            print(f'❌ Reply agent error: {e}')

        # Verify the observer survived the agent interaction
        if cdp_session and observer_ok:
            observer_ok = await _ensure_observer_active(cdp_session, new_msg_event)

    print('✅ Session ended.')


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
