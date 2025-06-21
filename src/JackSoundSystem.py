"""Jack Sound System for Python - A simple sound mixer using JACK Audio Connection Kit and lightly mimicing the pygame interafce.

This is evolving from a very iterative process, needs a decent amount of cleanup.
Most important next goal is to get it running with a simulation.
"""

import logging
import signal
import sys
import threading
import time
import typing
from dataclasses import dataclass
from enum import Enum

import jack
import json5
import numpy
import soundfile

from constants import SystemIdentifier
from SoundSystem import SoundSystem

logger = logging.getLogger(__name__)


class MixerState(Enum):
    INIT = 0
    STARTED = 1
    STOPPED = 2
    SHUTDOWN = 3


class SoundType(Enum):
    SOUND = "sound"
    MUSIC = "music"
    AMBIENCE = "ambience"
    VOICE = "voice"


@dataclass
class SoundData:
    key: str
    filename: str
    sound_type: SoundType
    data: numpy.ndarray
    samplerate: int

    def create_sound(self, volume: float = 1.0, num_loops: int = 0) -> 'Sound':
        """Create a Sound object from this SoundData."""
        return Sound(data=self.data, samplerate=self.samplerate, volume=volume, num_loops=num_loops)


def load_sound_file(filename: str) -> tuple[numpy.ndarray, int]:
    """Load a sound file and return its data and samplerate."""
    try:
        data, samplerate = soundfile.read(filename, dtype='float32')
        if len(data.shape) > 1:
            # Convert multitrack to mono if needed
            # TODO: I'm trying to get mono but it breaks elsewhere in places in numpy I don't understand yet
            # TODO: I'll kludge it into mono then back to stereo (next if statement)
            # TODO: Learn what vectorizing is in numpy, I'm pretty sure it's applying a thing to an array at phenominal speeds (no python looks), underestand it and the calling mechanic
            # It actuall sounds pretty good, mono comes later
            data = data.sum(axis=1) / data.shape[1]
        if len(data.shape) == 1:
            # Leftover from ChatGPT, I think this goes in the wrong direction, I want mono
            # TODO: Currently needed to make the other code work, the code assumes the wave is stereo
            data = data[:, numpy.newaxis]  # mono to 2D
        return data, samplerate
    except Exception as e:
        logger.error("Error loading sound file %s: %s", filename, e)
        raise


def load_sound_bank(directory: str) -> dict[str, SoundData]:
    """Look for a sound_bank_manifest.json file in the directory, and if it exists, load the sounds listed in it."""
    sound_bank = {}
    manifest_file = f"{directory}/sound_bank_manifest.json"
    try:
        with open(manifest_file, 'r') as f:
            manifest = json5.load(f)
            for name, sound_info in manifest.items():
                filename = sound_info['file']
                full_path = f"{directory}/{filename}"
                sound_info['key'] = name
                match sound_info['type']:
                    case SoundType.SOUND.value:
                        pass  # sound_info['type'] = 'sound'  # This is the default, so we don't need to set it
                    case SoundType.MUSIC.value:
                        pass  # sound_info['type'] = 'music'
                    case SoundType.AMBIENCE.value:
                        pass  # sound_info['type'] = 'ambience'
                    case SoundType.VOICE.value:
                        pass  # sound_info['type'] = 'voice'
                    case _:
                        logger.warning("Unknown sound type %s for %s, defaulting to 'sound'", sound_info['type'], name)
                        sound_info['type'] = 'sound'

                # TODO: add support for other sound types, for now load everything as 'sound'
                data, samplerate = load_sound_file(full_path)
                sound_bank[name] = SoundData(
                    key=name,
                    filename=filename,
                    sound_type=SoundType(sound_info['type']),
                    data=data,
                    samplerate=samplerate,
                )
    except FileNotFoundError:
        logger.warning("No sound bank manifest found in %s", directory)
        raise
    except ValueError as e:
    # except json5.JSONDecodeError as e:
        logger.error("Error decoding JSON from sound bank manifest: %s", e)
        raise
    except KeyError as e:
        logger.error("Missing key in sound bank manifest: %s", e)
        raise
    return sound_bank


class Sound:
    def __init__(self, filename: str = '', data: numpy.ndarray | None = None, samplerate: int | None = None, volume: float = 1.0, num_loops: int = 0):
        """Initialize a Sound object.

        There are two ways to initialize a Sound object:
        1. From a file, using the filename parameter.
        2. From raw data, using the data and samplerate parameters.
        If both filename and data are provided, data and samplerate takes precedence.
        """
        self.data: numpy.ndarray
        self.samplerate: int

        if data is not None and samplerate is not None:
            # If data and samplerate are provided, use them directly
            self.data = data
            self.samplerate = samplerate
        elif filename:
            # If a filename is provided, read the sound file
            self.data, self.samplerate = load_sound_file(filename)
        else:
            raise ValueError("Either filename or data and samplerate must be provided")

        self.position: int = 0
        self.channels: int = self.data.shape[1]
        self.volume: float = volume
        self.loops: int = num_loops
        # TODO: if I get into adding reltime effects, make this an effect
        self.fade_out_active: bool = False
        self.fade_out_frames_remaining: int = 0
        self.fade_out_step: float = 0.0
        self.fade_out_comelete: bool = False
        self.fade_out_curve = numpy.linspace(1.0, 1.0, 1, dtype=numpy.float32)
        self.fade_out_index = 0

    def __del__(self):
        """Ensure resources are cleaned up."""
        print("Sound object is being deleted, cleaning up resources.")
        if hasattr(self, 'data'):
            del self.data
        if hasattr(self, 'fade_out_curve'):
            del self.fade_out_curve

    def is_done(self) -> bool:
        logger.debug("%r %r %r %r", self.loops > 0, self.fade_out_comelete, self.fade_out_active, self.position >= len(self.data))
        if self.fade_out_comelete:
            return True
        if self.fade_out_active:
            return False
        if self.loops > 0:
            return False
        return self.position >= len(self.data)

    def start_fade_out(self, duration_sec: float, samplerate: int) -> None:
        total_frames = int(duration_sec * samplerate)
        self.fade_out_curve = numpy.linspace(self.volume, 0.0, total_frames, dtype=numpy.float32)
        self.fade_out_index = 0
        self.fade_out_active = True

    def stop(self) -> None:
        """Stop the sound immediately, without fading out."""
        self.fade_out_active = False
        self.fade_out_comelete = True
        self.position = len(self.data)

    def mix_into(self, output_buffers: list[numpy.ndarray], channel_map: list[int]) -> None:
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
                fade_remaining = len(self.fade_out_curve) - self.fade_out_index
                fade_len = min(block_len, fade_remaining)
                fade_values = self.fade_out_curve[self.fade_out_index:self.fade_out_index+fade_len]
                samples = samples[:fade_len] * fade_values
                self.fade_out_index += fade_len
                if self.fade_out_index >= len(self.fade_out_curve):
                    self.fade_out_active = False
                    self.fade_out_comelete = True

                buf[:fade_len] += samples
                position += fade_len
            else:
                buf[:block_len] += samples * self.volume
                position += block_len

            if position >= len(self.data) and self.loops != 0:
                self.loops -= 1
                position = 0
        self.position = position


class JackMixer:
    def __init__(self, name: str = "jack_mixer", num_channels: int = 8):
        # TODO: perhaps make the channel auto detected, as well as the force to stereo?
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
        logger.info("Mixer started.")

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
        logger.info("Shutting down JACK mixer...")
        self.client.deactivate()
        self.client.close()
        logger.info("Mixer shut down cleanly.")

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


class JackSoundSystem(SoundSystem):
    def __init__(self, num_channels: int = 8):
        super().__init__()
        self.mixer = JackMixer(num_channels=num_channels)

    def startup(self) -> None:
        """Start the JACK mixer."""
        self.mixer.startup()

    def shutdown(self) -> None:
        """Shutdown the JACK mixer."""
        self.mixer.stop_all(fade_duration=1.0)
        # time.sleep(1.2)
        while self.mixer.is_anything_playing():
            logger.info("   fading %.3f", self.mixer.client.cpu_load())
            time.sleep(0.05)
        self.mixer.shutdown()

    def update(self, delta_ms: float) -> None:
        """Update the JACK mixer state."""
        # This method is not implemented in this example, as the mixer processes audio in its own thread.
        # If needed, you could implement periodic updates or checks here.
        # Perhaps dealing with streaming data?
        pass

    def render(self) -> None:
        """Render the current state of the JACK mixer."""
        # This method is not implemented in this example, as the mixer processes audio in its own thread.
        # If needed, you could implement periodic rendering or checks here.
        pass

    def load_sound_bank(self, directory: str) -> None:
        """Load a sound bank from the specified directory."""
        self.sound_bank = load_sound_bank(directory)

    def play(self, system_id: SystemIdentifier, sound: str) -> Sound:
        """Play a sound from the sound bank."""
        if sound not in self.sound_bank:
            raise ValueError(f"Sound {sound} not found in sound bank")
        sound_data = self.sound_bank[sound]
        snd = sound_data.create_sound()
        self.mixer.play(snd, [0])
        return snd


# === Usage Example ===
def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    mixer = JackMixer(num_channels=2)
    # mixer = JackMixer(num_channels=8)
    mixer.startup()

    sound_bank = load_sound_bank("sound_bank_1")
    snd1 = sound_bank["boom"].create_sound(volume=0.1, num_loops=10)  # Create a sound with volume and number of loops
    snd2 = sound_bank["boom"].create_sound(num_loops=-1)  # Loop forever

    # filename = "LRMonof32.wav"  # Default
    # if len(sys.argv) > 1:
    #     filename = sys.argv[1]
    # snd1 = Sound(filename, num_loops=10)
    # snd2 = Sound(filename, num_loops=-1)  # Loop forever

    stop_first_sound_time = 5.0 + time.time()
    mixer.play(snd1, [0])       # Play to channel 0
    time.sleep(1.0)
    mixer.play(snd2, [1])    # Play stereo sound to channels 2 and 3

    def shutdown_handler(*_) -> None:
        # handler(signal_number: int, frame: types.FrameType|None)
        # The handler is called with two arguments: the signal number and the
        # current stack frame (None or a frame object; for a description of
        # frame objects, see the description in the type hierarchy or see the
        # attribute descriptions in the inspect module).
        logger.info("\nSignal received, shutting down...")
        mixer.stop_all(fade_duration=1.0)
        # time.sleep(1.2)
        while mixer.is_anything_playing():
            logger.info("   fading %.3f", mixer.client.cpu_load())
            time.sleep(0.05)
        mixer.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        # Keep main thread alive while sounds play
        i = 0
        while mixer.is_anything_playing():
            logger.info("waiting for sounds to finish %d %.3f %.3f %r", i, mixer.client.cpu_load(), time.time()-stop_first_sound_time, snd1)
            if snd1 and time.time() > stop_first_sound_time:
                logger.info("Stopping first sound")
                logger.info("Stopping first sound")
                logger.info("Stopping first sound")
                logger.info("Stopping first sound")
                logger.info("Stopping first sound")
                snd1.start_fade_out(0.1, snd1.samplerate)
                # snd1.stop()
                snd1 = None
            time.sleep(0.5)
            i += 1
    except KeyboardInterrupt:
        logger.info("keyboardinterrupt received")

    mixer.shutdown()
    logger.info("that's it")

if __name__ == "__main__":
    main()
