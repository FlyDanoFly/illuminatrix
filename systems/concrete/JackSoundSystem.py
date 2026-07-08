"""Jack Sound System for Python - A simple sound mixer using JACK Audio Connection Kit and lightly mimicing the pygame interafce.

This is evolving from a very iterative process, needs a decent amount of cleanup.
Most important next goal is to get it running with a simulation.
"""

import logging
import random
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

from bases.SoundSystem import Sound, SoundSystem
from constants.constants import TowerEnum

logger = logging.getLogger(__name__)


JACKMIXER_USE_SERVER = True
JACK_SERVER_NAME = "illuminatrix_jack_server_mixer"

# Minimum time between attempts to (re)connect to the JACK server
JACK_RECONNECT_INTERVAL_SECS = 2.0
# While disconnected, repeat an ERROR at this interval so a silent
# installation is visible in the log stream, not just one line at startup
JACK_DISCONNECTED_LOG_INTERVAL_SECS = 30.0


class MixerState(Enum):
    INIT = 0
    STARTED = 1
    DISCONNECTED = 2
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

    def create_sound(self, volume: float = 1.0, num_loops: int = 0) -> Sound:
        """Create a Sound object from this SoundData."""
        # TODO: formalize the key, filename, and sound_type usage
        ranby = self.key + "-" + "".join(random.choice("abcdefghij") for _ in range(8))
        return JackSound(filename=ranby, data=self.data, samplerate=self.samplerate, volume=volume, num_loops=num_loops)


def load_sound_file(filename: str) -> tuple[numpy.ndarray, int]:
    """Load a sound file and return its data and samplerate."""
    try:
        data, samplerate = soundfile.read(filename, dtype='float32')
        if len(data.shape) > 1:
            logger.warning("Loaded multitrack sound file %s, converting to mono.", filename)
            data = data.sum(axis=1) / data.shape[1]
        return data, samplerate
    except Exception as e:
        logger.error("Error loading sound file %s: %s", filename, e)
        raise


def load_sound_bank(directory: str) -> dict[str, SoundData]:
    """
    Look for a sound_bank_manifest.json file in the directory, and if it exists, load the sounds listed in it.

    The manifest should be a JSON5 file with the following structure:
    [
        "sound_name": {
            "file": "path/to/sound/file.wav",
            "type": "sound"  # or "music", "ambience", "voice"
        },
        ...
    ]
    """
    sound_bank = {}
    manifest_file = f"{directory}/sound_bank_manifest.json"
    try:
        with open(manifest_file, 'r') as f:
            manifest = json5.load(f)
            for name, sound_info in manifest.items():
                filename = sound_info['file']
                full_path = f"{directory}/{filename}"
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
                file_start_secs = time.perf_counter()
                data, samplerate = load_sound_file(full_path)
                logger.debug(
                    "Loaded %s (%.1fs of audio) in %.2fs",
                    full_path, len(data) / samplerate, time.perf_counter() - file_start_secs,
                )
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


class JackSound(Sound):
    """A class representing a sound that can be played by the mixer.

    This class can be initialized from a file or raw data, and supports looping and volume control.
    It also supports fading out the sound over a specified duration.
    """
    def __init__(self, filename: str = '', data: numpy.ndarray | None = None, samplerate: int | None = None, volume: float = 1.0, num_loops: int = 0):
        """Initialize a Sound object.

        There are two ways to initialize a Sound object:
        1. From a file, using the filename parameter.
        2. From raw data, using the data and samplerate parameters.
        If both filename and data are provided, data and samplerate takes precedence.
        """
        self.data: numpy.ndarray
        self.samplerate: int
        # TODO: formalize the key, filename, and sound_type usage
        self.key: str = filename  # Use filename as key, can be overridden later
        if data is not None and samplerate is not None:
            # If data and samplerate are provided, use them directly
            self.data = data
            self.samplerate = samplerate
        elif filename:
            # If a filename is provided, read the sound file
            self.data, self.samplerate = load_sound_file(filename)
        else:
            raise ValueError("Either filename or data and samplerate must be provided")

        assert len(self.data.shape) == 1, "Sound data must be 1D (mono), got shape: {}".format(self.data.shape)
        self.channels: int = 1
        self.position: int = 0
        self.volume: float = volume
        self.loops: int = num_loops
        # TODO: if I get into adding reltime effects, make this an effect
        self.fade_out_active: bool = False
        self.fade_out_complete: bool = False
        self.fade_out_curve = numpy.linspace(1.0, 1.0, 1, dtype=numpy.float32)
        self.fade_out_index = 0

    def is_done(self) -> bool:
        # Called from the JACK process callback: keep it allocation- and
        # logging-free
        if self.fade_out_complete:
            return True
        if self.fade_out_active:
            return False
        if self.loops > 0:
            return False
        return self.position >= len(self.data)

    def start_fade_out(self, duration_sec: float) -> None:
        total_frames = int(duration_sec * self.samplerate)
        self.fade_out_curve = numpy.linspace(self.volume, 0.0, total_frames, dtype=numpy.float32)
        self.fade_out_index = 0
        self.fade_out_active = True

    def stop(self) -> None:
        """Stop the sound immediately, without fading out."""
        self.fade_out_active = False
        self.fade_out_complete = True
        self.position = len(self.data)

    def mix_into(self, output_buffers: list[numpy.ndarray], channel_map: list[TowerEnum]) -> None:
        """Mix this sound's next block into every mapped channel.

        The block (and its fade-curve segment) is computed once and added
        identically to each channel; per-sound state advances once per
        callback, no matter how many towers the sound plays on.
        """
        frames = len(output_buffers[0])
        position = self.position
        remaining = len(self.data) - position
        block_len = min(frames, remaining)
        samples = self.data[position:position + block_len]

        if self.fade_out_active or self.fade_out_complete:
            fade_remaining = len(self.fade_out_curve) - self.fade_out_index
            fade_len = min(block_len, fade_remaining)
            samples = samples[:fade_len] * self.fade_out_curve[self.fade_out_index:self.fade_out_index + fade_len]
            self.fade_out_index += fade_len
            if self.fade_out_index >= len(self.fade_out_curve) or fade_len <= 0:
                self.fade_out_active = False
                self.fade_out_complete = True
            advance = fade_len
        else:
            samples = samples * self.volume
            advance = block_len

        for target_channel in (tower_enum.value - 1 for tower_enum in channel_map):
            if target_channel >= len(output_buffers):
                continue
            output_buffers[target_channel][:advance] += samples

        position += advance
        if position >= len(self.data) and self.loops != 0:
            self.loops -= 1
            position = 0
        self.position = position


class JackMixer:
    """Mixes Sound objects into JACK output ports, one port per tower.

    Connection lives in startup(), not __init__, and failures degrade
    instead of raising: a missing JACK server costs sound output, never
    the process. update() — driven every frame by JackSoundSystem —
    notices a dead server, drops the sounds it can no longer finish, and
    retries the connection, rate limited.
    """

    def __init__(
            self,
            name: str = "jack_mixer",
            use_server: bool = JACKMIXER_USE_SERVER,
            servername: str = JACK_SERVER_NAME,
    ):
        # TODO: perhaps make the channel auto detected, as well as the force to stereo?
        self.name = name
        self.use_server = use_server
        self.servername = servername
        self.client: jack.Client | None = None
        self.outports: list[jack.OwnPort] = []
        self.active_sounds: list[tuple[Sound, list[TowerEnum]]] = []
        self.lock: threading.Lock = threading.Lock()
        self.state: MixerState = MixerState.INIT
        self.force_play_on_all_channels: bool = False
        # Set from JACK's shutdown-callback thread; handled in update()
        self._server_went_away: bool = False
        self._last_connect_attempt_secs: float = float("-inf")
        self._last_disconnected_log_secs: float = float("-inf")

    def process(self, _: int):
        # the parameter is the number of frames to process
        output_buffers = [
            numpy.frombuffer(port.get_buffer(), dtype=numpy.float32)
            for port in self.outports
        ]
        # Zero before the state check so the shutdown window plays
        # silence instead of repeating the last rendered buffer
        for buf in output_buffers:
            buf[:] = 0.0

        if self.state != MixerState.STARTED:
            return

        with self.lock:
            still_playing = []
            for sound, channel_map in self.active_sounds:
                sound.mix_into(output_buffers, channel_map)
                if not sound.is_done():
                    still_playing.append((sound, channel_map))
            self.active_sounds = still_playing

    def startup(self):
        if self.state != MixerState.INIT:
            raise RuntimeError("Mixer can only be started from INIT state")
        if self._try_connect():
            self.state = MixerState.STARTED
        else:
            self.state = MixerState.DISCONNECTED
            logger.error(
                "JACK server unavailable at startup — no sound until it appears, retrying"
            )

    def update(self) -> None:
        """Per-frame maintenance, driven by JackSoundSystem: notice a dead
        server, tear down its client, and reconnect (rate limited)."""
        if self.state not in (MixerState.STARTED, MixerState.DISCONNECTED):
            return
        if self._server_went_away:
            self._server_went_away = False
            logger.error(
                "JACK server went away — dropping %d active sounds, reconnecting",
                len(self.active_sounds),
            )
            self._teardown_client()
            self.state = MixerState.DISCONNECTED
        if self.state == MixerState.DISCONNECTED:
            if self._try_connect():
                self.state = MixerState.STARTED
            else:
                self._log_disconnected()

    def _try_connect(self) -> bool:
        """Open a client, register ports, activate. Rate limited so a dead
        server doesn't get hammered every frame."""
        now = time.monotonic()
        if now - self._last_connect_attempt_secs < JACK_RECONNECT_INTERVAL_SECS:
            return False
        self._last_connect_attempt_secs = now
        client = None
        try:
            if self.use_server:
                client = jack.Client(self.name, no_start_server=True, servername=self.servername)
            else:
                client = jack.Client(self.name)
            client.set_process_callback(self.process)
            client.set_shutdown_callback(self._on_server_shutdown)
            client.activate()
            ports = []
            system_ports = client.get_ports(is_physical=True, is_input=True, is_audio=True, is_midi=False)
            for i, system_port in enumerate(system_ports, start=1):
                outport = typing.cast("jack.OwnPort", client.outports.register(f"out_{i}"))
                client.connect(outport, system_port)
                ports.append(outport)
        except jack.JackError as e:
            logger.debug("JACK connect attempt failed: %s", e)
            if client is not None:
                try:
                    client.close()
                except jack.JackError:
                    pass
            return False
        self.force_play_on_all_channels = len(ports) == 2
        if self.force_play_on_all_channels:
            # If we have exactly two output ports, force them to be stereo
            logger.info("Stereo output detected, forcing stereo playback on all channels.")
        self.outports = ports
        self.client = client
        # Reset so a future outage logs immediately again
        self._last_disconnected_log_secs = float("-inf")
        logger.info("Mixer connected to JACK (%d outputs)", len(ports))
        return True

    def _on_server_shutdown(self, status, reason) -> None:
        # Called on JACK's thread; defer all teardown to update() on the
        # game loop, where the lock and client are safe to touch
        self._server_went_away = True

    def _log_disconnected(self) -> None:
        now = time.monotonic()
        if now - self._last_disconnected_log_secs < JACK_DISCONNECTED_LOG_INTERVAL_SECS:
            return
        self._last_disconnected_log_secs = now
        logger.error("JACK server unavailable — no sound until it returns")

    def _teardown_client(self) -> None:
        client, self.client = self.client, None
        self.outports = []
        with self.lock:
            # Sounds can't finish without process callbacks; games gating
            # on are_any_sounds_playing() must not wait forever
            self.active_sounds = []
        if client is None:
            return
        try:
            client.deactivate()
            client.close()
        except jack.JackError as e:
            logger.debug("Ignoring error closing dead JACK client: %s", e)

    def shutdown(self):
        if self.state in (MixerState.SHUTDOWN, MixerState.INIT):
            return
        self.state = MixerState.SHUTDOWN
        logger.info("Shutting down JACK mixer...")
        self._teardown_client()
        logger.info("Mixer shut down cleanly.")

    def play(self, sound: Sound, channel_map: list[TowerEnum] | TowerEnum | None = None):
        """Play a sound on the mixer.

        Args:
            sound (Sound): The sound to play.
            channel_map (list[TowerEnum]): A list of channel indices to play the sound on. Defaults to all channels.
        """
        if self.state == MixerState.INIT:
            raise RuntimeError("Mixer must be started to play sounds")
        if self.state != MixerState.STARTED:
            logger.warning("JACK not connected, dropping sound")
            return
        if channel_map is None or self.force_play_on_all_channels:
            channel_map = list(TowerEnum)
        if not isinstance(channel_map, list):
            channel_map = [channel_map]
        with self.lock:
            self.active_sounds.append((sound, channel_map))

    def stop_all(self, fade_secs: float = 0.5):
        with self.lock:
            for sound, _ in self.active_sounds:
                sound.start_fade_out(fade_secs)

    def is_anything_playing(self):
        return bool(self.active_sounds)


SHUTDOWN_FADE_SECS = 1.0
# Bound the shutdown fade wait: if the JACK server died mid-run the
# process callback never runs, sounds never finish, and an unbounded
# wait would hang the whole shutdown
SHUTDOWN_FADE_GRACE_SECS = 1.0


class JackSoundSystem(SoundSystem):
    def __init__(self, mixer: JackMixer, **_):
        super().__init__()
        self.mixer = mixer
        self.sound_bank: dict[str, SoundData] = {}

    def startup(self) -> None:
        """Start the JACK mixer (degrades to silence if the server is
        missing; the mixer keeps retrying from update())."""
        self.mixer.startup()

    def shutdown(self) -> None:
        """Fade everything out, then shut down the JACK mixer."""
        self.mixer.stop_all(fade_secs=SHUTDOWN_FADE_SECS)
        deadline = time.monotonic() + SHUTDOWN_FADE_SECS + SHUTDOWN_FADE_GRACE_SECS
        while self.mixer.is_anything_playing() and time.monotonic() < deadline:
            time.sleep(0.05)
        if self.mixer.is_anything_playing():
            logger.warning(
                "Sounds still playing %.1fs after the shutdown fade began, shutting down anyway",
                SHUTDOWN_FADE_SECS + SHUTDOWN_FADE_GRACE_SECS,
            )
        self.mixer.shutdown()

    def update(self, delta_secs: float) -> None:
        """Audio itself renders on JACK's thread; this drives the mixer's
        housekeeping (server-death detection and reconnect)."""
        self.mixer.update()

    def render(self) -> None:
        """Audio renders on JACK's thread; nothing to do per frame."""
        pass

    def load_sound_bank(self, path: str) -> None:
        """Load a sound bank from the specified directory, replacing the
        current bank. Synchronous and potentially slow (decodes every
        file to float32 in memory) — the timing log tells you how slow."""
        logger.info("Loading sound bank from %s", path)
        start_secs = time.perf_counter()
        self.sound_bank = load_sound_bank(path)
        elapsed_secs = time.perf_counter() - start_secs
        audio_secs = sum(len(sd.data) / sd.samplerate for sd in self.sound_bank.values())
        logger.info(
            "Loaded sound bank %s: %d sounds, %.1fs of audio, in %.2fs",
            path, len(self.sound_bank), audio_secs, elapsed_secs,
        )

    def play(
            self,
            sound: str,
            tower_enums: list[TowerEnum] | None = None,
            volume: float = 1.0,
            num_loops: int = 0) -> Sound | None:
        """Play a sound from the sound bank."""
        if sound not in self.sound_bank:
            logger.warning("Sound %s not found in sound bank", sound)
            return None
        play_on_tower_enums: list[TowerEnum] = tower_enums or list(TowerEnum)
        sound_data = self.sound_bank[sound]
        snd = sound_data.create_sound(volume=volume, num_loops=num_loops)
        self.mixer.play(snd, play_on_tower_enums)
        return snd

    def stop_all(self, fade_secs: float = 0.25):
        self.mixer.stop_all(fade_secs)

    def are_any_sounds_playing(self) -> bool:
        """Check if any sounds are currently playing."""
        return self.mixer.is_anything_playing()

# === Usage Example ===
def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    mixer = JackMixer()
    mixer.startup()

    sound_bank = load_sound_bank("sound_banks/lucy_whack_a_mole_1")
    snd1: Sound|None = sound_bank["boom"].create_sound(volume=0.1, num_loops=10)  # Create a sound with volume and number of loops
    snd2 = sound_bank["boom"].create_sound(num_loops=-1)  # Loop forever

    # filename = "LRMonof32.wav"  # Default
    # if len(sys.argv) > 1:
    #     filename = sys.argv[1]
    # snd1 = Sound(filename, num_loops=10)
    # snd2 = Sound(filename, num_loops=-1)  # Loop forever

    stop_first_sound_time = 5.0 + time.time()
    mixer.play(snd1, [TowerEnum.Tower_1])       # Play to channel 0
    time.sleep(1.0)
    mixer.play(snd2, [TowerEnum.Tower_2])    # Play stereo sound to channels 2 and 3

    def shutdown_handler(*_) -> None:
        # handler(signal_number: int, frame: types.FrameType|None)
        # The handler is called with two arguments: the signal number and the
        # current stack frame (None or a frame object; for a description of
        # frame objects, see the description in the type hierarchy or see the
        # attribute descriptions in the inspect module).
        logger.info("\nSignal received, shutting down...")
        mixer.stop_all(fade_secs=1.0)
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
                snd1.start_fade_out(0.1)
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
