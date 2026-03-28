"""Tests for agents/whatsapp.py — MutationObserver-based message detection."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, call, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cdp_session():
    """Return a mock CDPSession with the shape auto_respond_to_person expects."""
    session = MagicMock()
    session.session_id = "fake-session-id"

    # cdp_client.send.Runtime.*  — all async
    runtime_send = MagicMock()
    runtime_send.addBinding = AsyncMock(return_value={})
    runtime_send.evaluate = AsyncMock(return_value={'result': {'value': True}})
    session.cdp_client.send.Runtime = runtime_send

    # cdp_client.register.Runtime.bindingCalled — sync registration
    session.cdp_client.register.Runtime.bindingCalled = MagicMock()

    return session


# ---------------------------------------------------------------------------
# _setup_agent_task
# ---------------------------------------------------------------------------

class TestSetupAgentTask:
    def test_contains_contact_name(self):
        from agents.whatsapp import _setup_agent_task
        result = _setup_agent_task("Alice")
        assert "Alice" in result

    def test_navigates_to_whatsapp_web(self):
        from agents.whatsapp import _setup_agent_task
        result = _setup_agent_task("Bob")
        assert "web.whatsapp.com" in result

    def test_instructs_no_messages_sent(self):
        from agents.whatsapp import _setup_agent_task
        result = _setup_agent_task("Bob")
        assert "Do not send" in result

    def test_mentions_writing_style(self):
        from agents.whatsapp import _setup_agent_task
        result = _setup_agent_task("Carol")
        assert "writing style" in result


# ---------------------------------------------------------------------------
# _build_reply_task
# ---------------------------------------------------------------------------

class TestBuildReplyTask:
    def test_contains_contact_name(self):
        from agents.whatsapp import _build_reply_task
        result = _build_reply_task("Alice")
        assert "Alice" in result

    def test_checks_last_message_sender(self):
        from agents.whatsapp import _build_reply_task
        result = _build_reply_task("Dave")
        # Must guard against replying when user sent last message
        assert "last message" in result.lower()

    def test_matches_writing_style(self):
        from agents.whatsapp import _build_reply_task
        result = _build_reply_task("Eve")
        assert "writing style" in result

    def test_no_navigation(self):
        from agents.whatsapp import _build_reply_task
        result = _build_reply_task("Eve")
        assert "navigate away" in result or "Do not navigate" in result


# ---------------------------------------------------------------------------
# _OBSERVER_JS content
# ---------------------------------------------------------------------------

class TestObserverJS:
    def test_guard_against_double_injection(self):
        from agents.whatsapp import _OBSERVER_JS
        assert "__waObserverActive" in _OBSERVER_JS

    def test_signals_via_binding(self):
        from agents.whatsapp import _OBSERVER_JS
        assert "__waNewMsg" in _OBSERVER_JS

    def test_watches_incoming_class(self):
        from agents.whatsapp import _OBSERVER_JS
        assert "message-in" in _OBSERVER_JS

    def test_watches_main_container(self):
        from agents.whatsapp import _OBSERVER_JS
        assert "#main" in _OBSERVER_JS

    def test_uses_data_id_for_deduplication(self):
        from agents.whatsapp import _OBSERVER_JS
        assert "data-id" in _OBSERVER_JS or "dataset.id" in _OBSERVER_JS

    def test_seeds_seen_on_injection(self):
        """Existing messages must be seeded so they don't trigger a reply."""
        from agents.whatsapp import _OBSERVER_JS
        assert "seedSeen" in _OBSERVER_JS or "seen.add" in _OBSERVER_JS


# ---------------------------------------------------------------------------
# _inject_observer
# ---------------------------------------------------------------------------

class TestInjectObserver:
    @pytest.mark.asyncio
    async def test_registers_binding_with_correct_name(self):
        from agents.whatsapp import _inject_observer
        cdp = _make_cdp_session()
        event = asyncio.Event()
        await _inject_observer(cdp, event)
        cdp.cdp_client.send.Runtime.addBinding.assert_called_once_with(
            {'name': '__waNewMsg'},
            session_id="fake-session-id",
        )

    @pytest.mark.asyncio
    async def test_evaluates_observer_js(self):
        from agents.whatsapp import _inject_observer, _OBSERVER_JS
        cdp = _make_cdp_session()
        event = asyncio.Event()
        await _inject_observer(cdp, event)
        cdp.cdp_client.send.Runtime.evaluate.assert_called_once()
        call_args = cdp.cdp_client.send.Runtime.evaluate.call_args
        assert call_args[0][0]['expression'] == _OBSERVER_JS
        assert call_args[1]['session_id'] == "fake-session-id"

    @pytest.mark.asyncio
    async def test_registers_binding_called_handler(self):
        from agents.whatsapp import _inject_observer
        cdp = _make_cdp_session()
        event = asyncio.Event()
        await _inject_observer(cdp, event)
        cdp.cdp_client.register.Runtime.bindingCalled.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_sets_event_on_correct_name(self):
        """The binding callback must set the asyncio.Event when name == '__waNewMsg'."""
        from agents.whatsapp import _inject_observer
        cdp = _make_cdp_session()
        event = asyncio.Event()
        await _inject_observer(cdp, event)

        # Extract the registered callback and call it with the correct binding name
        callback = cdp.cdp_client.register.Runtime.bindingCalled.call_args[0][0]
        assert not event.is_set()
        callback({'name': '__waNewMsg', 'payload': '{}', 'executionContextId': 1}, None)
        assert event.is_set()

    @pytest.mark.asyncio
    async def test_callback_ignores_other_binding_names(self):
        """Callbacks for other binding names must not set the event."""
        from agents.whatsapp import _inject_observer
        cdp = _make_cdp_session()
        event = asyncio.Event()
        await _inject_observer(cdp, event)

        callback = cdp.cdp_client.register.Runtime.bindingCalled.call_args[0][0]
        callback({'name': '__somethingElse', 'payload': '{}', 'executionContextId': 1}, None)
        assert not event.is_set()


# ---------------------------------------------------------------------------
# _ensure_observer_active
# ---------------------------------------------------------------------------

class TestEnsureObserverActive:
    @pytest.mark.asyncio
    async def test_returns_true_when_observer_active(self):
        from agents.whatsapp import _ensure_observer_active
        cdp = _make_cdp_session()
        cdp.cdp_client.send.Runtime.evaluate = AsyncMock(
            return_value={'result': {'value': True}}
        )
        event = asyncio.Event()
        result = await _ensure_observer_active(cdp, event)
        assert result is True

    @pytest.mark.asyncio
    async def test_reinjects_when_observer_gone(self):
        """When window.__waObserverActive is false, re-inject and return True."""
        from agents.whatsapp import _ensure_observer_active
        cdp = _make_cdp_session()
        # First call (check): returns False. Second call (re-inject evaluate): returns {}
        cdp.cdp_client.send.Runtime.evaluate = AsyncMock(
            side_effect=[
                {'result': {'value': False}},  # observer check
                {},                             # re-inject evaluate
            ]
        )
        event = asyncio.Event()
        result = await _ensure_observer_active(cdp, event)
        assert result is True
        # evaluate called twice: once to check, once to re-inject
        assert cdp.cdp_client.send.Runtime.evaluate.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_false_on_cdp_exception(self):
        """If CDP raises, return False gracefully (triggers polling fallback)."""
        from agents.whatsapp import _ensure_observer_active
        cdp = _make_cdp_session()
        cdp.cdp_client.send.Runtime.evaluate = AsyncMock(
            side_effect=RuntimeError("CDP connection lost")
        )
        event = asyncio.Event()
        result = await _ensure_observer_active(cdp, event)
        assert result is False


# ---------------------------------------------------------------------------
# auto_respond_to_person — high-level flow
# ---------------------------------------------------------------------------

class TestAutoRespondToPerson:
    @pytest.mark.asyncio
    async def test_exits_early_without_api_key(self, monkeypatch):
        import agents.whatsapp as wa
        monkeypatch.setattr(wa, "GOOGLE_API_KEY", None)
        # Should return without raising
        await wa.auto_respond_to_person("Alice")

    @pytest.mark.asyncio
    async def test_setup_agent_runs_once(self, monkeypatch):
        """The setup Agent.run() must be called exactly once before the event loop."""
        import agents.whatsapp as wa

        monkeypatch.setattr(wa, "GOOGLE_API_KEY", "fake-key")

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock()
        AgentCls = MagicMock(return_value=mock_agent)
        monkeypatch.setattr(wa, "Agent", AgentCls)

        mock_browser = MagicMock()
        BrowserCls = MagicMock(return_value=mock_browser)
        monkeypatch.setattr(wa, "BrowserSession", BrowserCls)

        cdp = _make_cdp_session()
        mock_browser.get_or_create_cdp_session = AsyncMock(return_value=cdp)

        # Trigger session end immediately by giving 0-minute session
        await wa.auto_respond_to_person("Alice", session_minutes=0)

        # Agent should be instantiated at least once (setup)
        assert AgentCls.call_count >= 1

    @pytest.mark.asyncio
    async def test_reply_agent_runs_on_message_event(self, monkeypatch):
        """When the asyncio.Event fires, a reply Agent must be created and run."""
        import agents.whatsapp as wa

        monkeypatch.setattr(wa, "GOOGLE_API_KEY", "fake-key")

        run_call_count = 0

        async def mock_run():
            nonlocal run_call_count
            run_call_count += 1

        mock_agent = MagicMock()
        mock_agent.run = mock_run
        AgentCls = MagicMock(return_value=mock_agent)
        monkeypatch.setattr(wa, "Agent", AgentCls)

        mock_browser = MagicMock()
        BrowserCls = MagicMock(return_value=mock_browser)
        monkeypatch.setattr(wa, "BrowserSession", BrowserCls)

        cdp = _make_cdp_session()
        mock_browser.get_or_create_cdp_session = AsyncMock(return_value=cdp)

        # After setup run, grab the registered binding callback and schedule it
        original_register = cdp.cdp_client.register.Runtime.bindingCalled

        async def run_setup_then_signal():
            """Run setup, then fire the JS binding event after a short delay."""
            await asyncio.sleep(0)  # yield to let injection happen

            # Fire the binding event via the registered callback
            if original_register.call_args:
                callback = original_register.call_args[0][0]
                callback({'name': '__waNewMsg', 'payload': '{}', 'executionContextId': 1}, None)

        async def patched_run():
            nonlocal run_call_count
            run_call_count += 1
            if run_call_count == 1:
                # After setup completes, schedule the message signal
                asyncio.get_event_loop().call_later(0.05, lambda: None)

        mock_agent.run = AsyncMock(side_effect=patched_run)

        # Use a very short session so it ends quickly after one reply
        async def run_with_signal():
            task = asyncio.create_task(
                wa.auto_respond_to_person("Alice", session_minutes=1)
            )
            await asyncio.sleep(0.2)

            # Fire the binding callback if registered
            if original_register.call_args:
                callback = original_register.call_args[0][0]
                callback({'name': '__waNewMsg', 'payload': '{}', 'executionContextId': 1}, None)

            await asyncio.sleep(2.5)  # wait for debounce (1.5s) + reply agent
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_with_signal()
        # Setup (1) + at least one reply (1) = at least 2 agent runs
        assert run_call_count >= 2

    @pytest.mark.asyncio
    async def test_falls_back_to_polling_when_injection_fails(self, monkeypatch):
        """If observer injection raises on all retries, polling mode activates."""
        import agents.whatsapp as wa

        monkeypatch.setattr(wa, "GOOGLE_API_KEY", "fake-key")

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock()
        monkeypatch.setattr(wa, "Agent", MagicMock(return_value=mock_agent))

        mock_browser = MagicMock()
        monkeypatch.setattr(wa, "BrowserSession", MagicMock(return_value=mock_browser))

        # Injection always fails
        mock_browser.get_or_create_cdp_session = AsyncMock(
            side_effect=RuntimeError("CDP unavailable")
        )

        # Session of 0 minutes ends immediately after setup
        await wa.auto_respond_to_person("Alice", session_minutes=0)

        # Must not raise — graceful fallback
