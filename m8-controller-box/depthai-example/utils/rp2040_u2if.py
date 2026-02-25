# SPDX-FileCopyrightText: 2021 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""Helper class for use with RP2040 running u2if firmware"""
# https://github.com/execuc/u2if

import os
import time
import hid

# Use to set delay between reset and device reopen. if negative, don't reset at all
RP2040_U2IF_RESET_DELAY = float(os.environ.get("RP2040_U2IF_RESET_DELAY", 1))

# pylint: disable=import-outside-toplevel,too-many-branches,too-many-statements
# pylint: disable=too-many-arguments,too-many-function-args, too-many-public-methods


class RP2040_u2if:
    """Helper class for use with RP2040 running u2if firmware"""

    # MISC
    RESP_OK = 0x01
    SYS_RESET = 0x10

    # GPIO
    GPIO_INIT_PIN = 0x20
    GPIO_SET_VALUE = 0x21
    GPIO_GET_VALUE = 0x22
    # Values
    GPIO_IN = 0
    GPIO_OUT = 1
    GPIO_LOW = 0
    GPIO_HIGH = 1
    GPIO_PULL_NONE = 0
    GPIO_PULL_UP = 1
    GPIO_PULL_DOWN = 2

    # ADC
    ADC_INIT_PIN = 0x40
    ADC_GET_VALUE = 0x41

    # I2C
    I2C0_INIT = 0x80
    I2C0_DEINIT = 0x81
    I2C0_WRITE = 0x82
    I2C0_READ = 0x83
    I2C0_WRITE_FROM_UART = 0x84
    I2C1_INIT = I2C0_INIT + 0x10
    I2C1_DEINIT = I2C0_DEINIT + 0x10
    I2C1_WRITE = I2C0_WRITE + 0x10
    I2C1_READ = I2C0_READ + 0x10
    I2C1_WRITE_FROM_UART = I2C0_WRITE_FROM_UART + 0x10

    # SPI
    SPI0_INIT = 0x60
    SPI0_DEINIT = 0x61
    SPI0_WRITE = 0x62
    SPI0_READ = 0x63
    SPI0_WRITE_FROM_UART = 0x64
    SPI1_INIT = SPI0_INIT + 0x10
    SPI1_DEINIT = SPI0_DEINIT + 0x10
    SPI1_WRITE = SPI0_WRITE + 0x10
    SPI1_READ = SPI0_READ + 0x10
    SPI1_WRITE_FROM_UART = SPI0_WRITE_FROM_UART + 0x10

    # WS2812B (LED)
    WS2812B_INIT = 0xA0
    WS2812B_DEINIT = 0xA1
    WS2812B_WRITE = 0xA2

    # PWM
    PWM_INIT_PIN = 0x30
    PWM_DEINIT_PIN = 0x31
    PWM_SET_FREQ = 0x32
    PWM_GET_FREQ = 0x33
    PWM_SET_DUTY_U16 = 0x34
    PWM_GET_DUTY_U16 = 0x35
    PWM_SET_DUTY_NS = 0x36
    PWM_GET_DUTY_NS = 0x37

    def __init__(self):
        self._vid = None
        self._pid = None
        self._hid = None
        self._opened = False
        self._i2c_index = None
        self._spi_index = None
        self._serial = None
        self._neopixel_initialized = False
        self._uart_rx_buffer = None

    def _hid_xfer(self, report, response=True):
        """Perform HID Transfer"""
        # first byte is report ID, which =0
        # remaing bytes = 64 byte report data
        # https://github.com/libusb/hidapi/blob/083223e77952e1ef57e6b77796536a3359c1b2a3/hidapi/hidapi.h#L185
        self._hid.write(b"\0" + report + b"\0" * (64 - len(report)))
        if response:
            # return is 64 byte response report
            ret = self._hid.read(64, timeout_ms=1000) # Sometimes this can hang, but if we time out the call, it will work on the next call
            assert len(ret) == 64, "HID Timeout occurred."
            return ret
        return None

    def _reset(self):
        self._hid_xfer(bytes([self.SYS_RESET]), False)
        self._hid.close()
        time.sleep(RP2040_U2IF_RESET_DELAY)
        start = time.monotonic()
        while time.monotonic() - start < 5:
            try:
                self._hid.open(self._vid, self._pid, self._serial)
            except OSError:
                time.sleep(0.1)
                continue
            return
        raise OSError("RP2040 u2if open error.")

    # ----------------------------------------------------------------
    # MISC
    # ----------------------------------------------------------------
    def open(self, vid = 0xcafe, pid = 0x4005, serial = None):
        """Open HID interface for given USB VID and PID."""

        if self._opened:
            return
        self._vid = vid
        self._pid = pid
        self._serial = serial
        self._hid = hid.device()
        self._hid.open(self._vid, self._pid, self._serial)
        if RP2040_U2IF_RESET_DELAY >= 0:
            self._reset()
        self._opened = True

    def close(self):
        """Close HID interface."""
        if not self._opened:
            return
        self._hid_xfer(bytes([self.SYS_RESET]), True)
        self._hid.close()
        self._opened = False

    # ----------------------------------------------------------------
    # GPIO
    # ----------------------------------------------------------------
    def gpio_init_pin(self, pin_id, direction, pull):
        """Configure GPIO Pin."""
        self._hid_xfer(
            bytes(
                [
                    self.GPIO_INIT_PIN,
                    pin_id,
                    direction,
                    pull,
                ]
            )
        )

    def gpio_set_pin(self, pin_id, value):
        """Set Current GPIO Pin Value"""
        self._hid_xfer(
            bytes(
                [
                    self.GPIO_SET_VALUE,
                    pin_id,
                    int(value),
                ]
            )
        )

    def gpio_get_pin(self, pin_id):
        """Get Current GPIO Pin Value"""
        resp = self._hid_xfer(
            bytes(
                [
                    self.GPIO_GET_VALUE,
                    pin_id,
                ]
            ),
            True,
        )
        return resp[3] != 0x00

    # ----------------------------------------------------------------
    # ADC
    # ----------------------------------------------------------------
    def adc_init_pin(self, pin_id):
        """Configure ADC Pin."""
        self._hid_xfer(
            bytes(
                [
                    self.ADC_INIT_PIN,
                    pin_id,
                ]
            )
        )

    def adc_get_value(self, pin_id):
        """Get ADC value for pin."""
        resp = self._hid_xfer(
            bytes(
                [
                    self.ADC_GET_VALUE,
                    pin_id,
                ]
            ),
            True,
        )
        return int.from_bytes(resp[3 : 3 + 2], byteorder="little")

    # ----------------------------------------------------------------
    # I2C
    # ----------------------------------------------------------------
    def i2c_configure(self, baudrate, pullup=False):
        """Configure I2C."""
        if self._i2c_index is None:
            raise RuntimeError("I2C bus not initialized.")

        resp = self._hid_xfer(
            bytes(
                [
                    self.I2C0_INIT if self._i2c_index == 0 else self.I2C1_INIT,
                    0x00 if not pullup else 0x01,
                ]
            )
            + baudrate.to_bytes(4, byteorder="little"),
            True,
        )
        if resp[1] != self.RESP_OK:
            raise RuntimeError("I2C init error.")

    def i2c_set_port(self, index):
        """Set I2C port."""
        if index not in (0, 1):
            raise ValueError("I2C index must be 0 or 1.")
        self._i2c_index = index

    def _i2c_write(self, address, buffer, start=0, end=None, stop=True):
        """Write data from the buffer to an address"""
        if self._i2c_index is None:
            raise RuntimeError("I2C bus not initialized.")

        end = end if end else len(buffer)

        write_cmd = self.I2C0_WRITE if self._i2c_index == 0 else self.I2C1_WRITE
        stop_flag = 0x01 if stop else 0x00

        while (end - start) > 0:
            remain_bytes = end - start
            chunk = min(remain_bytes, 64 - 7)
            resp = self._hid_xfer(
                bytes([write_cmd, address, stop_flag])
                + remain_bytes.to_bytes(4, byteorder="little")
                + buffer[start : (start + chunk)],
                True,
            )
            if resp[1] != self.RESP_OK:
                raise RuntimeError("I2C write error")
            start += chunk

    def _i2c_read(self, address, buffer, start=0, end=None):
        """Read data from an address and into the buffer"""
        # TODO: support chunkified reads
        if self._i2c_index is None:
            raise RuntimeError("I2C bus not initialized.")

        end = end if end else len(buffer)

        read_cmd = self.I2C0_READ if self._i2c_index == 0 else self.I2C1_READ
        stop_flag = 0x01  # always stop
        read_size = end - start

        resp = self._hid_xfer(bytes([read_cmd, address, stop_flag, read_size]), True)
        if resp[1] != self.RESP_OK:
            raise RuntimeError("I2C write error")
        # move into buffer
        for i in range(read_size):
            buffer[start + i] = resp[i + 2]

    def i2c_writeto(self, address, buffer, *, start=0, end=None):
        """Write data from the buffer to an address"""
        self._i2c_write(address, buffer, start, end)

    def i2c_readfrom_into(self, address, buffer, *, start=0, end=None):
        """Read data from an address and into the buffer"""
        self._i2c_read(address, buffer, start, end)

    def i2c_writeto_then_readfrom(
        self,
        address,
        out_buffer,
        in_buffer,
        *,
        out_start=0,
        out_end=None,
        in_start=0,
        in_end=None,
    ):
        """Write data from buffer_out to an address and then
        read data from an address and into buffer_in
        """
        self._i2c_write(address, out_buffer, out_start, out_end, False)
        self._i2c_read(address, in_buffer, in_start, in_end)

    def i2c_scan(self, *, start=0, end=0x79):
        """Perform an I2C Device Scan"""
        if self._i2c_index is None:
            raise RuntimeError("I2C bus not initialized.")
        found = []
        for addr in range(start, end + 1):
            # try a write
            try:
                self.i2c_writeto(addr, b"\x00\x00\x00")
            except RuntimeError:  # no reply!
                continue
            # store if success
            found.append(addr)
        return found

    # ----------------------------------------------------------------
    # SPI
    # ----------------------------------------------------------------
    def spi_configure(self, baudrate):
        """Configure SPI."""
        if self._spi_index is None:
            raise RuntimeError("SPI bus not initialized.")

        resp = self._hid_xfer(
            bytes(
                [
                    self.SPI0_INIT if self._spi_index == 0 else self.SPI1_INIT,
                    0x00,  # mode, not yet implemented
                ]
            )
            + baudrate.to_bytes(4, byteorder="little"),
            True,
        )
        if resp[1] != self.RESP_OK:
            raise RuntimeError("SPI init error.")

    def spi_set_port(self, index):
        """Set SPI port."""
        if index not in (0, 1):
            raise ValueError("SPI index must be 0 or 1.")
        self._spi_index = index

    def spi_write(self, buffer, *, start=0, end=None):
        """SPI write."""
        if self._spi_index is None:
            raise RuntimeError("SPI bus not initialized.")

        end = end if end else len(buffer)

        write_cmd = self.SPI0_WRITE if self._spi_index == 0 else self.SPI1_WRITE

        while (end - start) > 0:
            remain_bytes = end - start
            chunk = min(remain_bytes, 64 - 3)
            resp = self._hid_xfer(
                bytes([write_cmd, chunk]) + buffer[start : (start + chunk)], True
            )
            if resp[1] != self.RESP_OK:
                raise RuntimeError("SPI write error")
            start += chunk

    def spi_readinto(self, buffer, *, start=0, end=None, write_value=0):
        """SPI readinto."""
        if self._spi_index is None:
            raise RuntimeError("SPI bus not initialized.")

        end = end if end else len(buffer)
        read_cmd = self.SPI0_READ if self._spi_index == 0 else self.SPI1_READ
        read_size = end - start

        resp = self._hid_xfer(bytes([read_cmd, write_value, read_size]), True)
        if resp[1] != self.RESP_OK:
            raise RuntimeError("SPI write error")
        # move into buffer
        for i in range(read_size):
            buffer[start + i] = resp[i + 2]

    def spi_write_readinto(
        self,
        buffer_out,
        buffer_in,
        *,
        out_start=0,
        out_end=None,
        in_start=0,
        in_end=None,
    ):
        """SPI write and readinto."""
        raise NotImplementedError("SPI write_readinto Not implemented")

    # ----------------------------------------------------------------
    # NEOPIXEL
    # ----------------------------------------------------------------
    def neopixel_write(self, gpio, buf):
        """NeoPixel write."""
        # open serial (data is sent over this)
        if self._serial is None:
            import serial
            import serial.tools.list_ports

            ports = serial.tools.list_ports.comports()
            for port in ports:
                if port.vid == self._vid and port.pid == self._pid:
                    self._serial = serial.Serial(port.device)
                    break
        if self._serial is None:
            raise RuntimeError("Could not find Pico com port.")

        # init
        if not self._neopixel_initialized:
            # deinit any current setup
            # pylint: disable=protected-access
            self._hid_xfer(bytes([self.WS2812B_DEINIT]))
            resp = self._hid_xfer(
                bytes(
                    [
                        self.WS2812B_INIT,
                        gpio._pin.id,
                    ]
                ),
                True,
            )
            if resp[1] != self.RESP_OK:
                raise RuntimeError("Neopixel init error")
            self._neopixel_initialized = True

        self._serial.reset_output_buffer()

        # write
        # command is done over HID
        remain_bytes = len(buf)
        resp = self._hid_xfer(
            bytes([self.WS2812B_WRITE]) + remain_bytes.to_bytes(4, byteorder="little"),
            True,
        )
        if resp[1] != self.RESP_OK:
            # pylint: disable=no-else-raise
            if resp[2] == 0x01:
                raise RuntimeError(
                    "Neopixel write error : too many pixel for the firmware."
                )
            elif resp[2] == 0x02:
                raise RuntimeError(
                    "Neopixel write error : transfer already in progress."
                )
            else:
                raise RuntimeError("Neopixel write error.")
        # buffer is sent over serial
        self._serial.write(buf)
        # hack (see u2if)
        if len(buf) % 64 == 0:
            self._serial.write([0])
        self._serial.flush()
        # polling loop to wait for write complete?
        time.sleep(0.1)
        resp = self._hid.read(64)
        while resp[0] != self.WS2812B_WRITE:
            resp = self._hid.read(64)
        if resp[1] != self.RESP_OK:
            raise RuntimeError("Neopixel write (flush) error.")

    # ----------------------------------------------------------------
    # PWM
    # ----------------------------------------------------------------
    # pylint: disable=unused-argument
    def pwm_configure(self, pin_id: int, frequency=500, duty_cycle=0, variable_frequency=False):
        """Configure PWM."""
        self.pwm_deinit(pin_id)
        resp = self._hid_xfer(bytes([self.PWM_INIT_PIN, pin_id]), True)
        if resp[1] != self.RESP_OK:
            raise RuntimeError("PWM init error.")

        self.pwm_set_frequency(pin_id, frequency)
        self.pwm_set_duty_cycle(pin_id, duty_cycle)

    def pwm_deinit(self, pin_id: int):
        """Deinit PWM."""
        self._hid_xfer(bytes([self.PWM_DEINIT_PIN, pin_id]))

    def pwm_get_frequency(self, pin_id: int):
        """PWM get freq."""
        resp = self._hid_xfer(bytes([self.PWM_GET_FREQ, pin_id]), True)
        if resp[1] != self.RESP_OK:
            raise RuntimeError("PWM get frequency error.")
        return int.from_bytes(resp[3 : 3 + 4], byteorder="little")

    def pwm_set_frequency(self, pin_id: int, frequency):
        """PWM set freq."""
        resp = self._hid_xfer(
            bytes([self.PWM_SET_FREQ, pin_id])
            + frequency.to_bytes(4, byteorder="little"),
            True,
        )
        if resp[1] != self.RESP_OK:
            # pylint: disable=no-else-raise
            if resp[3] == 0x01:
                raise RuntimeError("PWM different frequency on same slice.")
            elif resp[3] == 0x02:
                raise RuntimeError("PWM frequency too low.")
            elif resp[3] == 0x03:
                raise RuntimeError("PWM frequency too high.")
            else:
                raise RuntimeError("PWM frequency error.")

    def pwm_get_duty_cycle(self, pin_id: int):
        """PWM get duty cycle."""
        resp = self._hid_xfer(bytes([self.PWM_GET_DUTY_U16, pin_id]), True)
        if resp[1] != self.RESP_OK:
            raise RuntimeError("PWM get duty cycle error.")
        return int.from_bytes(resp[3 : 3 + 4], byteorder="little")

    def pwm_set_duty_cycle(self, pin_id: int, duty_cycle):
        """PWM set duty cycle."""
        resp = self._hid_xfer(
            bytes([self.PWM_SET_DUTY_U16, pin_id])
            + duty_cycle.to_bytes(2, byteorder="little"),
            True,
        )
        if resp[1] != self.RESP_OK:
            raise RuntimeError("PWM set duty cycle error.")

