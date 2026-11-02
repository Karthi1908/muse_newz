"""Your Daily Muse application package."""
import os

# On Windows in sandboxed or isolated execution environments, Python's ProactorEventLoop uses socket.socketpair()
# for its self-pipe, which can block waiting for local loopback handshake due to sandbox network isolation policies.
# We safely patch the self-pipe to use os.pipe() so asyncio event loops initialize cleanly and instantly.
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
