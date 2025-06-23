import asyncio
import threading
from queue import Empty, Queue

import jack
import numpy as np

##
## THIS DOESN'T WORK... YET
##
## THIS IS FROM EXPERIMENTS WITH ChatGPT
## A NEW SOUND CARD IS COMING, PERHAPS THAT WILL WORK BETTER?
##
## NOTE: JACK MAY BE TOO GRANULAR, PERHAPS SDL3?
##


class RingBuffer:
    def __init__(self, max_frames=48000 * 5):
        self.buffer = np.zeros(max_frames, dtype=np.float32)
        self.read_pos = 0
        self.write_pos = 0
        self.frames_available = 0
        self.lock = threading.Lock()

    def write(self, data):
        with self.lock:
            length = len(data)
            end_pos = (self.write_pos + length) % len(self.buffer)
            if end_pos < self.write_pos:
                first_chunk = len(self.buffer) - self.write_pos
                self.buffer[self.write_pos:] = data[:first_chunk]
                self.buffer[:end_pos] = data[first_chunk:]
            else:
                self.buffer[self.write_pos:end_pos] = data

            self.write_pos = end_pos
            self.frames_available = min(self.frames_available + length, len(self.buffer))

    def read(self, num_frames):
        with self.lock:
            if self.frames_available < num_frames:
                return np.zeros(num_frames, dtype=np.float32)

            end_pos = (self.read_pos + num_frames) % len(self.buffer)
            if end_pos < self.read_pos:
                out = np.concatenate((self.buffer[self.read_pos:], self.buffer[:end_pos]))
            else:
                out = self.buffer[self.read_pos:end_pos].copy()

            self.read_pos = end_pos
            self.frames_available -= num_frames
            return out


class SoundWorker:
    def __init__(self, queue: Queue, ringbuffer: RingBuffer):
        self.queue = queue
        self.ringbuffer = ringbuffer
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def _generate_sine_wave(self, freq=440.0, duration=0.5, rate=48000):
        t = np.linspace(0, duration, int(rate * duration), False)
        wave = 0.5 * np.sin(2 * np.pi * freq * t)
        return wave.astype(np.float32)

    def _run(self):
        print("[Worker] Sound worker started.")
        while self.running:
            try:
                command = self.queue.get(timeout=0.1)
                if command["action"] == "play":
                    print(f"[Worker] Loading sound: {command['sound']}")
                    wave = self._generate_sine_wave(freq=440.0)
                    self.ringbuffer.write(wave)
            except Empty:
                continue


class Game:
    def __init__(self, command_queue: Queue):
        self.queue = command_queue
        self.tick = 0

    async def run(self):
        while True:
            self.tick += 1
            print(f"[Game] Tick {self.tick}")

            if self.tick % 3 == 0:
                self.play_sound("ding.wav")

            await asyncio.sleep(1)

    def play_sound(self, sound_name: str):
        self.queue.put({"action": "play", "sound": sound_name})


def main():
    ringbuffer = RingBuffer()
    sound_queue = Queue()

    # JACK setup
    client = jack.Client("game_audio")
    out = client.outports.register("out")

    # Set sample rate and block size from JACK
    sample_rate = client.samplerate
    block_size = client.blocksize

    @client.set_process_callback
    def process(frames):
        buffer = ringbuffer.read(frames)
        out.get_buffer()[:] = buffer

    @client.set_shutdown_callback
    def shutdown(status, reason):
        print(f"[JACK] Shutdown: {reason}")

    # Start JACK
    client.activate()
    out.connect("system:playback_1")  # Connect to left speaker
    # Optionally: also connect to system:playback_2 for stereo

    # Start background components
    SoundWorker(sound_queue, ringbuffer)
    game = Game(sound_queue)

    try:
        asyncio.run(game.run())
    except KeyboardInterrupt:
        print("\n[System] Stopping...")
    finally:
        client.deactivate()
        client.close()


if __name__ == "__main__":
    main()

