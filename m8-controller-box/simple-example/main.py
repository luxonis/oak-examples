import time
from utils.rp2040_u2if import RP2040_u2if

rp2040 = RP2040_u2if()
rp2040.open()

# leds
rp2040.gpio_init_pin(18, RP2040_u2if.GPIO_OUT, RP2040_u2if.GPIO_PULL_NONE)
rp2040.gpio_init_pin(17, RP2040_u2if.GPIO_OUT, RP2040_u2if.GPIO_PULL_NONE)

# button
rp2040.gpio_init_pin(19, RP2040_u2if.GPIO_IN, RP2040_u2if.GPIO_PULL_UP)

blink_interval = 0.5
last_blink_time = time.monotonic()
led_state = 0

while True:
    current_time = time.monotonic()

    # Non-blocking blink
    if current_time - last_blink_time >= blink_interval:
        led_state = 1 - led_state
        rp2040.gpio_set_pin(18, led_state)
        last_blink_time = current_time

    # Button check runs continuously
    button_state = rp2040.gpio_get_pin(19)

    if button_state != 0:
        rp2040.gpio_set_pin(17, 1)
    else:
        rp2040.gpio_set_pin(17, 0)
