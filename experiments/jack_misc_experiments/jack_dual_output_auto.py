import time

import jack
import numpy as np

client = jack.Client("dual_output_auto")

thingys = []
# out1 = client.outports.register("out1")
# out2 = client.outports.register("out2")

samplerate = client.samplerate
frequency = 440.0
duration = 3.0
samples = int(duration * samplerate)
t = np.arange(samples) / samplerate
# wave1 = 0.2 * np.sin(2 * np.pi * frequency * t).astype(np.float32)
# wave2 = 0.2 * np.sin(3 * np.pi * frequency * t).astype(np.float32)
frame_cursor = 0

@client.set_process_callback
def process(frames):
    global frame_cursor
    end = frame_cursor + frames
    # print("process", end, frame_cursor, frames)
    if thingys and end > len(thingys[0]["wave"]):
    # if end > len(wave1):
        for idx, thingy in enumerate(thingys):
            print(f"procss: {idx}")
            buf = thingy["out"].get_buffer()
            buf[:] = bytes(len(buf))
        # out1.get_buffer()[:] = bytes(len(out1.get_buffer()))
        # out2.get_buffer()[:] = bytes(len(out1.get_buffer()))
        return

    # chunk1 = wave1[frame_cursor:end]
    for thingy in thingys:
        # print(f"procss: {idx}")
        chunk = thingy["wave"][frame_cursor:end]
        thingy["out"].get_buffer()[:] = chunk

    # out1.get_buffer()[:] = chunk1
    # chunk2 = wave1[frame_cursor:end]
    # out2.get_buffer()[:] = chunk2
    frame_cursor = end

@client.set_shutdown_callback
def shutdown(status, reason):
    print("JACK shutdown:", reason)

client.activate()


# --- Auto-detect first two distinct physical playback outputs ---
ports = client.get_ports(is_audio=True, is_output=False)
# ports = client.get_ports(is_audio=True, is_physical=True, is_output=False)
print(ports)
card_groups = {}
for port in ports:
    # Group by card/device identifier before the colon
    card_id = port.name.split(':')[0]
    print("card_id",card_id,"port.name", port.name)
    if "capture" in port.name or "dual_output_auto" in port.name:
        print("skipping:", port)
        continue
    card_groups.setdefault(card_id, []).append(port.name)
print(card_groups)
# Pick two different cards
card_keys = list(sorted(card_groups.keys()))
print("card_keys", card_keys)
if len(card_keys) < 2:
    raise RuntimeError("Less than two sound cards found! Cannot proceed.")

print("Playing on:")
for idx, card_key in enumerate(card_keys, start=1):
    print("creating", idx)
    if idx != 2:
        continue
    for iidx, card_sub_key in enumerate(card_groups[card_key]):
        thingy = {
            "out":  client.outports.register(f"out{idx}{iidx}"),
            "wave": 0.2 * np.sin((idx + 0.5 * iidx) * np.pi * frequency * t).astype(np.float32),
        }
        thingys.append(thingy)
        client.connect(thingy["out"], card_sub_key)
        print(f" - {card_key} -> vv {card_sub_key}")
        # client.connect(thingy["out"], card_groups[card_key][0])
        # print(f" - {card_key} -> vv {card_groups[card_key][0]}")
    # if idx == 2:
    #     break
# Connect each output to the first channel of a different card
# client.connect(out1, card_groups[card_keys[0]][0])
# client.connect(out2, card_groups[card_keys[1]][0])

# print(f"Playing on:\n - {card_keys[0]} → {card_groups[card_keys[0]][0]}\n - {card_keys[1]} → {card_groups[card_keys[1]][0]}")
print("Playing for 1 seconds...")

time.sleep(1)

client.deactivate()
client.close()

