#include <SoftPWM.h>   // Palatis/arduino-softpwm  (NOT bhagman/SoftPWM)

#define NUM_TOWERS  7
#define NUM_CONTROL 3

#define FRAME_SIZE       (NUM_TOWERS * 3 + NUM_CONTROL)   // 24 data bytes
#define FRAME_START_BYTE 0xAA

// Response is framed like the request: start byte, payload, CRC8
#define RESPONSE_SIZE 4   // start + tower switches + control switches + CRC

// If the sender stalls mid-frame, give up waiting for the rest after this
// long and rescan for a start byte instead of wedging in the wait loop
#define FRAME_WAIT_TIMEOUT_MS 50

/* ---------------- SoftPWM channel map -----------------------------------
   Palatis addresses outputs by PORT/BIT (compile-time) and by channel
   INDEX (0..23). The index order below is identical to the serial frame
   order, so the parser can call SoftPWM.set(index, value) directly.

   Mega 2560 pin -> port/bit is fixed silicon; change the pin in a comment
   only after changing the DDR/PORT/BIT to match.

     idx   tower/ch    Arduino pin   port.bit                          */
SOFTPWM_DEFINE_CHANNEL( 0, DDRE, PORTE, PORTE4);  // T1 R   pin 2
SOFTPWM_DEFINE_CHANNEL( 1, DDRE, PORTE, PORTE5);  // T1 G   pin 3
SOFTPWM_DEFINE_CHANNEL( 2, DDRG, PORTG, PORTG5);  // T1 B   pin 4
SOFTPWM_DEFINE_CHANNEL( 3, DDRE, PORTE, PORTE3);  // T2 R   pin 5
SOFTPWM_DEFINE_CHANNEL( 4, DDRH, PORTH, PORTH3);  // T2 G   pin 6
SOFTPWM_DEFINE_CHANNEL( 5, DDRH, PORTH, PORTH4);  // T2 B   pin 7
SOFTPWM_DEFINE_CHANNEL( 6, DDRH, PORTH, PORTH5);  // T3 R   pin 8
SOFTPWM_DEFINE_CHANNEL( 7, DDRH, PORTH, PORTH6);  // T3 G   pin 9
SOFTPWM_DEFINE_CHANNEL( 8, DDRB, PORTB, PORTB4);  // T3 B   pin 10
SOFTPWM_DEFINE_CHANNEL( 9, DDRB, PORTB, PORTB5);  // T4 R   pin 11
SOFTPWM_DEFINE_CHANNEL(10, DDRB, PORTB, PORTB6);  // T4 G   pin 12
SOFTPWM_DEFINE_CHANNEL(11, DDRB, PORTB, PORTB7);  // T4 B   pin 13
SOFTPWM_DEFINE_CHANNEL(12, DDRJ, PORTJ, PORTJ1);  // T5 R   pin 14
SOFTPWM_DEFINE_CHANNEL(13, DDRJ, PORTJ, PORTJ0);  // T5 G   pin 15
SOFTPWM_DEFINE_CHANNEL(14, DDRH, PORTH, PORTH1);  // T5 B   pin 16
SOFTPWM_DEFINE_CHANNEL(15, DDRH, PORTH, PORTH0);  // T6 R   pin 17
SOFTPWM_DEFINE_CHANNEL(16, DDRD, PORTD, PORTD3);  // T6 G   pin 18
SOFTPWM_DEFINE_CHANNEL(17, DDRD, PORTD, PORTD2);  // T6 B   pin 19
SOFTPWM_DEFINE_CHANNEL(18, DDRD, PORTD, PORTD1);  // T7 R   pin 20
SOFTPWM_DEFINE_CHANNEL(19, DDRD, PORTD, PORTD0);  // T7 G   pin 21
SOFTPWM_DEFINE_CHANNEL(20, DDRA, PORTA, PORTA0);  // T7 B   pin 22  <-- the once-cursed channel
SOFTPWM_DEFINE_CHANNEL(21, DDRC, PORTC, PORTC7);  // Ctrl 1 pin 30
SOFTPWM_DEFINE_CHANNEL(22, DDRC, PORTC, PORTC6);  // Ctrl 2 pin 31
SOFTPWM_DEFINE_CHANNEL(23, DDRC, PORTC, PORTC5);  // Ctrl 3 pin 32

/* 24 channels, 256 PWM levels (0..255) so your correction[] maps 1:1.
   If the ISR load is too high, switch to:
     SOFTPWM_DEFINE_OBJECT_WITH_PWM_LEVELS(24, 100);
   and scale correction[] outputs to 0..99.                              */
SOFTPWM_DEFINE_OBJECT(24);

using namespace Palatis;   // lets us write SoftPWM.set(...) / SoftPWM.begin(...)

// Switches still use ordinary Arduino pin numbers (digitalRead)
const uint8_t towerSwitchPins[NUM_TOWERS]    = {23, 24, 25, 26, 27, 28, 29};
const uint8_t controlSwitchPins[NUM_CONTROL] = {33, 34, 35};

uint8_t inputBuffer[FRAME_SIZE];

#ifdef USE_GAMMA
/*
* Practically speaking, I'm barely using the mega's memory so I'll
* just have a lookup table that either maps straight or with gamma
* correction.
*
* Gamma Commentary (todo: put this elsewhere) 2025-07-10
* 8 bit- gamma smooths out mids and tops but lows look really choppy.
* 16 bit- would be nice but is more hardware intensive.
* Most of my stuff is dark environments, would be nice to get 255 levels
* with a dimmer ceiling, e.g. an a standard 256, make 64 the top and have
* 255 levels from 0 to the new ceiling. Maybe do some research someday.
*/
const uint8_t correction[] = {
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1,
  1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2,
  2, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 5, 5, 5,
  5, 6, 6, 6, 6, 7, 7, 7, 7, 8, 8, 8, 9, 9, 9, 10,
  10, 10, 11, 11, 11, 12, 12, 13, 13, 13, 14, 14, 15, 15, 16, 16,
  17, 17, 18, 18, 19, 19, 20, 20, 21, 21, 22, 22, 23, 24, 24, 25,
  25, 26, 27, 27, 28, 29, 29, 30, 31, 32, 32, 33, 34, 35, 35, 36,
  37, 38, 39, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 50,
  51, 52, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 66, 67, 68,
  69, 70, 72, 73, 74, 75, 77, 78, 79, 81, 82, 83, 85, 86, 87, 89,
  90, 92, 93, 95, 96, 98, 99,101,102,104,105,107,109,110,112,114,
  115,117,119,120,122,124,126,127,129,131,133,135,137,138,140,142,
  144,146,148,150,152,154,156,158,160,162,164,167,169,171,173,175,
  177,180,182,184,186,189,191,193,196,198,200,203,205,208,210,213,
  215,218,220,223,225,228,231,233,236,239,241,244,247,249,252,255,
};

#else

const uint8_t correction[] = {
  0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
  16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
  32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47,
  48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63,
  64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79,
  80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95,
  96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111,
  112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127,
  128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143,
  144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159,
  160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175,
  176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191,
  192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207,
  208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223,
  224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239,
  240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255,
};
#endif
// ---- keep your existing correction[] table(s) exactly as-is -------------
// -------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);

  // 120 Hz: flicker-free for eyes and phone cameras, and measured serial
  // round-trip stays ~4ms median / <11ms max (180 Hz doubled it).
  // begin() sets every channel's DDR to OUTPUT for you.
  SoftPWM.begin(120);

  // Bench diagnostic ONLY. It prints text on Serial — never enable this
  // while the Pi is connected, it will corrupt your binary protocol:
  // SoftPWM.printInterruptLoad();

  for (int i = 0; i < NUM_TOWERS;  i++) pinMode(towerSwitchPins[i],   INPUT_PULLUP);
  for (int i = 0; i < NUM_CONTROL; i++) pinMode(controlSwitchPins[i], INPUT_PULLUP);
}

uint8_t computeCRC8(const uint8_t *data, uint8_t len) {
  uint8_t crc = 0x00;
  while (len--) {
    uint8_t inbyte = *data++;
    for (uint8_t i = 0; i < 8; i++) {
      uint8_t mix = (crc ^ inbyte) & 0x01;
      crc >>= 1;
      if (mix) crc ^= 0x8C;
      inbyte >>= 1;
    }
  }
  return crc;
}

void loop() {
  while (Serial.available()) {
    if (Serial.read() == FRAME_START_BYTE) {
      // Bounded wait for the rest of the frame (24 data + 1 CRC). If the
      // sender stalls mid-frame (Pi killed between write chunks, USB
      // hiccup), bail and rescan instead of wedging here forever.
      unsigned long waitStart = millis();
      while (Serial.available() < FRAME_SIZE + 1) {
        if (millis() - waitStart > FRAME_WAIT_TIMEOUT_MS) return;
      }

      Serial.readBytes(inputBuffer, FRAME_SIZE);
      uint8_t receivedCRC = Serial.read();

      if (computeCRC8(inputBuffer, FRAME_SIZE) != receivedCRC) return;  // discard

      // Channel index == frame index, so we can drive set() straight through.
      int index = 0;

      // Towers: channels 0..20, gamma/level corrected
      for (int i = 0; i < NUM_TOWERS * 3; i++) {
        SoftPWM.set(index, correction[inputBuffer[index]]);
        index++;
      }
      // Control LEDs: channels 21..23, raw intensity (matches your original)
      for (int i = 0; i < NUM_CONTROL; i++) {
        SoftPWM.set(index, inputBuffer[index]);
        index++;
      }

      // ---- switch readback, framed like the request ----
      uint8_t response[RESPONSE_SIZE];
      response[0] = FRAME_START_BYTE;
      response[1] = 0;   // tower switches
      response[2] = 0;   // control switches
      for (int i = 0; i < NUM_TOWERS; i++)
        if (digitalRead(towerSwitchPins[i]) == LOW)  response[1] |= (1 << i);
      for (int i = 0; i < NUM_CONTROL; i++)
        if (digitalRead(controlSwitchPins[i]) == LOW) response[2] |= (1 << i);
      response[3] = computeCRC8(&response[1], 2);

      Serial.write(response, RESPONSE_SIZE);
    }
  }
}
