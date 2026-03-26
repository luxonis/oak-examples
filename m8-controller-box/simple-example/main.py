"""
Controller Box Simple Example
-----------------------------

This example demonstrates basic usage of the ControllerBox:

- LED 1 blinks continuously
- Button 2 controls LED 2

This showcases simple GPIO-style interaction using the high-level API.
"""

import time
from luxonis_u2if import ControllerBox


# ------------------------------------------------------------
# Connect to ControllerBox device
# ------------------------------------------------------------

box = ControllerBox()


# ------------------------------------------------------------
# Initialize LEDs
# ------------------------------------------------------------

box.led_init()


# ------------------------------------------------------------
# Initialize Button (polling)
# ------------------------------------------------------------

# Button 2 corresponds to index 2 (internally mapped)
BUTTON_INDEX = 2
LED_INDEX = 2


print("ControllerBox ready")
print("LED 1 blinking, Button 2 controls LED 2")


# ------------------------------------------------------------
# Main loop
# ------------------------------------------------------------

blink_interval = 0.5
last_blink_time = time.monotonic()
led_state = False

while True:
    current_time = time.monotonic()

    # Non-blocking LED 1 blink
    if current_time - last_blink_time >= blink_interval:
        led_state = not led_state
        box.led_set(1, led_state)
        last_blink_time = current_time

    # Poll Button 2 (via underlying GPIO mapping)
    button_state = box.gpio_get(ControllerBox.BUTTON_PINS[BUTTON_INDEX - 1])

    # Button pressed -> LED ON
    box.led_set(LED_INDEX, button_state)

    time.sleep(0.01)