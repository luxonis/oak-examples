"""
Box Configuration Module
------------------------

Handles:
• Initialization of ControllerBox (single instance)
• Relay control (relay 1)
• FSYNC controller setup
• LED indication
"""

import time
from luxonis_u2if import ControllerBox


class BoxConfig:
    """
    Singleton-style ControllerBox manager
    Provides:
    • Relay control
    • FSYNC initialization
    """

    def __init__(self):
        # ----------------------------------------------------
        # Connect to ControllerBox (only once!)
        # ----------------------------------------------------
        self.box = ControllerBox()

        # ----------------------------------------------------
        # Initialize hardware
        # ----------------------------------------------------
        self.box.relay_init()
        self.box.led_init()

        # Relay configuration
        self.relay_id = 1

        # FSYNC output selection
        self.fsync_out = ControllerBox.FsyncOutput.ISOLATED_STROBE

    # --------------------------------------------------------
    # Relay control
    # --------------------------------------------------------
    def stop_conveyor(self):
        """
        Activate relay → stop conveyor
        """
        self.box.led_on(0)
        self.box.relay_reset(self.relay_id)

    def start_conveyor(self):
        """
        Deactivate relay → start conveyor
        """
        self.box.led_off(0)
        self.box.relay_set(self.relay_id)

    # --------------------------------------------------------
    # FSYNC control
    # --------------------------------------------------------
    def init_fsync(self, mode=ControllerBox.FsyncMode.SLAVE, frequency=0.1, polarity=True, duty_cycle=50.0):
        """
        Initialize FSYNC controller.
        Defaults to SLAVE mode with low frequency.
        """
        self.box.fsync_controller_init()
        self.box.fsync_controller_set_mode(mode)
        self.box.fsync_controller_set_frequency(frequency)
        self.box.fsync_controller_set_polarity(polarity, self.fsync_out)
        self.box.fsync_controller_set_duty_cycle(duty_cycle, self.fsync_out)