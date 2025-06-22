First take: the documentation isn't super straight forward so I expect I'll be doing some trial and error.

It is interesting to note that it worked out of the box with `aplay`, though it was hard to tell if it one could direct the sound to the other ports.

My linux version is `6.12.25+rpt-rpi-2712`
My HiFiBerry device:
- HiFiBerry DAC8x
- https://www.hifiberry.com/shop/boards/hifiberry-dac8x/

# Try 1 - Do the linux 4.x section first
Reference: https://www.hifiberry.com/docs/software/configuring-linux-3-18-x/
1. It says if you've configured the correct overlay and the driver isn't loaded then you may need to `force_eeprom_read=0`. ooohhh. This is when I come straight to the "Linux 5.4 and Higher section". I think it expects that you do the 4.x section first, trying that.
2. Commenting out the line
	1.  `dtparam=audio=on`
3. Disabling the `vc4-kms-v3d` driver
	1. `dtoverlay=vc4-kms-v3d,noaudio`
4. It has a blurb about Pi5 some overlays needed to be adapted and then it lists specific ones, mine is not in the list: `DAC+ Standard, DAC+ Pro, DAC2 Pro, DAC+ ADC`. I am skipping this part, assuming that I don't need it.
5. Instead, adding the DAC8x overlay
	1. `dtoverlay=hifiberry-dac8x`
6. There are only 3 matches for `8x`, one of which is invisible.
7. OK, trying to reboot and see what happens
8. It didn't work, error
	1. `aplay LRMonoPhase4.wav`
	2. `aplay: main:831: audio open error: Invalid argument`
9. It might be picky about audio input, going to try mplayer like is suggested here https://www.hifiberry.com/docs/software/playing-test-sounds/
10. Trying again with mplayer, error
	1. `mplayer LRMonoPhase4.wav`
	2. `mplayer LRMonoPhase4.wav`
	3. `MPlayer UNKNOWN-12 (C) 2000-2023 MPlayer Team`
	4. `do_connect: could not connect to socket` (this was there before)
	5. `connect: No such file or directory.`  (this was there before)
	6. `Failed to open LIRC support. You will not be able to use your remote control.` (I'm pretty sure this line is mplayer generic and nothing to do with the sound card)
11. Oh yea, check it out with `aplay`
	1. `$ aplay -l`
	2. `**** List of PLAYBACK Hardware Devices ****`
	3. `card 0: sndrpihifiberry [snd_rpi_hifiberry_dac8x], device 0: HifiBerry DAC8x HiFi snd-soc-dummy-dai-0 []`
	4. `  Subdevices: 1/1`
	5. `  Subdevice #0: subdevice #0`
12. Adding debugging and installing vcdbg (oops, two things at once)
	1. Adding `dtdebug=1` to the `config.txt` file
	2. Reboot
	3. ...and it worked
13. Checking it out with `afplay` again
	1.  `$  aplay -l`
	2. `**** List of PLAYBACK Hardware Devices ****`
	3. `card 0: sndrpihifiberry [snd_rpi_hifiberry_dac8x], device 0: HifiBerry DAC8x HiFi snd-soc-dummy-dai-0 [HifiBerry DAC8x HiFi snd-soc-dummy-dai-0]`
	4. `  Subdevices: 1/1`
	5. `  Subdevice #0: subdevice #0`
14. Commenting out `dtdebug=1` and rebooting and seeing where we're at
	1. It works
	2. Was it installing `vcdbg`?
15. Trying to uninstall `vcdbg` and seeing what happens
	1. huh, it installed a LOT of things, but it only removed one
	2. And doing `autoremove` didn't do anything 
	3. Gonna try a reboot and check the sound
	4. It didn't work
16. Trying to install `vcdbg` again and rebooting
	1. OK, it isn't installing a lot in terms of packages, it's enumerating all the files
	2. Yet it works fine now, something about installing that package
	3. I'm not interested in the moment to figure out what exactly is different, it could be one of these files
		1. `The following additional packages will be installed:`
		2. `  libraspberrypi0:armhf libstdc++6:armhf raspberrypi-bootloader raspberrypi-kernel`
		3. `The following NEW packages will be installed:`
		4. `  libraspberrypi0:armhf libstdc++6:armhf raspberrypi-bootloader raspberrypi-kernel vcdbg:armhf`
	4. Let's see the output of `sudo vcdbg log msg`
		1. It is said with turning on `dtdebug=1` I'm trying without it 
		2. `sudo vcdbg log msg`
		3. `Segmentation fault`
		4. maybe it does need the debug thing?
	5. Let's see if we can play on another port
		1. Can't figue it out
		2. Confirmed there should be only one sound card with `aplay -l`
	6. It says try Sox to do 8 channel sine wave...
		1. IT WORKS!!!!!
	7. OK, so see if SDL can do multiple channels, and if not perhaps have to go back to Jack
	8. 