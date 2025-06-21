**SUMMARY: SDL3 didn't work, and we got a killer jack mixer working**

Notes along the path

1. First going to try to get copilot to write me a command line to do something similar to the pop program I had. I'd break it out but my former laptop died.
2. Copilot says to install `pysdl3` so I did. It says to `import pysdl3` but that doesn't work. After some digging it appears the import should be `import sdl3`
3. I got a Python REPL
	1. `import sdl3`.
	2. `Warning: No metadata detected.`
	3. `Info: Downloading 'https://github.com/Aermoss/PySDL3-Build/releases/download/v3.2.16/Linux-ARM64-v3.2.16.zip'`
	4. This appears to be a one-time thing.
	5. Quitting and restarting, `import pysdl3` still dosent' work and `import sdl3` still does.
4. I got copilot to write a program to play sounds at random intervals each on a random channel.
	1. It said first to `Make sure your audio card is properly configured and detected by SDL.`
	2. I asked how and it wrote a program.
	3. I'm going to alter the program to use `sdl3` and try again
	4. Nope, doesn't work. Gonna try to get copilot to fix.
5.  I tried a lot of things with SDL3 and I'm not finding a lot of examples and copilot keeps writing code that doesn't work while claiming it fixes each mistake that I'm pointing out.
	1. There's a lot going on with SDL3
	2. Also, I've tried to poke around myself on my mac and on the rpi, it does seems like there are discrepancies between them
	3. I'm not set on SDL3, I thought it might be interesting and a high-enough level interface to make it easy.
	4. I might want to consider pygame, it has the kind of interface I'd like.
	5. But first I'll try something else with copilot's suggestion: python's `sounddevice` using `portaudio`

## sounddevice and portaudio
1. Install portaudio
	1. `sudo apt-get install portaudio19-dev libportaudio`
2. Install sounddevice and numpy
	1. `pip install sounddevice numpy`
3. This is working, and copilot is giving code that works
	1. Now going to try that one at random intervals on random channels
	2. Looks like it also wants `soundfile`, which I remember is often used with sounddevice
	3. `poetry add soundfile`
4. It works!
	1. It is called `test_sounddevice_random.py`

## Musings...
1. read up on `sounddevice` interface... probably too simple but can be a start 
2. try pygame
	1. from a quick try, copilot says it only supports 2 channels, the docs say 6
	2. 6 is still not enough
	3. TODO I installed pygame at a system level, I should uninstall it
	4. done, both system and poetry
3. tried pyo
	1. Not getting the system version `python3-pyo` to work properly
	2. it isn't detecting the number of channels proprly
	3. it is reported properly on sounddevice
	4. probaly worth another round
	5. 
4. remember to uninstall harfbuzz... I can't find it I'm pretty sure I did this.

## Breakthrough!
Talking with the AIs a bit. Mostly copilot and some ChatGPT, finding the balance between learning about what their suggestions are and trying things to see if they'll work. We started converging on "I want pygame's mixer model but for 8 channels." It gave me the basic setup code. Successive iterations have demonstrated that mixing two sounds into one channel is AOK.

Now we're evolving it into an audio subsystem. It's doing OK, it's suggesting things in directions that I'm going. I'm focusing on making the basics robust then dive more into the suggestions it is doing.

I'm trying to take care to learn enough about what it is suggesting and making better changes as we go. It is still really nice to have it output so much so I don't have to type quite so much. 

Def curious about taking this further.

OK, now have a mixer and sounds that can fade out, has a better lifecycle than my original style. TODO: make them all better like that but this is a cleanup nice-to-have.

**Efficiency**
Adding fade made this at least 10x slower than the original. An efficiency pass will be warranted. Or perhaps one better would be to run the processer in fast language, like Rust or C, and use the python interprocess communication between them. Let's give ChatGPT a quick attempt at it before moving on.

Turns out there's a bug with multiple channels that I just fixed.

It dawns on me that the `cpu_load()`function's range might be [0..100] and not [0.0..1.0] as I had originally assumed. The docs aren't clear. It is running flawlessly at values of 25 though. (I had thought >1.0 was bad, but that was when I had the multiple channels bug.)

OK, it gave me three ideas for efficiency
1. Instead of using a volume variable and multiply it by an array that is generated every frame and let numpy handle it. It onvolves more memory and also still has python for loops.
2. Instead of updating the volume once per frame, update it once per `process` update, it'll cut down on that one operation a LOT
3. More complex: lean on numpy to do transformations and skip the python for loops completely.

I'm intrigued by each. Gonna take a look.

1. Haven't tried this yet
	1. Definitely more expensive, goes from around 24 to around 28
	2. That's probably not a lot, but it adds up
	3. Note: there's a slight bug, there's a pop at the end of the fade, I'm guessing there's an off-by-one with the index and the array
		1. Got it!
		2. So it took a couple extra guards around the indexing, lots more comparisions. If I want to do this method i should clean this part up.
	4. Note to the future: this is probably what'll happen when an effect is applied
	5. Out of curiosity, I'll see if I can do it twice
		1. cpu_load around 37
		2. without is about 28
	6. **Conclusion: this is not worth it for a fade, but might be an avenue if there are processing effects, but maybe #3 is better?**
2. Volume once per frame vs volume once per update
	1. I can't tell the difference in either the quality or the processing load
	2. Doing it every frame is consistent and marginally more expensive, even when fading. I wonder if the `if` is kinda expensive?
	3. Doing in every update surges during fadeout to about every frame levels and is marginally cheaper overall
	4. **Conclusion: this is negligible**
3. Doing it all in numpy and skipping the Python loop
	1. Holy crap, first run is less than 1, just like in the beginning
	2. There's a bug in the fading...
		1. Race condition, the extra fade out math was checking only fade_out_active but there was (at least) one update where it was complete but not active, fixed with checking for both
	3. Still less that 1
	4. Fade out does surge just a little bit, but like 0.02-ish
	5. **Conclusion: holy cow! Clearly 10x superior, I'm going with this one**


## Effects suggested by ChatGPT - let's come back to these
### Effect Extensions You Can Easily Add
#### 🔊 1. **Fade-In**
Just like fade-out, precompute a fade-in curve:
- Add `fade_in_curve`, `fade_in_index`
- Modify `mix_into` to apply it for the first N frames
- Blend `fade_in` and `fade_out` together if both are active
#### 🎚️ 2. **Per-Channel Panning**

Add a pan factor per channel:
```python
channel_gains = [1.0, 0.8, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0]
```
Then
```python
buf[:len(samples)] += samples * channel_gains[i]
```
#### 3. **Volume Envelopes or ADSR**
Replace linear fades with more dynamic curves:
```python
self.fade_curve = np.logspace(0, -2, total_frames, base=10) * self.volume
```
#### 4. **Streaming / Infinite Playback**
For large files, read in chunks via `soundfile.blocks()` and use a ring buffer or chunk loader.
#### 5. **Realtime FX (Reverb, Delay, Filters)**
- Add optional FX chains per Sound
- Vectorized `samples = fx_chain(samples)`
- You can even use libraries like `scipy.signal` or [`rtmixer`](https://pypi.org/project/rtmixer/) 

## Mac
Now trying to get this code working on my mac.
1. First try late last night, it worked but the tone sounded too low
2. Today after sleeping and restarting, it's not working at all
	1. Maybe a restart?
3. Got it working, see [[Jack Mixer part 2]]