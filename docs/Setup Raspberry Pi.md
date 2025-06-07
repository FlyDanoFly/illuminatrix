## Specs
**Raspberry Pi 5**
- 8 Gigs of memory
**MicroSD**
- Amazon Basics Micro SDXC Memory Card with Full Size Adapter, A2, U3, Read Speed up to 100 MB/s, 128 GB, Black

## Format MicroSD Card
1. On my work mac (for convenience)
2. Using Raspberry Pi Imager
3. Main Options
	1. Device: Raspberry Pi 5
	2. OS: Raspberry Pi OS Lite (64-bit)
4. Configuration
	1. **General**
		1. **Hostname:** `illuminatrix`
		2. **Username and password**
			1. **username:** dano
			2. **password:** illuminatrix#7
		3. **Configure wireless LAN**
			1. **SSID:** mudita
			2. **Password:** `<standard password>`
			3. **Wireless LAN country:** US
		4. **Set locale settings**
			1. **Time zone:** America/Los_Angeles
			2. **Keyboard layout:** us
	2. **Services**
		1. **Enable SSH:** True
		2. **Use password authentication** (will set up public-key authentication later)
	3. **Options** - irrelevant, these are options when formatting is done
5. Waiting...
	1. To write and verify it took about: 1:25

## First Configuration
**Network**
- Note: I had already set the router to auto assign an IP and my pihole to serve a name for it
- IP: `192.168.42.179`
- Network name: `illumantrix.lan`

**Housekeeping**
1. **Update**
	1. `apt update`
	2. `apt full-upgrade`
2. **Put ghostty terminal compatibility**
	1. On my arch machine
		1. Reference: https://ghostty.org/docs/help/terminfo#copy-ghostty's-terminfo-to-a-remote-machine
		2. `infocmp -x xterm-ghostty | ssh illuminatrix.lan -- tic -x -`
		3. Note: The `tic` command on the server may give the warning `"<stdin>", line 2, col 31, terminal 'xterm-ghostty': older tic versions may treat the description field as an alias` which can be safely ignored.
3. **Copy over public SSH keys to make login easier**
	1. `ssh-copy-id dano@illuminatrix.lan`
	2. (longer message saying it worked, now test)
	3. Both worked: `ssh dano@illuminatrix.lan` and `ssh dano@192.168.42.179`
4. **Reboot**
5. **Install some critical programs, NOTE: Putting install scripts in `~/installs`**
	1. **git**
		1. `sudo install git`
	2. **ripgrep**
		1. `script --append ripgrep.install.txt --command "sudo apt install ripgrep"`
	3. **npm (will also get nodejs)**
		1. `script --append npm.install.txt --command "sudo apt install npm"`
		2. Needed for `pyright` and probably a bazillion other things
	4. **pipx & pipx support**
		1. `script --append pipx.install.txt --command "sudo apt install pipx"`
		2. `pipx ensurepath` - to put the `bin` directories in the PATH
	5. **poetry**
		1. `script --append poetry.pipx.install.txt --command "pipx install poetry"`
	6. **Neovim**, **NOTE:** at the time of this writing, neovim is an old version, need to install from scratch
		1. Reference: https://forums.raspberrypi.com/viewtopic.php?t=367119
		2. See `~/installs/neovim.build_from_scratch.txt` -- ALAS this didn't work
		3. Of note, the make commands
				1. `sudo apt install ninja-build gettext cmake unzip curl` - ideally in a typescript file
				2. `mkdir ~/installs/from_scratch ; cd ~/installs/from_scratch`
				3. `git clone https://github.com/neovim/neovim` 
				4. `cd neovim`
				5. `git checkout stable`
				6. `make CMAKE_EXTRA_FLAGS=-DCMAKE_INSTALL_PREFIX=/opt/neovim`
				7. `make install`
		5. Copy files from my gainsight work box, it seems to be the most complete
			1. `scp -r dano@gainsbox.lan:.config/nvim ~/.config/nvim`
		6. Test first run (before adding to path)
			1. `/opt/neovim/bin/nvim`
			2. It is installing everything
			3. It cannot install `json5`
				1. Ah, it looks like a rust problem
					1. Rust is cool, I'm not sure I want to mess with it on my system :thinking:
					2. There must be an alternative?
					3. I'm going to comment it all out for the moment
					4. It seems to have taken it
			4. pyright
				1. `pyright: failed to install`
				2. Let's go looking for it, perhaps a raspberry pi thing?
				3. Apparently in needs `nodejs`, so install that (putting this in a previous step)
				4. Back from installing `npm` to get `nodejs`, will update again...
				5. Hmm, "nodejs is too old, update to 20.x or newer"... apparently the package manager doesn't have it, I'll bet it's more copilot that an actual necessity for my needs
				6. Oh, and look at that: `pyright successfully installed`
		7. Add it to THE SYSTEM PATH
			1. `sudo nvim /etc/profile`
			2. Add `/opt/neovim/bin` to the PATHS in there
			3. Logout, login, it works!
6. **Reboot**
7. **Get basic sound working**
	1. I'm attaching one of the USB sound adapters I got for illuminatrix and the cheap desktop speakers too
	2.  Downloaded `curl -O 'https://www.kozco.com/tech/LRMonoPhase4.wav'`
	3. `aplay LRMonoPhase4.wav`
	4. It works!Get basic Jack sound working
8. 

OK, that should be the basics, not to do more interesting things