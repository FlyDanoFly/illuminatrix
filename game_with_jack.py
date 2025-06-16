import asyncio
import threading
import time
from queue import Queue, Empty

##
## THIS DOESN'T WORK... YET
##
## THIS IS FROM EXPERIMENTS WITH ChatGPT
## A NEW SOUND CARD IS COMING, PERHAPS THAT WILL WORK BETTER?
##
## NOTE: JACK MAY BE TOO GRANULAR, PERHAPS SDL3?
##

# 🎵 Simulated JACK client that runs in its own thread
class MockJackClient:
    def __init__(self, command_queue: Queue):
        self.command_queue = command_queue
        self.running = False

    def start(self):
        self.running = True
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        print("[JACK] Worker started.")
        while self.running:
            try:
                command = self.command_queue.get(timeout=0.1)
                print(f"[JACK] Executing command: {command}")
                # Simulate audio action delay
                time.sleep(0.1)
            except Empty:
                continue

    def stop(self):
        self.running = False


# 📟 Async game logic
class Game:
    def __init__(self, sound_queue: Queue):
        self.sound_queue = sound_queue
        self.tick = 0

    async def run(self):
        while True:
            self.tick += 1
            print(f"[Game] Tick {self.tick}")

            # Every 3 ticks, play a sound on all stations
            if self.tick % 3 == 0:
                self.play_sound_all("ding")

            # Simulate station-specific logic
            if self.tick % 5 == 0:
                self.play_sound_station(2, "beep")

            await asyncio.sleep(1)

    def play_sound_all(self, sound: str):
        self.sound_queue.put({"target": "all", "action": "play", "sound": sound})

    def play_sound_station(self, station_id: int, sound: str):
        self.sound_queue.put({"target": station_id, "action": "play", "sound": sound})


# 🚀 Main entry point
def main():
    sound_queue = Queue()
    jack_client = MockJackClient(sound_queue)
    jack_client.start()

    game = Game(sound_queue)

    try:
        asyncio.run(game.run())
    except KeyboardInterrupt:
        print("\n[System] Shutting down.")
        jack_client.stop()


if __name__ == "__main__":
    main()

