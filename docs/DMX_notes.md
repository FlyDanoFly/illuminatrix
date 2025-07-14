# Notes for DMX Setup 2025-07-12
Because I *love* relearning things I did in crunch time last year


## My light docs (excerpt)
For the DMX lights that I have, the spec sheet says it listens for this data:
(Yes, for the explanations that go off the edge of the table, they are cut off in the source documentation)

| Channel | Numerical value | Function |
| ------- | --------------- | -------- |
| 1       | 0-255           | Total dimming |
| 2       | 0-255           | Red dimming |
| 3       | 0-255           | Green dimming |
| 4       | 0-255           | Blue dimming |
| 5       | 0-7             | No flash |
|         | 8-255           | The higher the value, the faster the stroboscopic |
| 6       | 0-10            | 1 to 5 channels are valid |
|         | 11-60           | There are 7 fixed colors, and the color is determined by the sevent |
|         | 61-110          | In gradient mode, the speed is set by channel 7. The larger the val |
|         | 111-160         | Pulse mode, set the speed from channel 7. The larger the value, the |
|         | 161-210         | Jump mode, set the speed from channel 7. The larger the value, the |
|         | 211-255         | Audio Mode |
| 7       | 0-255           | Channel 6 related mode speed setting |


## Address and offsets **important**
I had to relearn this again
In DMX there are "universes". AFAICT it boils down to this: each universe is a array of uint8 that is 255 elements long.
You set DMX things by pushing this big array to the universe.
With my DMX lights, the address you set on the device, e.g. `d01`, is the address it starts listening at

For example, with this data in `[255, 255, 255, 0, 0, 0, 0, ...]`
- One of my lights set to `d01` would turn yellow:
  - It starts listening in offset `0`
  - Intensity: `255`, Red: `255`, Green: `255`, Blue: `0`
- With another light set to `d02`, it would turn red
  - It starts listening in offset `1`
  - Intensity: `255`, Red: `255`, Green: `0`, Blue: `0`


## Intersection with Critical 2024 code
I set a "width" of 10 so that I could make each light start on a number divisible by `(n-1)/10`
And then towers were in pairs, e.g.
- Tower 1: `d01`, `d11`
- Tower 2: `d21`, `d31`
- etc

## About to integrate this learning with my code, notes here

