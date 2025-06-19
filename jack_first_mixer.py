import signal
import sys
import threading
import time
import typing
from enum import Enum

import jack
import numpy
import soundfile

# 0 == multipling by volume, doing it every frame during the fade out
# 1 == making an array to do the fadeout, still relies on python loops
# 2 == multiplying by volume, doing it once per update
# 3 == no python loops, do it all with numpy operations -- BEST by an order of magnitude, cpu_load goes done to 0.9 from 24-28ish
STYLE = 3


class MixerState(Enum):
    INIT = 0
    STARTED = 1
    STOPPED = 2
    SHUTDOWN = 3


class Sound:
    def __init__(self, filename: str, volume: float = 1.0, num_loops: int = 0):
        self.data: numpy.ndarray
        self.samplerate: int
        self.data, self.samplerate = soundfile.read(filename, dtype='float32')
        if len(self.data.shape) == 1:
            self.data = self.data[:, numpy.newaxis]  # mono to 2D
        self.position: int = 0
        self.channels: int = self.data.shape[1]
        self.volume: float = volume
        self.loops: int = num_loops
        # TODO: if I get into adding reltime effects, make this an effect
        self.fade_out_active: bool = False
        self.fade_out_frames_remaining: int = 0
        self.fade_out_step: float = 0.0
        self.fade_out_comelete: bool = False
        self.fade_out_1_curve = None
        self.fade_out_1_index = 0

    def is_done(self) -> bool:
        # print(self.loops > 0, self.fade_out_comelete, self.fade_out_active, self.position >= len(self.data))
        if self.loops > 0:
            return False
        if self.fade_out_comelete:
            return True
        if self.fade_out_active:
            return False
        return self.position >= len(self.data)

    def start_fade_out_0(self, duration_sec: float, samplerate: int) -> None:
        self.fade_out_active = True
        self.fade_out_frames_remaining = int(duration_sec * samplerate)
        self.fade_out_step = self.volume / max(1, self.fade_out_frames_remaining)

    def start_fade_out_1(self, duration_sec: float, samplerate: int) -> None:
        total_frames = int(duration_sec * samplerate)
        self.fade_out_1_curve = numpy.linspace(self.volume, 0.0, total_frames, dtype=numpy.float32)
        self.fade_out_1_index = 0
        self.fade_out_active = True

    def start_fade_out_2(self, duration_sec: float, samplerate: int) -> None:
        self.fade_out_active = True
        self.fade_out_frames_remaining = int(duration_sec * samplerate)
        self.fade_out_step = 1024*self.volume / max(1, self.fade_out_frames_remaining)

    def mix_into_0(self, output_buffers: list[numpy.ndarray], channel_map: list[int]) -> None:
        frames = len(output_buffers[0])
        for i, target_channel in enumerate(channel_map):
            if target_channel >= len(output_buffers):
                continue
            buf = output_buffers[target_channel]
            position = self.position
            for f in range(frames):
                if position >= len(self.data):
                    if self.loops > 0:
                        position = 0
                        if self.loops < 0:
                            self.loops -= 0
                    else:
                        break
                if self.volume >= 0.95:
                    sample = self.data[position, i % self.channels]
                else:
                    sample = self.data[position, i % self.channels] * self.volume
                buf[f] += sample
                position += 1
                if self.fade_out_active:
                    self.volume = max(0.0, self.volume - self.fade_out_step)
                    self.fade_out_frames_remaining -= 1
                    if self.fade_out_frames_remaining <= 0 or self.volume <= 0.0:
                        self.volume = 0.0
                        self.fade_out_active = False
                        self.fade_out_comelete = True
                        print("="*80)
        self.position += frames
 
    def mix_into_1(self, output_buffers: list[numpy.ndarray], channel_map: list[int]) -> None:
        frames = len(output_buffers[0])
        for i, target_channel in enumerate(channel_map):
            if target_channel >= len(output_buffers):
                continue
            buf = output_buffers[target_channel]
            position = self.position
            for f in range(frames):
                if position >= len(self.data):
                    if self.loops > 0:
                        position = 0
                        if self.loops < 0:
                            self.loops -= 0
                    else:
                        break
                # if self.volume >= 0.95:
                #     sample = self.data[position, i % self.channels]
                # else:
                #     sample = self.data[position, i % self.channels] * self.volume
                fade_multiplier = 1.0
                if self.fade_out_active and self.fade_out_1_index < len(self.fade_out_1_curve):
                    fade_multiplier = self.fade_out_1_curve[self.fade_out_1_index]
                elif self.fade_out_comelete or self.fade_out_active and self.fade_out_1_index >= len(self.fade_out_1_curve):
                    fade_multiplier = 0.0
                sample = self.data[position, i % self.channels] * fade_multiplier
                sample = self.data[position, i % self.channels] * fade_multiplier

                buf[f] += sample
                position += 1
                if self.fade_out_active:
                    self.fade_out_1_index += 1
                    if self.fade_out_1_index >= len(self.fade_out_1_curve):
                        self.fade_out_active = False
                        self.fade_out_comelete = True
        self.position += frames

    def mix_into_2(self, output_buffers: list[numpy.ndarray], channel_map: list[int]) -> None:
        frames = len(output_buffers[0])
        for i, target_channel in enumerate(channel_map):
            if target_channel >= len(output_buffers):
                continue
            buf = output_buffers[target_channel]
            position = self.position
            for f in range(frames):
                if position >= len(self.data):
                    if self.loops > 0:
                        position = 0
                        if self.loops < 0:
                            self.loops -= 0
                    else:
                        break
                if self.volume >= 0.95:
                    sample = self.data[position, i % self.channels]
                else:
                    sample = self.data[position, i % self.channels] * self.volume
                buf[f] += sample
                position += 1
        self.position += frames
        if self.fade_out_active:
            self.volume = max(0.0, self.volume - self.fade_out_step)
            self.fade_out_frames_remaining -= frames
            if self.fade_out_frames_remaining <= 0 or self.volume <= 0.0:
                self.volume = 0.0
                self.fade_out_active = False
                self.fade_out_comelete = True

    def mix_into_3(self, output_buffers: list[numpy.ndarray], channel_map: list[int]) -> None:
        frames = len(output_buffers[0])
        position = self.position
        for i, target_channel in enumerate(channel_map):
            if target_channel >= len(output_buffers):
                continue
            buf = output_buffers[target_channel]
            position = self.position
            remaining = len(self.data) - position
            block_len = min(frames, remaining)

            samples = self.data[position:position+block_len, i % self.channels]

            if self.fade_out_active or self.fade_out_comelete:
                fade_remaining = len(self.fade_out_1_curve) - self.fade_out_1_index
                fade_len = min(block_len, fade_remaining)
                fade_values = self.fade_out_1_curve[self.fade_out_1_index:self.fade_out_1_index+fade_len]
                samples = samples[:fade_len] * fade_values
                self.fade_out_1_index += fade_len
                if self.fade_out_1_index >= len(self.fade_out_1_curve):
                    self.fade_out_active = False
                    self.fade_out_comelete = True

                buf[:fade_len] += samples
                position += fade_len
            else:
                buf[:block_len] += samples * self.volume
                position += block_len

            if position >= len(self.data) and self.loops > 0:
                self.loops -= 1
                position = 0
        self.position = position


class JackMixer:
    def __init__(self, name: str = "jack_mixer", num_channels: int = 8):
        self.client: jack.Client = jack.Client(name)
        self.num_channels: int = num_channels
        self.outports: list[jack.OwnPort] = [typing.cast("jack.OwnPort", self.client.outports.register(f"out_{i}")) for i in range(num_channels)]
        self.active_sounds: list[tuple[Sound, list[int]]] = []
        self.lock: threading.Lock = threading.Lock()
        self.state: MixerState = MixerState.INIT
        self.shutdown_called: bool = False
        self.client.set_process_callback(self.process)

    def process(self, _: int):
        # the parameter is the number of frames to process
        if self.state != MixerState.STARTED:
            return

        # Create empty output buffers

        output_buffers = [
            numpy.frombuffer(port.get_buffer(), dtype=numpy.float32)
            for port in self.outports
        ]
        for buf in output_buffers:
            buf[:] = 0.0

        with self.lock:
            still_playing = []
            for sound, channel_map in self.active_sounds:
                if STYLE == 0:
                    sound.mix_into_0(output_buffers, channel_map)
                elif STYLE == 1:
                    sound.mix_into_1(output_buffers, channel_map)
                elif STYLE == 2:
                    sound.mix_into_2(output_buffers, channel_map)
                elif STYLE == 3:
                    sound.mix_into_3(output_buffers, channel_map)
                else:
                    RuntimeError("Invalid STYLE")
                # sound.mix_into(output_buffers, channel_map)
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
        if self.shutdown_called or self.state in [MixerState.SHUTDOWN, MixerState.INIT]:
            return
        self.shutdown_called = True
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
                if STYLE == 0:
                    sound.start_fade_out_0(fade_duration, self.client.samplerate)
                elif STYLE == 1:
                    sound.start_fade_out_1(fade_duration, self.client.samplerate)
                elif STYLE == 2:
                    sound.start_fade_out_2(fade_duration, self.client.samplerate)
                elif STYLE == 3:
                    sound.start_fade_out_1(fade_duration, self.client.samplerate)
                else:
                    RuntimeError("Invalid STYLE")

    def is_anything_playing(self):
        return bool(self.active_sounds)

# === Usage Example ===
# if __name__ == "__main__":
def main():
    mixer = JackMixer(num_channels=8)
    mixer.startup()
    snd1 = Sound("LRMonoPhase4_8ch.wav")
    snd2 = Sound("LRMonoPhase4_8ch.wav")

    mixer.play(snd1, [0,6])       # Play to channel 0
    time.sleep(1.0)
    mixer.play(snd2, [1, 6, 4])    # Play stereo sound to channels 2 and 3
    # mixer.play(snd2, [2, 3])    # Play stereo sound to channels 2 and 3

    def shutdown_handler(*_) -> None:
        # handler(signal_number: int, frame: types.FrameType|None)
        # The handler is called with two arguments: the signal number and the
        # current stack frame (None or a frame object; for a description of
        # frame objects, see the description in the type hierarchy or see the
        # attribute descriptions in the inspect module).
        print("\nSignal received, shutting down...")
        mixer.stop_all(fade_duration=1.0)
        # time.sleep(1.2)
        while mixer.is_anything_playing():
            print("fading", mixer.client.cpu_load())
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

    mixer.shutdown()
    print("that's it")

if __name__ == "__main__":
    main()
