# Illuminatrix

Controller and program code.
Trying out AI helping me along.

# TODO
- Get a basic gameloop and framework to communicate lighting and sound to towers, or as a whole system

# Jack
I'm trying to this python program running with Jack
I'm having a hard time
ChatGPT says I need to have jackd running 
It gives an error:
Could not open component .so '/usr/lib/jack/jack_firewire.so': libffado.so.2: cannot open shared object file: No such file or directory

There is also jackdbus which I think is supposed to be more modern?
There is also a thread that suggests installing `realtime-privileges`, but that's probably to make it easier to run a command as a user without elevated priviliegs, let's return to this

Jack2 was already installed
The only command available: jackd
I installed jack2-dbug
Commands now avaialble: jack_control jackd jackdbus
Running `jackdbus` says:
jackdbus should be auto-executed by D-Bus message bus daemon.
If you want to run it manually anyway, specify "auto" as only parameter

I'm not really understanding what's going on
Do I need to install the libffado library? Let's come back to that...
Maybe try `jack_control`?
It is a command command like git
```
~/.../ArchLinux$ jack_control status
--- status
stopped
~/.../ArchLinux$ jack_control start
--- start
~/.../ArchLinux$ ps -e | grep -i jack
  38786 ?        00:00:00 jackdbus
```
... OK? Back to trying to get the python to make a sound, any sound

Nope, going to try with ChatGPT again
It suggests adding qjackctl (graphical control interface) and realtime-priviligees
Hmm, should I set all this up on the pi and connect audio to it? Seems like I should do it in both places
OK, one sec while I it all working

# Point of order: Good notes!
I should do some real note taking so that I can get this working again if I lose everything
Maybe go full on Obsitian notes so I can have different sections
...start from scratch?
sigh 
might be best in the long term, I'm continually forgetting what I did last time and it take hours to get back there
And when I have notes I do it faster
OK....
sigh...
From the card wipe onwards :-/



OK UPDATE!
I got the basic setup with the RPi and lots of "proper" notes with Obsidian
I'm going to check everything in as a milestone
Future work will be on the RPi and backported to this box
Big deal to get working today is sound
(And all the other things)
I'm going to make a big commit, then connect my RPI up to my GitHub and pull down the repository

OK, instead of one big commit, I made a modest one that starts all the notes
I think I might start off with JUST getting jack working on the Raspberry Pi

