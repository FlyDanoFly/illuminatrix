Lots has happened, and I think my other changes are in another branch. Doing this part 2 until I can get back and integrate.

## TODO
- **DONE** There's a bug is OXS where sometimes it won't stop, it'll inifinite loop 
	- Could be this is in linux too and I just haven't ever seen it?
	- I think I fixed it, it was a problem with the order in the `is_done`
- Add in streaming support
	- this may be an interesting thing with threads?
	- or better to have little sips synchronously? more control that way, but blocking on IO :-/
- Add in opus support and test, it might be best to use opus only for streaming stuff, I probably have enough storage and memory to handle uncompressed PCM data for the project
- Make sure the PI can't swap
- Put the PI in a throttled mode for testing to see if it still works
- **DONE** Add sound banks
	- override a `dict` to experiment with that
	- after a brief look, it looks to be a pain in the ass, gonna just make a helper that return a dict
- Add tag support, it could be useful, like "stop all game playing sounds and play the error sound"
- Make code work with mono files
	- Current workaround: encode to mono then back to stereo
- Add "PLAY TO ALL" option
- Add "ALWAYS_PLAY_TO_ALL" option in setup for simulation with OSX
- **DONE** Convert mixer to using `logging` 
	- Stretch goal, maybe ask the API for a crash course of changing logging levels
- Make the higher level API and integrate it with the code
- Make one of the simulations work with the new sound stuff
- **DONE** Make sure I can call `stop` on a sound and have it go away
	- A fade of 0.1 is nicer though, maybe make it a default? `smooth_stop` vs `hard_stop`?
- 
## Pitch shifted problem on OSX - Solved
Notes since last night:
1. OSX was playing pitch-shifted down, I realized that it was probably a sampling rate mismatch. Sure enough, Jack was configured on OSX with a sample rate of 44100
	1. To change it, edit:
		1. `/opt/homebrew/Cellar/jack/1.9.22_1/homebrew.mxcl.jack.plist`
			1. Note: for Intel it is likely in `/usr/local`
			2. Note: it is XML
		2. Add 2 lines in the `<key>ProgramArguments</key>` section:
			1. `<string>-p</string>`
			2. `<string>48000</string>
2. I don't know where it is configured on linux, perhaps it is a default
3. **TODO** Figure out if this is thing: pre-encode the audio to be the best for the audio card so the amount of conversion is minimized, the goal is to minimize the CPU usage
