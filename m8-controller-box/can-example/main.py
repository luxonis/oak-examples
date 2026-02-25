import time
import can
from utils.rp2040_u2if import RP2040_u2if

# button
BUTTON_PIN = 19

rp2040 = RP2040_u2if()
rp2040.open()

# Button uses pull-up; typical behavior: released=1, pressed=0
rp2040.gpio_init_pin(BUTTON_PIN, RP2040_u2if.GPIO_IN, RP2040_u2if.GPIO_PULL_UP)

# --- CAN (python-can with SocketCAN) ---
CAN_IFACE = "can0"
CAN_ID = 0x123
CAN_DATA = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]

bus = can.interface.Bus(channel=CAN_IFACE, interface="socketcan")


def send_can_frame():
    msg = can.Message(
        arbitration_id=CAN_ID,
        data=CAN_DATA,
        is_extended_id=False,
    )
    bus.send(msg)
    print(f"Sent CAN: {CAN_IFACE} id=0x{CAN_ID:X} data={CAN_DATA}")


# --- Button edge detection (send once per press) ---
last_button_state = rp2040.gpio_get_pin(BUTTON_PIN)

# Debounce
last_press_time = 0.0
debounce_s = 0.05

while True:
    button_state = rp2040.gpio_get_pin(BUTTON_PIN)

    # With pull-up: a press is usually 1->0 (falling edge)
    now = time.monotonic()
    pressed_edge = (last_button_state != 0) and (button_state == 0)

    if pressed_edge and (now - last_press_time) > debounce_s:
        try:
            send_can_frame()
        except Exception as e:
            print(f"[ERROR] Failed to send CAN frame: {e}")
        last_press_time = now

    last_button_state = button_state
    time.sleep(0.001)
