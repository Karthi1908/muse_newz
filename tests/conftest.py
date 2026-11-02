import os
import sys
import pytest
from config.settings import settings

# On Windows in sandboxed test environments, Python's ProactorEventLoop uses socket.socketpair()
# for its self-pipe, which blocks waiting for local network handshake due to sandbox network isolation.
# We safely patch the self-pipe to use os.pipe() so asyncio event loops run cleanly in tests.
if os.name == "nt":
    from asyncio import proactor_events

    class _PipeSocket:
        def __init__(self, fd: int) -> None:
            self._fd = fd

        def fileno(self) -> int:
            return self._fd

        def close(self) -> None:
            try:
                os.close(self._fd)
            except OSError:
                pass

        def setblocking(self, flag: bool) -> None:
            pass

    def _safe_make_self_pipe(self):
        r, w = os.pipe()
        self._ssock = _PipeSocket(r)
        self._csock = _PipeSocket(w)
        self._internal_fds += 1

    def _safe_close_self_pipe(self):
        if self._self_reading_future is not None:
            self._self_reading_future.cancel()
            self._self_reading_future = None
        if self._ssock is not None:
            self._ssock.close()
            self._ssock = None
            self._internal_fds -= 1
        if self._csock is not None:
            self._csock.close()
            self._csock = None
            self._internal_fds -= 1

    def _safe_loop_self_reading(self, f=None):
        pass

    def _safe_write_to_self(self):
        if self._csock is not None:
            try:
                os.write(self._csock.fileno(), b"\0")
            except OSError:
                pass

    proactor_events.BaseProactorEventLoop._make_self_pipe = _safe_make_self_pipe
    proactor_events.BaseProactorEventLoop._close_self_pipe = _safe_close_self_pipe
    proactor_events.BaseProactorEventLoop._loop_self_reading = _safe_loop_self_reading
    proactor_events.BaseProactorEventLoop._write_to_self = _safe_write_to_self


@pytest.fixture(autouse=True)
def force_demo_mode_in_tests(monkeypatch):
    """Enforces Constitution Principle 8: Unit tests run alone against mock/fixture data without live network calls."""
    monkeypatch.setattr(settings, "DEMO_CACHE_MODE", "always")
