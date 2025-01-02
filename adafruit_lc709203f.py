# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2020 ladyada for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`adafruit_lc709203f`
================================================================================

Library for I2C LC709203F battery status and fuel gauge


* Author(s): ladyada

Implementation Notes
--------------------

**Hardware:**

* `Adafruit LC709203F LiPoly / LiIon Fuel Gauge and Battery Monitor
  <https://www.adafruit.com/product/4712>`_ (Product ID: 4712)

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads

* Adafruit's Bus Device library:
  https://github.com/adafruit/Adafruit_CircuitPython_BusDevice

* Adafruit's Register library:
  https://github.com/adafruit/Adafruit_CircuitPython_Register

"""

import time

from micropython import const
from adafruit_bus_device import i2c_device

try:
    from typing import Iterable, Optional, Tuple
    from typing_extensions import Literal
    from circuitpython_typing import ReadableBuffer
    from busio import I2C
except ImportError:
    pass

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_LC709203F.git"

LC709203F_I2CADDR_DEFAULT = const(0x0B)
LC709203F_CMD_ICVERSION = const(0x11)
LC709203F_CMD_BATTPROF = const(0x12)
LC709203F_CMD_POWERMODE = const(0x15)
LC709203F_CMD_APA = const(0x0B)
LC709203F_CMD_INITRSOC = const(0x07)
LC709203F_CMD_CELLVOLTAGE = const(0x09)
LC709203F_CMD_CELLITE = const(0x0F)
LC709203F_CMD_CELLTEMPERATURE = const(0x08)
LC709203F_CMD_THERMISTORB = const(0x06)
LC709203F_CMD_STATUSBIT = const(0x16)
LC709203F_CMD_ALARMPERCENT = const(0x13)
LC709203F_CMD_ALARMVOLTAGE = const(0x14)

LC709203F_I2C_RETRY_COUNT = 10


class CV:
    """struct helper"""

    @classmethod
    def add_values(
        cls, value_tuples: Iterable[Tuple[str, int, str, Optional[float]]]
    ) -> None:
        """Add CV values to the class"""
        cls.string = {}
        cls.lsb = {}

        for value_tuple in value_tuples:
            name, value, string, lsb = value_tuple
            setattr(cls, name, value)
            cls.string[value] = string
            cls.lsb[value] = lsb

    @classmethod
    def is_valid(cls, value: int) -> bool:
        """Validate that a given value is a member"""
        return value in cls.string


class PowerMode(CV):
    """Options for ``power_mode``"""

    pass  # pylint: disable=unnecessary-pass


PowerMode.add_values(
    (
        ("OPERATE", 0x0001, "Operate", None),
        ("SLEEP", 0x0002, "Sleep", None),
    )
)


class PackSize(CV):
    """Options for ``pack_size``"""

    pass  # pylint: disable=unnecessary-pass


PackSize.add_values(
    (
        ("MAH100", 0x08, "100 mAh", 100),
        ("MAH200", 0x0B, "200 mAh", 200),
        ("MAH400", 0x0E, "400 mAh", 400),
        ("MAH500", 0x10, "500 mAh", 500),
        ("MAH1000", 0x19, "1000 mAh", 1000),
        ("MAH2000", 0x2D, "2000 mAh", 2000),
        ("MAH2200", 0x30, "2200 mAh", 2200),
        ("MAH3000", 0x36, "3000 mAh", 3000),
    )
)


class LC709203F:
    """Interface library for LC709203F battery monitoring and fuel gauge sensors

    :param ~busio.I2C i2c_bus: The I2C bus the device is connected to
    :param int address: The I2C device address. Defaults to :const:`0x0B`

    """

    def __init__(self, i2c_bus: I2C, address: int = LC709203F_I2CADDR_DEFAULT) -> None:
        value_exc = None
        for _ in range(3):
            try:
                self.i2c_device = i2c_device.I2CDevice(i2c_bus, address)
                break
            except ValueError as exc:
                value_exc = exc
                # Wait a bit for the sensor to wake up.
                time.sleep(0.1)
        else:
            raise value_exc

        self._buf = bytearray(10)
        self.power_mode = PowerMode.OPERATE  # pylint: disable=no-member
        self.pack_size = PackSize.MAH500  # pylint: disable=no-member
        self.battery_profile = 1  # 4.2V profile
        time.sleep(0.1)
        self.init_RSOC()
        time.sleep(0.1)

    def init_RSOC(self) -> None:  # pylint: disable=invalid-name
        """Initialize the state of charge calculator"""
        self._write_word(LC709203F_CMD_INITRSOC, 0xAA55)

    @property
    def cell_voltage(self) -> float:
        """Returns floating point voltage"""
        try:
            return self._read_word(LC709203F_CMD_CELLVOLTAGE) / 1000
        except OSError:
            return None

    @property
    def cell_percent(self) -> float:
        """Returns percentage of cell capacity"""
        try:
            return self._read_word(LC709203F_CMD_CELLITE) / 10
        except OSError:
            return None

    @property
    def cell_temperature(self) -> float:
        """Returns the temperature of the cell"""
        try:
            return self._read_word(LC709203F_CMD_CELLTEMPERATURE) / 10 - 273.15
        except OSError:
            return None

    @cell_temperature.setter
    def cell_temperature(self, value: float) -> None:
        """Sets the temperature in the LC709203F"""
        if self.thermistor_enable:
            raise ValueError("temperature can only be set in i2c mode")
        self._write_word(LC709203F_CMD_CELLTEMPERATURE, int(value + 273.15) * 10)

    @property
    def ic_version(self) -> int:
        """Returns read-only chip version"""
        return self._read_word(LC709203F_CMD_ICVERSION)

    @property
    def power_mode(self) -> Literal[1, 2]:
        """Returns current power mode (operating or sleeping)"""
        return self._read_word(LC709203F_CMD_POWERMODE)

    @power_mode.setter
    def power_mode(self, mode: Literal[1, 2]) -> None:
        if not PowerMode.is_valid(mode):
            raise ValueError("power_mode must be a PowerMode")
        self._write_word(LC709203F_CMD_POWERMODE, mode)

    @property
    def battery_profile(self) -> Literal[0, 1]:
        """Returns current battery profile (0 or 1)"""
        return self._read_word(LC709203F_CMD_BATTPROF)

    @battery_profile.setter
    def battery_profile(self, mode: Literal[0, 1]) -> None:
        if not mode in (0, 1):
            raise ValueError("battery_profile must be 0 or 1")
        self._write_word(LC709203F_CMD_BATTPROF, mode)

    @property
    def pack_size(self) -> int:
        """Returns current battery pack size"""
        return self._read_word(LC709203F_CMD_APA)

    @pack_size.setter
    def pack_size(self, size: int) -> None:
        if not PackSize.is_valid(size):
            raise ValueError("pack_size must be a PackSize")
        self._write_word(LC709203F_CMD_APA, size)

    @property
    def thermistor_bconstant(self) -> int:
        """Returns the thermistor B-constant"""
        return self._read_word(LC709203F_CMD_THERMISTORB)

    @thermistor_bconstant.setter
    def thermistor_bconstant(self, bconstant: int) -> None:
        """Sets the thermistor B-constant"""
        self._write_word(LC709203F_CMD_THERMISTORB, bconstant)

    @property
    def thermistor_enable(self) -> bool:
        """Returns the current temperature source"""
        return self._read_word(LC709203F_CMD_STATUSBIT)

    @thermistor_enable.setter
    def thermistor_enable(self, status: bool) -> None:
        """Sets the temperature source to Tsense"""
        if not isinstance(status, bool):
            raise ValueError("thermistor_enable must be True or False")
        self._write_word(LC709203F_CMD_STATUSBIT, status)

    @property
    def low_voltage_alarm_percent(self) -> int:
        """Return the current low voltage alarm percentage.
        0 indicates disabled."""
        return self._read_word(LC709203F_CMD_ALARMPERCENT)

    @low_voltage_alarm_percent.setter
    def low_voltage_alarm_percent(self, percent: int) -> None:
        """Set the low voltage alarm percentage.
        Value of 0 disables the alarm"""
        if not 0 <= percent <= 100:
            raise ValueError("alarm voltage percent must be 0-100")
        self._write_word(LC709203F_CMD_ALARMPERCENT, percent)

    @property
    def low_voltage_alarm(self) -> int:
        """Return the current low voltage alarm value in mV
        0 indicates disabled"""
        return self._read_word(LC709203F_CMD_ALARMVOLTAGE)

    @low_voltage_alarm.setter
    def low_voltage_alarm(self, voltage: int) -> None:
        """Set the low voltage alarm value in mV.
        Value of 0 disables the alarm."""
        self._write_word(LC709203F_CMD_ALARMVOLTAGE, voltage)

    # pylint: disable=no-self-use
    def _generate_crc(self, data: ReadableBuffer) -> int:
        """8-bit CRC algorithm for checking data"""
        crc = 0x00
        # calculates 8-Bit checksum with given polynomial
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x07
                else:
                    crc <<= 1
                crc &= 0xFF
        return crc

    def _read_word(self, command: int) -> int:
        self._buf[0] = LC709203F_I2CADDR_DEFAULT * 2  # write byte
        self._buf[1] = command  # command / register
        self._buf[2] = self._buf[0] | 0x1  # read byte

        for x in range(LC709203F_I2C_RETRY_COUNT):
            try:
                with self.i2c_device as i2c:
                    i2c.write_then_readinto(
                        self._buf,
                        self._buf,
                        out_start=1,
                        out_end=2,
                        in_start=3,
                        in_end=7,
                    )

                crc8 = self._generate_crc(self._buf[0:5])
                if crc8 != self._buf[5]:
                    raise OSError("CRC failure on reading word")
                return (self._buf[4] << 8) | self._buf[3]
            except OSError as exception:
                # print("OSError in read: ", x+1, "/10: ", exception)
                if x == (LC709203F_I2C_RETRY_COUNT - 1):
                    # Retry count reached
                    # print("Retry count reached in read: ", exception)
                    raise exception

        # Code should never reach this point, add this to satisfy pylint R1710.
        return None

    def _write_word(self, command: int, data: int) -> None:
        self._buf[0] = LC709203F_I2CADDR_DEFAULT * 2  # write byte
        self._buf[1] = command  # command / register
        self._buf[2] = data & 0xFF
        self._buf[3] = (data >> 8) & 0xFF
        self._buf[4] = self._generate_crc(self._buf[0:4])

        for x in range(LC709203F_I2C_RETRY_COUNT):
            try:
                with self.i2c_device as i2c:
                    i2c.write(self._buf[1:5])
                return
            except OSError as exception:
                # print("OSError in write: ", x+1, "/10: ", exception)
                if x == (LC709203F_I2C_RETRY_COUNT - 1):
                    # Retry count reached
                    # print("Retry count reached in write: ", exception)
                    raise exception
