"""Tests for DmxController — fake wrapper/client, no olad, no threads.

The worker's per-connection loop (_run) is driven synchronously: the fake
wrapper executes scheduled events in order for a bounded number of ticks,
and the fake client acks immediately, so every send/ack/dirty interaction
is deterministic.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from systems.concrete.dmx_controller import (  # noqa: E402
    ACK_TIMEOUT_SECS,
    DmxController,
)


class FakeStatus:
    def __init__(self, succeeded: bool = True):
        self._succeeded = succeeded
        self.message = None if succeeded else "fake rejection"

    def Succeeded(self) -> bool:
        return self._succeeded


class FakeClient:
    def __init__(self):
        self.sent: list[tuple[int, bytes]] = []
        self.accept_sends = True
        self.ack_sends = True
        self.ack_succeeds = True

    def SendDmx(self, universe, data, callback) -> bool:
        if not self.accept_sends:
            return False
        self.sent.append((universe, data.tobytes()))
        if self.ack_sends:
            callback(FakeStatus(self.ack_succeeds))
        return True


class FakeWrapper:
    """Executes scheduled events immediately, in order, up to max_ticks.

    between_ticks(tick_number) runs after each event, standing in for
    "things the main thread did while the worker slept".
    """

    def __init__(self, client, max_ticks: int = 5, between_ticks=None):
        self._client = client
        self._max_ticks = max_ticks
        self._between_ticks = between_ticks
        self._events = []
        self._running = False

    def Client(self):
        return self._client

    def AddEvent(self, _time_in_ms, callback) -> None:
        self._events.append(callback)

    def Stop(self) -> None:
        self._running = False

    def Run(self) -> None:
        self._running = True
        ticks = 0
        while self._running and self._events and ticks < self._max_ticks:
            ticks += 1
            self._events.pop(0)()
            if self._between_ticks is not None:
                self._between_ticks(ticks)


class TestChannelBuffer(unittest.TestCase):
    def test_set_fixture_colour_writes_intensity_and_rgb(self):
        controller = DmxController(fixture_channel_width=10)
        controller.set_fixture_colour(3, (10, 20, 30))
        base = 30
        self.assertEqual(controller._channels[base], 255)
        self.assertEqual(bytes(controller._channels[base + 1 : base + 4]), bytes([10, 20, 30]))

    def test_other_channels_stay_zero(self):
        controller = DmxController(fixture_channel_width=10)
        controller.set_fixture_colour(1, (9, 9, 9))
        untouched = bytes(controller._channels[:10]) + bytes(controller._channels[14:])
        self.assertEqual(untouched, bytes(len(untouched)))

    def test_set_fixture_colour_marks_dirty(self):
        controller = DmxController()
        controller._dirty = False
        controller.set_fixture_colour(0, (1, 2, 3))
        self.assertTrue(controller._dirty)


class TestRunLoop(unittest.TestCase):
    def test_initial_frame_sent_once_then_quiet(self):
        # Starts dirty, so the first tick sends; later ticks have nothing
        # new and the keepalive is not yet due
        controller = DmxController(universe=7)
        client = FakeClient()
        controller._run(FakeWrapper(client, max_ticks=5))
        self.assertEqual(len(client.sent), 1)
        universe, _frame = client.sent[0]
        self.assertEqual(universe, 7)

    def test_dirty_between_ticks_triggers_send_with_latest_data(self):
        controller = DmxController(fixture_channel_width=10)
        client = FakeClient()

        def between_ticks(tick):
            if tick == 2:
                controller.set_fixture_colour(0, (40, 50, 60))

        controller._run(FakeWrapper(client, max_ticks=5, between_ticks=between_ticks))
        self.assertEqual(len(client.sent), 2)
        _universe, frame = client.sent[-1]
        self.assertEqual(frame[0], 255)
        self.assertEqual(frame[1:4], bytes([40, 50, 60]))

    def test_latest_wins_between_ticks(self):
        # Two updates during one sleep produce one send with the second value
        controller = DmxController(fixture_channel_width=10)
        client = FakeClient()

        def between_ticks(tick):
            if tick == 2:
                controller.set_fixture_colour(0, (1, 1, 1))
                controller.set_fixture_colour(0, (2, 2, 2))

        controller._run(FakeWrapper(client, max_ticks=5, between_ticks=between_ticks))
        self.assertEqual(len(client.sent), 2)
        self.assertEqual(client.sent[-1][1][1:4], bytes([2, 2, 2]))

    def test_refused_send_raises_for_reconnect(self):
        controller = DmxController()
        client = FakeClient()
        client.accept_sends = False
        with self.assertRaises(ConnectionError):
            controller._run(FakeWrapper(client, max_ticks=5))

    def test_missing_acks_time_out(self):
        # olad accepts writes but never replies: after the ack window
        # passes, the run loop must raise so the worker reconnects
        controller = DmxController()
        client = FakeClient()
        client.ack_sends = False

        def between_ticks(_tick):
            # Backdate the last ack instead of sleeping through the window
            controller._last_ack_secs -= ACK_TIMEOUT_SECS + 1.0

        with self.assertRaises(TimeoutError):
            controller._run(FakeWrapper(client, max_ticks=5, between_ticks=between_ticks))

    def test_acked_sends_do_not_time_out(self):
        controller = DmxController()
        client = FakeClient()
        # Same backdating as above, but acks arrive: on_ack refreshes the
        # clock and clears the outstanding count, so no timeout fires
        sent_before = 0

        def between_ticks(_tick):
            controller._last_ack_secs -= ACK_TIMEOUT_SECS + 1.0

        controller._run(FakeWrapper(client, max_ticks=5, between_ticks=between_ticks))
        self.assertGreaterEqual(len(client.sent), sent_before)

    def test_rejected_frames_counted_but_not_fatal(self):
        # A NACK (e.g. nothing patched to the universe) is a config
        # problem, not a connection problem: keep sending, count it
        controller = DmxController()
        client = FakeClient()
        client.ack_succeeds = False

        def between_ticks(_tick):
            controller.set_fixture_colour(0, (1, 2, 3))

        controller._run(FakeWrapper(client, max_ticks=5, between_ticks=between_ticks))
        self.assertGreater(len(client.sent), 1)
        self.assertEqual(controller._frames_rejected, len(client.sent))

    def test_stop_event_stops_the_wrapper(self):
        controller = DmxController()
        client = FakeClient()
        wrapper = FakeWrapper(client, max_ticks=10)

        def between_ticks(tick):
            if tick == 2:
                controller._stop_event.set()

        wrapper._between_ticks = between_ticks
        controller._run(wrapper)
        self.assertFalse(wrapper._running)


class TestLifecycle(unittest.TestCase):
    def test_stop_without_start_is_safe(self):
        DmxController().stop()

    def test_full_frame_resent_after_reconnect(self):
        # _worker marks dirty on every connect; simulate by checking that
        # a fresh _run after a clean one sends even with no new colors
        controller = DmxController()
        client = FakeClient()
        controller._run(FakeWrapper(client, max_ticks=3))
        self.assertEqual(len(client.sent), 1)
        with controller._lock:
            controller._dirty = True  # what _worker does on reconnect
        controller._run(FakeWrapper(client, max_ticks=3))
        self.assertEqual(len(client.sent), 2)


if __name__ == "__main__":
    unittest.main()
