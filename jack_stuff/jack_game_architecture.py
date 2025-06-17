import asyncio
import threading
import time
import numpy as np
from queue import Queue, Empty


##
## THIS DOESN'T WORK... YET
##
## THIS IS FROM EXPERIMENTS WITH ChatGPT
## A NEW SOUND CARD IS COMING, PERHAPS THAT WILL WORK BETTER?
##
## NOTE: JACK MAY BE TOO GRANULAR, PERHAPS SDL3?
##


# 🎵 Shared ring buffer to simulate audio playback buffer
class RingBuffer:
    def __init__(self, max_frames=48000):
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


# 🧠 Simulated JACK client (just a loop calling a "process" callback)
class MockJackClient:
    def __init__(self, ringbuffer, frame_size=128, rate=48000):
        self.ringbuffer = ringbuffer
        self.frame_size = frame_size
        self.running = False
        self.rate = rate

    def start(self):
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        print("[JACK] Started simulated process loop.")
        frame_duration = self.frame_size / self.rate
        while self.running:
            self.process(self.frame_size)
            time.sleep(frame_duration)

    def process(self, frames):
        audio_data = self.ringbuffer.read(frames)
        if np.any(audio_data):
            print(f"[JACK] Playing {frames} frames")
        else:
            print("[JACK] Silence")

    def stop(self):
        self.running = False


# 👷 Worker thread to load sound data (mocked with sine wave)
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
                    wave = self._generate_sine_wave(freq=440.0)  # mock load
                    self.ringbuffer.write(wave)
            except Empty:
                continue


# 🎮 Async game loop
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


# 🚀 Main
def main():
    ringbuffer = RingBuffer()
    sound_queue = Queue()

    # Start JACK simulation
    jack = MockJackClient(ringbuffer)
    jack.start()

    # Start sound worker
    SoundWorker(sound_queue, ringbuffer)

    # Start game loop
    game = Game(sound_queue)
    try:
        asyncio.run(game.run())
    except KeyboardInterrupt:
        print("\n[System] Shutting down.")
        jack.stop()


if __name__ == "__main__":
    main()

