"""OLA DMX output on a dedicated worker thread.

The frame loop writes colors into a latest-wins channel buffer and never
touches the network. The worker owns every socket operation: it connects
(with rate-limited retry), paces sends, consumes every RPC response, and
reconnects on any failure. A wedged or restarting olad therefore costs
light output, never the game loop.

Ground rules learned from the previous controller (see
experiments/dmx_reference/dmx_controller.py and the 2026-07-06 soak-test
stall): OLA's client is asynchronous — every SendDmx gets a response that
must be consumed by the wrapper's select loop, or the socket buffers fill
until a blocking send() wedges the process. Here the wrapper's Run() loop
is always running while connected, and the socket we hand it has a real
timeout, so no call can block forever.
"""

import array
import logging
import socket
import threading
import time

from ola.ClientWrapper import ClientWrapper
from ola.OlaClient import OLA_PORT, OLADNotRunningException

logger = logging.getLogger(__name__)

DMX_UNIVERSE_SIZE = 512
DEFAULT_UNIVERSE = 0
# Each fixture listens on a block of this many channels; offsets 0..3 are
# intensity, red, green, blue and the rest are the fixture's special
# functions (strobe, sound-active, ...) which we leave at zero
DEFAULT_FIXTURE_CHANNEL_WIDTH = 10

# The worker wakes at this interval; a frame goes out only when a fixture
# changed or the keepalive is due
TICK_INTERVAL_MS = 25
# Send even without changes so olad and the health bookkeeping see a live
# client, and a frame lost to a reconnect window is re-sent promptly
KEEPALIVE_INTERVAL_SECS = 1.0

# connect()/send() give up after this long; turns a wedged olad into an
# exception and a reconnect instead of blocking the worker forever
SOCKET_TIMEOUT_SECS = 1.0

# Every send expects an RPC ack. If acks stop while sends continue, olad is
# accepting writes but not servicing them — treat as wedged and reconnect
ACK_TIMEOUT_SECS = 2.0

# Minimum time between attempts to (re)connect to olad
RECONNECT_INTERVAL_SECS = 1.0
# While disconnected, repeat an ERROR at this interval so a dead light
# system is visible in the log stream, not just one line at startup
DISCONNECTED_LOG_INTERVAL_SECS = 30.0

# Periodic INFO line with send/ack counters — cheap soak-test breadcrumbs
HEALTH_LOG_INTERVAL_SECS = 300.0

# olad NACKing frames (e.g. nothing patched to the universe) repeats at
# send rate; warn at this interval instead of 40x/sec
REJECTED_LOG_INTERVAL_SECS = 10.0

# stop() gives the worker this long to finish; it can be inside a socket
# timeout, so allow a little more than SOCKET_TIMEOUT_SECS
SHUTDOWN_JOIN_TIMEOUT_SECS = 3.0


class DmxController:
    """Threaded, self-healing controller for OLA DMX fixtures."""

    def __init__(
        self,
        universe: int = DEFAULT_UNIVERSE,
        fixture_channel_width: int = DEFAULT_FIXTURE_CHANNEL_WIDTH,
        **_,
    ):
        self._universe = universe
        self._fixture_channel_width = fixture_channel_width

        # Shared with the worker; everything below the lock line is guarded
        self._lock = threading.Lock()
        self._channels = bytearray(DMX_UNIVERSE_SIZE)
        # Starts dirty so the first connect pushes a full frame
        self._dirty = True
        self._wrapper: ClientWrapper | None = None

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Worker-owned bookkeeping (only the worker thread touches these
        # while it runs; initialized here so tests can drive _run directly)
        self._last_send_secs = float("-inf")
        self._last_ack_secs = float("-inf")
        self._outstanding_acks = 0
        self._frames_sent = 0
        self._frames_acked = 0
        self._frames_rejected = 0
        self._last_health_log_secs = float("-inf")
        self._last_reject_log_secs = float("-inf")

    # ---- main-thread API ----------------------------------------------

    def start(self) -> None:
        """Start the worker. Never touches the network itself, so a dead
        olad at boot costs nothing — the worker retries until it appears."""
        if self._thread is not None:
            logger.warning("DmxController.start() called twice, ignoring")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            name="dmx_worker", target=self._worker, daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            wrapper = self._wrapper
        if wrapper is not None:
            # SelectServer documents Stop/Execute as its only thread-safe
            # methods; this wakes the select loop immediately
            wrapper.Stop()
        if self._thread is not None:
            self._thread.join(timeout=SHUTDOWN_JOIN_TIMEOUT_SECS)
            if self._thread.is_alive():
                logger.warning("DMX worker did not stop within %.1fs", SHUTDOWN_JOIN_TIMEOUT_SECS)
            self._thread = None

    def set_fixture_colour(self, fixture_id: int, rgb) -> None:
        """Stage a fixture color; the worker sends it on its next tick.
        Latest-wins: setting a color twice between ticks sends only the
        second, so a burst of updates can never queue anything."""
        base = fixture_id * self._fixture_channel_width
        with self._lock:
            self._channels[base] = 255  # intensity
            self._channels[base + 1 : base + 4] = bytes(rgb)
            self._dirty = True

    # ---- worker thread --------------------------------------------------

    def _worker(self) -> None:
        logger.info("DMX worker started (universe %d)", self._universe)
        last_disconnected_log_secs = float("-inf")
        while not self._stop_event.is_set():
            sock = None
            try:
                sock = socket.create_connection(
                    ("localhost", OLA_PORT), timeout=SOCKET_TIMEOUT_SECS
                )
                wrapper = ClientWrapper(socket=sock)
            except OSError as e:
                now = time.monotonic()
                if now - last_disconnected_log_secs >= DISCONNECTED_LOG_INTERVAL_SECS:
                    last_disconnected_log_secs = now
                    logger.error(
                        "olad unavailable (%s) — lights hold their last state until it returns", e
                    )
                else:
                    logger.debug("olad connect attempt failed: %s", e)
                if sock is not None:
                    sock.close()
                self._stop_event.wait(RECONNECT_INTERVAL_SECS)
                continue

            with self._lock:
                self._wrapper = wrapper
                # (Re)connected: whatever we have is news to this olad
                self._dirty = True
            # Reset so a future outage logs immediately again
            last_disconnected_log_secs = float("-inf")
            logger.info("Connected to olad on universe %d", self._universe)

            try:
                self._run(wrapper)
            except (OLADNotRunningException, OSError) as e:
                logger.error("DMX I/O failed, reconnecting: %s", e)
            finally:
                with self._lock:
                    self._wrapper = None
                try:
                    sock.close()
                except OSError:
                    pass

            self._stop_event.wait(RECONNECT_INTERVAL_SECS)
        logger.info("DMX worker stopped")

    def _run(self, wrapper) -> None:
        """Drive one connection until stop() or a failure.

        Runs the wrapper's select loop the way OLA intends: it consumes
        every RPC response the moment it arrives, and our tick rides on the
        wrapper's own event scheduling. Failures raise out of Run() into
        _worker's reconnect path.
        """
        client = wrapper.Client()
        now = time.monotonic()
        self._last_send_secs = float("-inf")
        self._last_ack_secs = now
        self._outstanding_acks = 0
        self._last_health_log_secs = now

        def on_ack(status) -> None:
            now = time.monotonic()
            self._last_ack_secs = now
            self._outstanding_acks = max(0, self._outstanding_acks - 1)
            self._frames_acked += 1
            if not status.Succeeded():
                self._frames_rejected += 1
                if now - self._last_reject_log_secs >= REJECTED_LOG_INTERVAL_SECS:
                    self._last_reject_log_secs = now
                    logger.warning(
                        "olad rejected a DMX frame for universe %d (%s) — %d rejected total; "
                        "is anything patched to the universe?",
                        self._universe,
                        status.message,
                        self._frames_rejected,
                    )

        def tick() -> None:
            if self._stop_event.is_set():
                wrapper.Stop()
                return
            wrapper.AddEvent(TICK_INTERVAL_MS, tick)
            now = time.monotonic()

            if (
                self._outstanding_acks > 0
                and now - self._last_ack_secs > ACK_TIMEOUT_SECS
            ):
                raise TimeoutError(
                    f"olad stopped acking sends for {now - self._last_ack_secs:.1f}s "
                    f"({self._outstanding_acks} outstanding)"
                )

            with self._lock:
                dirty = self._dirty
                self._dirty = False
                data = array.array("B", self._channels)

            if dirty or now - self._last_send_secs >= KEEPALIVE_INTERVAL_SECS:
                if self._outstanding_acks == 0:
                    # The ack clock only matters while something is in
                    # flight; restart it so idle time doesn't count
                    self._last_ack_secs = now
                # Count before sending: the ack may arrive at any point
                # after SendDmx initiates, and must find itself counted
                self._outstanding_acks += 1
                if not client.SendDmx(self._universe, data, on_ack):
                    self._outstanding_acks -= 1
                    raise ConnectionError("SendDmx refused the frame (socket closed)")
                self._last_send_secs = now
                self._frames_sent += 1
                logger.debug(
                    "DMX frame sent (dirty=%s): %s...",
                    dirty,
                    data.tobytes()[: 4 * self._fixture_channel_width].hex(),
                )

            if now - self._last_health_log_secs >= HEALTH_LOG_INTERVAL_SECS:
                self._last_health_log_secs = now
                logger.info(
                    "DMX health: %d frames sent, %d acked, %d rejected, %d awaiting ack",
                    self._frames_sent,
                    self._frames_acked,
                    self._frames_rejected,
                    self._outstanding_acks,
                )

        wrapper.AddEvent(0, tick)
        wrapper.Run()


if __name__ == "__main__":
    # Bench smoke test: cycles red/green/blue on the first two fixtures.
    # Needs a running olad; ^C to quit.
    logging.basicConfig(level=logging.DEBUG)
    controller = DmxController()
    controller.start()
    try:
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        step = 0
        while True:
            for fixture_id in (0, 1):
                controller.set_fixture_colour(fixture_id, colors[step % 3])
            step += 1
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Exiting")
    finally:
        controller.stop()
