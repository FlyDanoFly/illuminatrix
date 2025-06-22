import sdl3

sdl3.init(sdl3.INIT_AUDIO)

num_devices = sdl3.audio.get_num_audio_devices(False)  # False = output devices

print(f"Found {num_devices} audio output device(s):")
for i in range(num_devices):
    name = sdl3.audio.get_audio_device_name(i, False)
    print(f"{i}: {name}")

sdl3.quit()
