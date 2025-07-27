# import os
import logging
import threading
import time
import array

from ola.ClientWrapper import ClientWrapper
from ola.OlaClient import OLADNotRunningException


DEFAULT_WIDTH = 10
NUM_DMX_RETRIES = 3
DMX_SLEEP_RETRY_SECS = 0.3

CLI_FLASH_RATE_SECS = 1.5


class DmxController:
    """Controller for OLA DMX modules"""

    def __init__(self, universe=0, width=DEFAULT_WIDTH):
        """Setup"""
        self.universe = universe
        self.wrapper = ClientWrapper()
        self.client = self.wrapper.Client()
        self.channels = [0] * 512
        self.fixture_channel_width = width
        self.tick_interval = 25
        self.dmx_thread_should_run = True

    def _get_fixture_channels(self, fixture_id):
        """Returns the channel IDs of the fixture"""
        start = int((fixture_id * self.fixture_channel_width))
        return {
            'i': start + 0,
            'r': start + 1,
            'g': start + 2,
            'b': start + 3,
        }

    def _callback_dmx_sent(self, state):
        """Callback for DMX sent to controller"""
        if not state.Succeeded():
            self.wrapper.Stop()

    def set_fixture_colour(self, fixture_id, rgb):
        """Sets the colour on a fixture"""
        fixture_channels = self._get_fixture_channels(fixture_id)
        self.channels[fixture_channels['i']] = 255
        self.channels[fixture_channels['r']] = rgb[0]
        self.channels[fixture_channels['g']] = rgb[1]
        self.channels[fixture_channels['b']] = rgb[2]
        self._send_dmx_frame()

    def _send_dmx_frame(self):
        """Updates the fixtures"""
        logging.debug('Sending frame')
        self.wrapper.AddEvent(self.tick_interval, self._send_dmx_frame)
        # Seems the OLA daemon restarts every hour and crashes the program
        # Give it a couple retries
        for d in range(NUM_DMX_RETRIES):
            try:
                self.client.SendDmx(
                    self.universe,
                    array.array('B', self.channels),
                    self._callback_dmx_sent)
                break
            except OLADNotRunningException as e:
                print("!"*120)
                print("Caught the exception:", e)
                print(f"trying {NUM_DMX_RETRIES} times, that was try #{d+1}, recreating the objects then sleeping {DMX_SLEEP_RETRY_SECS }")
                self.wrapper = ClientWrapper()
                self.client = self.wrapper.Client()
                time.sleep(DMX_SLEEP_RETRY_SECS)
                # last time reraise the exception
                if d + 1 == NUM_DMX_RETRIES:
                    raise

    def _dmx_thread_master(self):
        """Thread for running DMX frames by hand"""
        # This is so I can learn and re-learn how this DMX controller works with the stage lights I bought
        # In short: the DMX controller listens starting at dXX - 1 (e.g. d01 listens at universe[0]) and
        # reads the next 7, the important ones are offests 0, 1, 2, 3 which is Intensity, Red, Green, Blue respectively
        # The rest offset 4-6 are for its special functions, like flashing or listening to audio
        next_sec: float = time.time() + CLI_FLASH_RATE_SECS
        cycle: int = 0
        while self.dmx_thread_should_run:
            channels = [0]*512
            channels[cycle+0] = 255
            channels[cycle+2] = 255
            self.channels = channels
            # print("yo:", cycle, self.channels[:20])
            time.sleep(self.tick_interval / 1000)
            curr_time = time.time()
            if next_sec < curr_time:
                print("Switching to cycle", cycle)
                print("Universe[:20]:", cycle, self.channels[:20])
                self.client.SendDmx(
                    self.universe,
                    # array.array('B', self.channels),
                    array.array('B', channels),
                    self._callback_dmx_sent)
                next_sec = curr_time + CLI_FLASH_RATE_SECS
                cycle += 1
                if cycle > 300:
                    cycle = 0
        logging.info('DMX master thread shutting down')

    def run(self):
        """Run the module"""
        self.dmx_thread = threading.Thread(name='dmx_thread', target=self._dmx_thread_master)
        self.dmx_thread.start()
    
    def terminate(self):
        """Terminates the module"""
        self.dmx_thread_should_run = False


if __name__ == '__main__':
    try:
        dc = DmxController()
        dc.run()
    except KeyboardInterrupt:
        print('Exiting')
