"""
Controller Box Simple Example – Button Beep & LED
-------------------------------------------------

This simple example demonstrates core functionality of the M8 Controller Box with a USB audio hub:

1. **LED Blinking**: LED 1 blinks continuously to indicate the program is running.
2. **Button Handling via GPIO IRQ**: Button connected to GPIO pin 20 triggers events without polling.
3. **Continuous Beep on Button Hold**: While the button is pressed, a 1 kHz tone plays continuously through the USB audio speaker.
4. **LED During Button Press**: LED 2 (or same LED if desired) lights only while the button is pressed.
5. **Minimal Dependencies**: Works in a minimal Linux container using only Python and `aplay`. No additional packages required.

This example is ideal for understanding basic GPIO interaction, interrupt-driven button handling, and simple audio output.
"""

import time
import os
from luxonis_u2if import ControllerBox

# ------------------------------------------------------------
# Connect to the ControllerBox
# ------------------------------------------------------------
box = ControllerBox()
box.led_init()  # Initialize all LEDs

# ------------------------------------------------------------
# Button setup (IRQ)
# ------------------------------------------------------------
BUTTON_PIN = 20  # GPIO pin where the button is connected
box.gpio_init(BUTTON_PIN, box.GPIO_IN, box.GPIO_PULL_UP)

# Enable interrupts for rising and falling edges with debounce
box.gpio_set_irq(
    BUTTON_PIN,
    box.IRQ_RISING | box.IRQ_FALLING,
    debounce=True
)

# ------------------------------------------------------------
# Audio setup
# ------------------------------------------------------------
CARD = 1          # USB audio card number (from /proc/asound/cards)
DEVICE = 0        # Audio device on that card
FREQ = 1000       # Beep frequency in Hz
DURATION = 0.1    # Tone chunk duration in seconds
TONE_FILE = "/tmp/beep.wav"  # Temporary WAV file to use with aplay

def generate_wav():
    """Generate a short 1kHz sine wave WAV file if it doesn't exist."""
    import wave, struct, math
    framerate = 44100
    amplitude = 32767
    n_samples = int(framerate * DURATION)

    with wave.open(TONE_FILE, 'w') as wf:
        wf.setnchannels(1)        # Mono
        wf.setsampwidth(2)        # 16-bit
        wf.setframerate(framerate)
        for i in range(n_samples):
            value = int(amplitude * math.sin(2 * math.pi * FREQ * i / framerate))
            wf.writeframesraw(struct.pack('<h', value))

def play_tone():
    """Play the generated tone using aplay."""
    if not os.path.exists(TONE_FILE):
        generate_wav()
    os.system(f"aplay -D hw:{CARD},{DEVICE} {TONE_FILE} >/dev/null 2>&1")

# ------------------------------------------------------------
# Program ready message
# ------------------------------------------------------------
print("ControllerBox Simple Example ready.")
print("LED 1 blinks continuously.")
print("Press and hold the button to light the LED and play a beep.\n")

# ------------------------------------------------------------
# Main loop
# ------------------------------------------------------------
blink_interval = 0.5        # Time for LED 1 blink
last_blink = time.monotonic()
led_on = False
button_pressed = False      # Track if button is currently pressed

while True:
    now = time.monotonic()

    # ----------------------------
    # LED 1 blinking logic
    # ----------------------------
    if now - last_blink >= blink_interval:
        led_on = not led_on
        if led_on:
            box.led_on(1)
        else:
            box.led_off(1)
        last_blink = now

    # ----------------------------
    # Handle button IRQ events
    # ----------------------------
    for pin, event in box.gpio_get_irq():
        if pin != BUTTON_PIN:
            continue

        if event == box.IRQ_RISING:
            # Button pressed
            button_pressed = True
            box.led_on(2)       # Turn on LED 2 while pressed
            print("Button pressed → starting beep")

        elif event == box.IRQ_FALLING:
            # Button released
            button_pressed = False
            box.led_off(2)      # Turn off LED 2
            print("Button released → stopping beep")

    # ----------------------------
    # Continuous beep while button held
    # ----------------------------
    if button_pressed:
        play_tone()  # Play short tone repeatedly

    time.sleep(0.01)  # Small delay for loop efficiency
