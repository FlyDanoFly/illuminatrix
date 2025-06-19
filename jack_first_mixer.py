import jack
import soundfile as sf
import numpy as np
import threading
import time

class Sound:
    def __init__(self, filename):
        self.data, self.samplerate = sf.read(filename, dtype='float32')
        if len(self.data.shape) == 1:
            self.data = self.data[:, np.newaxis]  # mono to 2D
        self.position = 0
        self.channels = self.data.shape[1]

    def is_done(self):
        return self.position >= len(self.data)

    def mix_into(self, output_buffers, channel_map):
        frames = len(output_buffers[0])
        for i, target_channel in enumerate(channel_map):
            if target_channel >= len(output_buffers):
                continue
            buf = output_buffers[target_channel]
            if self.position >= len(self.data):
                continue
            remaining = len(self.data) - self.position
            to_copy = min(frames, remaining)
            buf[:to_copy] += self.data[self.position:self.position+to_copy, i % self.channels]
        self.position += frames


class JackMixer:
    def __init__(self, name="jack_mixer", num_channels=8):
        self.client = jack.Client(name)
        self.num_channels = num_channels
        self.outports = [self.client.outports.register(f"out_{i}") for i in range(num_channels)]
        self.active_sounds = []
        self.lock = threading.Lock()
        self.client.set_process_callback(self.process)
        self.running = False

        # @self.client.set_process_callback
    def process(self, frames):
        if not self.running:
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

    def startup(self):
        if not self.running:
            self.client.activate()
        self.running = True
        self._connect_to_physical_outputs() 

    def _connect_to_physical_outputs(self):
        # Auto-connect to physical outputs
        system_out = self.client.get_ports(is_physical=True, is_input=True)
        for i, port in enumerate(self.outports):
            if i < len(system_out):
                self.client.connect(port, system_out[i].name)

    def shutdown(self):
        print("Shutting down JACK mixer...")
        self.running = False
        self.client.deactivate()
        self.client.close()

    def play(self, sound: Sound, channel_map):
        with self.lock:
            self.active_sounds.append((sound, channel_map))

    def is_anything_playing(self):
        return bool(self.active_sounds)

# === Usage Example ===
# if __name__ == "__main__":
def main():
    mixer = JackMixer(num_channels=8)
    mixer.startup()
    snd1 = Sound("LRMonoPhase4.wav")
    snd2 = Sound("LRMonoPhase4.wav")

    mixer.play(snd1, [0])       # Play to channel 0
    time.sleep(5.0)
    mixer.play(snd2, [0])    # Play stereo sound to channels 2 and 3
    # mixer.play(snd2, [2, 3])    # Play stereo sound to channels 2 and 3

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
