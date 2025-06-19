import signal
import sys
import threading
import time
from enum import Enum

import jack
import numpy as np
import soundfile as sf


class LOOP_INFINITE:
    # Old trick to have a constant for an out-of-band value
    # To start my looping strategy is to have `loop` be then number
    # of loops left, so 0 needs to be a valid value.
    # This method makes infinite a constant, the alternative is 
    # the tried and true "a negative number means loop forever"
    # I'm in the mood to try this in this moment, I may change
    # it later.
    pass
 

class MixerState(Enum):
    INIT = 0
    STARTED = 1
    STOPPED = 2
    SHUTDOWN = 3


class Sound:
    def __init__(self, filename, volume=1.0, num_loops=0):
        self.data, self.samplerate = sf.read(filename, dtype='float32')
        if len(self.data.shape) == 1:
            self.data = self.data[:, np.newaxis]  # mono to 2D
        self.position = 0
        self.channels = self.data.shape[1]
        self.volume = volume
        self.loops = num_loops
        # TODO: if I get into adding reltime effects, make this an effect
        self.fade_out_active = False
        self.fade_out_frames_remaining = 0
        self.fade_out_step = 0.0
        self.fade_out_comelete: bool = False

    def is_done(self):
        return (
            not self.loops and (
                self.fade_out_comelete or
                self.position >= len(self.data) and
                not self.fade_out_active
            )
        )

    def start_fade_out(self, duration_sec: float, samplerate: int) -> None:
        self.fade_out_active = True
        self.fade_out_frames_remaining = int(duration_sec * samplerate)
        self.fade_out_step = self.volume / max(1, self.fade_out_frames_remaining)

    def mix_into(self, output_buffers, channel_map):
        frames = len(output_buffers[0])
        for i, target_channel in enumerate(channel_map):
            if target_channel >= len(output_buffers):
                continue
            buf = output_buffers[target_channel]
            for f in range(frames):
                if self.position >= len(self.data):
                    if self.loops:
                        self.position = 0
                        if self.loops is not LOOP_INFINITE:
                            self.loops -= 0
                    else:
                        break
                if self.volume >= 0.95:
                    sample = self.data[self.position, i % self.channels] * self.volume
                else:
                    sample = self.data[self.position, i % self.channels]
                sample = self.data[self.position, i % self.channels] * self.volume
                buf[f] += sample
                self.position += 1
                if self.fade_out_active:
                    self.volume -= self.fade_out_step
                    self.fade_out_frames_remaining -= 1
                    if self.fade_out_frames_remaining <= 0:
                        self.volume = 0.0
                        self.fade_out_active = False
                        self.fade_out_comelete = True
                        print("="*80)


class JackMixer:
    def __init__(self, name="jack_mixer", num_channels=8):
        self.client = jack.Client(name)
        self.num_channels = num_channels
        self.outports = [self.client.outports.register(f"out_{i}") for i in range(num_channels)]
        self.active_sounds = []
        self.lock = threading.Lock()
        self.state = MixerState.INIT
        self.client.set_process_callback(self.process)

    def process(self, frames):
        if self.state != MixerState.STARTED:
            return

        # Create empty output buffers
        output_buffers = [
            np.frombuffer(port.get_buffer(), dtype=np.float32)
            for port in self.outports
        ]
        for buf in output_buffers:
            buf[:] = 0.0

        with self.lock:
            still_playing = []
            for sound, channel_map in self.active_sounds:
                sound.mix_into(output_buffers, channel_map)
                if not sound.is_done():
                    still_playing.append((sound, channel_map))
            self.active_sounds = still_playing

    def startup(self, auto_connect=True):
        if self.state != MixerState.INIT:
            raise RuntimeError("Mixer can only be started from INIT state")
        self.client.activate()
        self.state = MixerState.STARTED
        if auto_connect:
            self._connect_to_physical_outputs()
        print("Mixer started.")

    def _connect_to_physical_outputs(self):
        # Auto-connect to physical outputs
        system_out = self.client.get_ports(is_physical=True, is_input=True)
        for i, port in enumerate(self.outports):
            if i < len(system_out):
                self.client.connect(port, system_out[i].name)

    def shutdown(self):
        if self.state in [MixerState.SHUTDOWN, MixerState.INIT]:
            return
        self.state = MixerState.SHUTDOWN
        print("Shutting down JACK mixer...")
        self.client.deactivate()
        self.client.close()
        print("Mixer shut down cleanly.")

    def play(self, sound: Sound, channel_map):
        if self.state != MixerState.STARTED:
            raise RuntimeError("Mixer must be started to play sounds")
        with self.lock:
            self.active_sounds.append((sound, channel_map))

    def stop_all(self, fade_duration=0.5):
        with self.lock:
            for sound, _ in self.active_sounds:
                sound.start_fade_out(fade_duration, self.client.samplerate)

    def is_anything_playing(self):
        return bool(self.active_sounds)

# === Usage Example ===
# if __name__ == "__main__":
def main():
    mixer = JackMixer(num_channels=8)
    mixer.startup()
    snd1 = Sound("LRMonoPhase4_8ch.wav")
    snd2 = Sound("LRMonoPhase4_8ch.wav")

    mixer.play(snd1, [0])       # Play to channel 0
    time.sleep(5.0)
    mixer.play(snd2, [1])    # Play stereo sound to channels 2 and 3
    # mixer.play(snd2, [2, 3])    # Play stereo sound to channels 2 and 3

    def shutdown_handler(sig, frame):
        print("\nSignal received, shutting down...")
        mixer.stop_all(fade_duration=1.0)
        # time.sleep(1.2)
        while mixer.is_anything_playing():
            print("fading")
            time.sleep(0.05)
        mixer.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)


    try:
        # Keep main thread alive while sounds play
        i = 0
        while mixer.is_anything_playing():
            print("waiting for sounds to finish", i, mixer.client.cpu_load())
            time.sleep(0.5)
            i += 1
    except KeyboardInterrupt:
        print("keyboardinterrupt received")

    # print("giving it a little extra time for a clean finish")
    # time.sleep(3)
    mixer.shutdown()
    print("and just a little more...")
    time.sleep(0.5)
    print("that's it")

if __name__ == "__main__":
    main()
