"""
Controller Box CAN Button IRQ Example
------------------------------------

Demonstrates how to send a CAN frame using
ControllerBox button events without polling.
Uses GPIO interrupts instead of continuous polling.
"""

import time
import can
from luxonis_u2if import ControllerBox


# ------------------------------------------------------------
# Connect to ControllerBox device
# ------------------------------------------------------------

box = ControllerBox()


# ------------------------------------------------------------
# CAN configuration
# ------------------------------------------------------------

CAN_IFACE = "can0"
CAN_ID = 0x123
CAN_DATA = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]

bus = can.interface.Bus(channel=CAN_IFACE, interface="socketcan")


def send_can_frame():
    """
    Send a predefined CAN frame.
    """
    msg = can.Message(
        arbitration_id=CAN_ID,
        data=CAN_DATA,
        is_extended_id=False,
    )
    bus.send(msg)
    print(f"Sent CAN: {CAN_IFACE} id=0x{CAN_ID:X} data={CAN_DATA}")


# ------------------------------------------------------------
# Button callback
# ------------------------------------------------------------

BUTTON_INDEX = 1  # Button 1
button_pin = ControllerBox.BUTTON_PINS[BUTTON_INDEX - 1]

def button_cb(btn, state):
    """
    Triggered on button press/release.

    Parameters
    ----------
    btn : int
        Button index (1..3)
    state : bool
        True = pressed, False = released
    """
    if btn == BUTTON_INDEX and state:  # pressed
        try:
            send_can_frame()
        except Exception as e:
            print(f"[ERROR] Failed to send CAN frame: {e}")


# ------------------------------------------------------------
# Register callback
# ------------------------------------------------------------

box.set_btn_callback(button_cb)


print("ControllerBox ready")
print("Press Button 1 to send CAN frame")


# ------------------------------------------------------------
# Main loop
# ------------------------------------------------------------

# Nothing required here — button events handled via IRQ
while True:
    time.sleep(1)