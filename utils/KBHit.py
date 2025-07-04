#!/usr/bin/env python
'''
From:
https://stackoverflow.com/a/22085679/3077006

A Python class implementing KBHIT, the standard keyboard-interrupt poller.
Works transparently on Windows and Posix (Linux, Mac OS X).  Doesn't work
with IDLE.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as 
published by the Free Software Foundation, either version 3 of the 
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

'''

import os
from typing import Self

# Windows
if os.name == 'nt':
    import msvcrt

# Posix (Linux, OS X)
else:
    import atexit
    import sys
    import termios
    from select import select


class KBHit:

    def __init__(self):
        '''Creates a KBHit object that you can call to do various keyboard things.
        '''
        pass

    def __enter__(self) -> Self:
        return self.startup()

    def startup(self) -> Self:
        if os.name == 'nt':
            pass

        else:

            # Save the terminal settings
            self.fd = sys.stdin.fileno()
            self.new_term = termios.tcgetattr(self.fd)
            self.old_term = termios.tcgetattr(self.fd)

            # New terminal setting unbuffered
            self.new_term[3] = (self.new_term[3] & ~termios.ICANON & ~termios.ECHO)
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new_term)

            # Support normal-terminal reset at exit
            atexit.register(self.set_normal_term)

        return self


    def __exit__(self, type, value, traceback) -> None:
        self.shutdown()

    def shutdown(self) -> None:
        print('All done, resetting the term')
        self.set_normal_term()

    def set_normal_term(self) -> None:
        ''' Resets to normal terminal.  On Windows this is a no-op.
        '''

        if os.name == 'nt':
            pass

        else:
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old_term)


    def getch(self) -> str:
        ''' Returns a keyboard character after kbhit() has been called.
            Should not be called in the same program as getarrow().
        '''

        if os.name == 'nt':
            return msvcrt.getch().decode('utf-8')

        else:
            return sys.stdin.read(1)


    def getarrow(self):
        ''' Returns an arrow-key code after kbhit() has been called. Codes are
        0 : up
        1 : right
        2 : down
        3 : left
        Should not be called in the same program as getch().
        '''

        if os.name == 'nt':
            msvcrt.getch() # skip 0xE0
            c = msvcrt.getch()
            vals = [72, 77, 80, 75]

        else:
            c = sys.stdin.read(3)[2]
            vals = [65, 67, 66, 68]

        return vals.index(ord(c.encode('utf-8')))


    def kbhit(self, timeout:float = 0) -> bool:
        ''' Returns True if keyboard character was hit, False otherwise.
        '''
        if os.name == 'nt':
            return msvcrt.kbhit()

        else:
            dr,dw,de = select([sys.stdin], [], [], timeout)
            # print(dr, dw, de)
            return dr != []


# Test    
if __name__ == "__main__":

    with KBHit() as kb:
        try:
            print('Hit any key, or ESC to exit')

            i = 0

            while True:
                i += 1
                if kb.kbhit():
                    c = kb.getch()
                    if ord(c) == 27: # ESC
                        break
                    print(type(c), c, i)
                # print("iter", i)
                # time.sleep(5)
        except KeyboardInterrupt:
            # Ignore the keyboard interrupt
            pass
