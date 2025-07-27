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

CLI_FLASH_RATE_SECS = 0.5


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
        next_sec: float = time.time() + CLI_FLASH_RATE_SECS
        cycle: int = 0
        while self.dmx_thread_should_run:
            channels = [0]*512
            match cycle:
                case 0:
                    channels = [0] + [255, 255, 0, 0] * (512//4)
                case 1:
                    channels = [0] + [255, 0, 255, 0] * (512//4)
                case 2:
                    channels = [0] + [255, 0, 0, 255] * (512//4)
                case _:
                    raise RuntimeError("Bad cycle, should be [0-2]")
            # channels[0] = 250
            # channels[1] = 250
            # channels[2] = 0
            # channels[3] = 0
            # channels[4] = 0
            # channels[5] = 0
            # channels[6] = 0
            # channels[7] = 0
            # channels[8] = 0
            # channels[9] = 250
            # channels[10] = 0
            # channels[11] = 250
            # channels[12] = 0
            # channels[13] = 0
            self.channels = channels
            # channels = self.channels
            # print("yo:", self.channels[:20])
            # self.client.SendDmx(
            #     self.universe,
            #     # array.array('B', self.channels),
            #     array.array('B', channels),
            #     self._callback_dmx_sent)
            time.sleep(self.tick_interval / 1000)
            curr_time = time.time()
            if next_sec < curr_time:
                print("switching")
                self.client.SendDmx(
                    self.universe,
                    # array.array('B', self.channels),
                    array.array('B', channels),
                    self._callback_dmx_sent)
                next_sec = curr_time + CLI_FLASH_RATE_SECS
                cycle += 1
                if cycle > 2:
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
