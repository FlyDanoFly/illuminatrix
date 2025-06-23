import sounddevice as sd


def list_output_devices():
    print("Available audio output devices:\n")
    devices = sd.query_devices()
    for idx, device in enumerate(devices):
        if device['max_output_channels'] > 0:
            print(f"#{idx}: {device['name']}")
            print(f"    Max output channels: {device['max_output_channels']}")
            print(f"    Host API: {sd.query_hostapis()[device['hostapi']]['name']}")
            print()

if __name__ == "__main__":
    list_output_devices()

