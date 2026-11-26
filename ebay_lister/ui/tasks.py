"""Run slow work (network calls) in a background thread without freezing the Tk window.

Tkinter is not thread-safe, so worker threads never touch widgets. They put results on a
queue, and :class:`TaskRunner` drains that queue on the Tk main loop every 100 ms and calls
the callbacks there.
"""

import queue
import threading
import traceback

from ebay_lister.api.http import ApiError


class TaskRunner:
    """Background job runner bound to one Tk root window.

    Example::

        runner.run(lambda: client.shipping_profiles(),
                   on_ok=lambda profiles: show(profiles),
                   on_err=lambda exc: messagebox.showerror("Oops", str(exc)))
    """

    POLL_MS = 100

    def __init__(self, root, log):
        """``log`` is called on the main thread for messages sent with :meth:`log_from_thread`."""
        self.root = root
        self._log = log
        self._q = queue.Queue()
        self.root.after(self.POLL_MS, self._poll)

    def run(self, fn, on_ok=None, on_err=None):
        """Call ``fn()`` in a daemon thread; then ``on_ok(result)`` or ``on_err(exception)`` on the UI thread."""
        def worker():
            try:
                result = fn()
                self._q.put(("callback", on_ok, result))
            except Exception as exc:  # noqa: BLE001 - every error is reported to the UI
                if not isinstance(exc, ApiError):
                    traceback.print_exc()  # unexpected bug: keep the traceback in the terminal
                self._q.put(("callback", on_err, exc))

        threading.Thread(target=worker, daemon=True).start()

    def log_from_thread(self, msg):
        """Thread-safe logging: the message is shown in the activity logs on the next poll."""
        self._q.put(("log", msg))

    def _poll(self):
        try:
            while True:
                kind, *rest = self._q.get_nowait()
                if kind == "log":
                    self._log(rest[0])
                elif rest[0] is not None:
                    rest[0](rest[1])
        except queue.Empty:
            pass
        self.root.after(self.POLL_MS, self._poll)
