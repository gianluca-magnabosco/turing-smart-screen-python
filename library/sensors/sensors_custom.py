# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# Copyright (C) 2021 Matthieu Houdebine (mathoudebine)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# This file allows to add custom data source as sensors and display them in System Monitor themes
# There is no limitation on how much custom data source classes can be added to this file
# See CustomDataExample theme for the theme implementation part

import math
import os
import platform
import time
from abc import ABC, abstractmethod
from statistics import mean
from typing import List

import psutil


# Custom data classes must be implemented in this file, inherit the CustomDataSource and implement its 2 methods
class CustomDataSource(ABC):
    @abstractmethod
    def as_numeric(self) -> float:
        # Numeric value will be used for graph and radial progress bars
        # If there is no numeric value, keep this function empty
        pass

    @abstractmethod
    def as_string(self) -> str:
        # Text value will be used for text display and radial progress bar inner text
        # Numeric value can be formatted here to be displayed as expected
        # It is also possible to return a text unrelated to the numeric value
        # If this function is empty, the numeric value will be used as string without formatting
        pass

    @abstractmethod
    def last_values(self) -> List[float]:
        # List of last numeric values will be used for plot graph
        # If you do not want to draw a line graph or if your custom data has no numeric values, keep this function empty
        pass


# Example for a custom data class that has numeric and text values
class ExampleCustomNumericData(CustomDataSource):
    # This list is used to store the last 10 values to display a line graph
    last_val = [math.nan] * 10  # By default, it is filed with math.nan values to indicate there is no data stored

    def as_numeric(self) -> float:
        # Numeric value will be used for graph and radial progress bars
        # Here a Python function from another module can be called to get data
        # Example: self.value = my_module.get_rgb_led_brightness() / audio.system_volume() ...
        self.value = 75.845

        # Store the value to the history list that will be used for line graph
        self.last_val.append(self.value)
        # Also remove the oldest value from history list
        self.last_val.pop(0)

        return self.value

    def as_string(self) -> str:
        # Text value will be used for text display and radial progress bar inner text.
        # Numeric value can be formatted here to be displayed as expected
        # It is also possible to return a text unrelated to the numeric value
        # If this function is empty, the numeric value will be used as string without formatting
        # Example here: format numeric value: add unit as a suffix, and keep 1 digit decimal precision
        return f'{self.value:>5.1f}%'
        # Important note! If your numeric value can vary in size, be sure to display it with a default size.
        # E.g. if your value can range from 0 to 9999, you need to display it with at least 4 characters every time.
        # --> return f'{self.as_numeric():>4}%'
        # Otherwise, part of the previous value can stay displayed ("ghosting") after a refresh

    def last_values(self) -> List[float]:
        # List of last numeric values will be used for plot graph
        return self.last_val


# Example for a custom data class that only has text values
class ExampleCustomTextOnlyData(CustomDataSource):
    def as_numeric(self) -> float:
        # If there is no numeric value, keep this function empty
        pass

    def as_string(self) -> str:
        # If a custom data class only has text values, it won't be possible to display graph or radial bars
        return "Python: " + platform.python_version()

    def last_values(self) -> List[float]:
        # If a custom data class only has text values, it won't be possible to display line graph
        pass


# =============================================================================
# Dual-CPU Custom Sensors
# =============================================================================
# These custom sensor classes support dual-CPU (multi-socket) systems by
# querying each CPU independently via LibreHardwareMonitor's .NET API.
# Also includes RAM clock speed and disk I/O speed sensors.
#
# These sensors require HW_SENSORS to be set to LHM or AUTO (Windows only).
# =============================================================================

# Lazy-loaded LHM references — only imported when a dual-CPU sensor is first used
_lhm_handle = None
_lhm_Hardware = None
_lhm_initialized = False


def _init_lhm():
    """Lazy-load the LHM handle. This avoids import errors when LHM is not available."""
    global _lhm_handle, _lhm_Hardware, _lhm_initialized
    if _lhm_initialized:
        return
    _lhm_initialized = True
    try:
        from library.sensors.sensors_librehardwaremonitor import handle, Hardware
        _lhm_handle = handle
        _lhm_Hardware = Hardware
    except ImportError:
        pass


def _get_cpus():
    """Return a list of all CPU hardware objects from LHM, updated."""
    _init_lhm()
    if _lhm_handle is None:
        return []
    cpus = []
    for hardware in _lhm_handle.Hardware:
        if hardware.HardwareType == _lhm_Hardware.HardwareType.Cpu:
            hardware.Update()
            cpus.append(hardware)
    return cpus


def _get_cpu_by_index(index):
    """Return the Nth CPU hardware object (0-based), or None."""
    cpus = _get_cpus()
    if index < len(cpus):
        return cpus[index]
    return None


def _find_sensor(hw, sensor_type, name_contains=None, name_startswith=None):
    """Find a sensor on a hardware object by type and optional name filter."""
    if hw is None:
        return None
    for sensor in hw.Sensors:
        if sensor.SensorType == sensor_type and sensor.Value is not None:
            name = str(sensor.Name)
            if name_contains and name_contains not in name:
                continue
            if name_startswith and not name.startswith(name_startswith):
                continue
            return sensor
    return None


# ---------------------------------------------------------------------------
# Per-CPU Percentage (Load %)
# ---------------------------------------------------------------------------
class Cpu0Percentage(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0

    def as_numeric(self) -> float:
        _init_lhm()
        cpu = _get_cpu_by_index(0)
        if cpu:
            sensor = _find_sensor(cpu, _lhm_Hardware.SensorType.Load, name_startswith="CPU Total")
            if sensor:
                Cpu0Percentage.value = float(sensor.Value)
                Cpu0Percentage.last_val.append(Cpu0Percentage.value)
                Cpu0Percentage.last_val.pop(0)
                return Cpu0Percentage.value
        return math.nan

    def as_string(self) -> str:
        return f'{Cpu0Percentage.value:>3.0f}%'

    def last_values(self) -> List[float]:
        return Cpu0Percentage.last_val


class Cpu1Percentage(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0

    def as_numeric(self) -> float:
        _init_lhm()
        cpu = _get_cpu_by_index(1)
        if cpu:
            sensor = _find_sensor(cpu, _lhm_Hardware.SensorType.Load, name_startswith="CPU Total")
            if sensor:
                Cpu1Percentage.value = float(sensor.Value)
                Cpu1Percentage.last_val.append(Cpu1Percentage.value)
                Cpu1Percentage.last_val.pop(0)
                return Cpu1Percentage.value
        return math.nan

    def as_string(self) -> str:
        return f'{Cpu1Percentage.value:>3.0f}%'

    def last_values(self) -> List[float]:
        return Cpu1Percentage.last_val


# ---------------------------------------------------------------------------
# Per-CPU Temperature
# ---------------------------------------------------------------------------
class Cpu0Temperature(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0

    def as_numeric(self) -> float:
        _init_lhm()
        cpu = _get_cpu_by_index(0)
        if cpu:
            # Try Core Average first, then Core Max, then CPU Package
            for name_prefix in ["Core Average", "Core Max", "CPU Package", "Core"]:
                sensor = _find_sensor(cpu, _lhm_Hardware.SensorType.Temperature, name_startswith=name_prefix)
                if sensor:
                    Cpu0Temperature.value = float(sensor.Value)
                    Cpu0Temperature.last_val.append(Cpu0Temperature.value)
                    Cpu0Temperature.last_val.pop(0)
                    return Cpu0Temperature.value
        return math.nan

    def as_string(self) -> str:
        return f'{Cpu0Temperature.value:>3.0f}°C'

    def last_values(self) -> List[float]:
        return Cpu0Temperature.last_val


class Cpu1Temperature(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0

    def as_numeric(self) -> float:
        _init_lhm()
        cpu = _get_cpu_by_index(1)
        if cpu:
            for name_prefix in ["Core Average", "Core Max", "CPU Package", "Core"]:
                sensor = _find_sensor(cpu, _lhm_Hardware.SensorType.Temperature, name_startswith=name_prefix)
                if sensor:
                    Cpu1Temperature.value = float(sensor.Value)
                    Cpu1Temperature.last_val.append(Cpu1Temperature.value)
                    Cpu1Temperature.last_val.pop(0)
                    return Cpu1Temperature.value
        return math.nan

    def as_string(self) -> str:
        return f'{Cpu1Temperature.value:>3.0f}°C'

    def last_values(self) -> List[float]:
        return Cpu1Temperature.last_val


# ---------------------------------------------------------------------------
# Per-CPU Frequency (Clock Speed)
# ---------------------------------------------------------------------------
class Cpu0Frequency(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0

    def as_numeric(self) -> float:
        _init_lhm()
        cpu = _get_cpu_by_index(0)
        if cpu:
            frequencies = []
            for sensor in cpu.Sensors:
                if (sensor.SensorType == _lhm_Hardware.SensorType.Clock
                        and "Core #" in str(sensor.Name)
                        and "Effective" not in str(sensor.Name)
                        and sensor.Value is not None):
                    frequencies.append(float(sensor.Value))
            if frequencies:
                Cpu0Frequency.value = mean(frequencies)
                Cpu0Frequency.last_val.append(Cpu0Frequency.value)
                Cpu0Frequency.last_val.pop(0)
                return Cpu0Frequency.value
        return math.nan

    def as_string(self) -> str:
        return f'{Cpu0Frequency.value / 1000:>4.2f} GHz'

    def last_values(self) -> List[float]:
        return Cpu0Frequency.last_val


class Cpu1Frequency(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0

    def as_numeric(self) -> float:
        _init_lhm()
        cpu = _get_cpu_by_index(1)
        if cpu:
            frequencies = []
            for sensor in cpu.Sensors:
                if (sensor.SensorType == _lhm_Hardware.SensorType.Clock
                        and "Core #" in str(sensor.Name)
                        and "Effective" not in str(sensor.Name)
                        and sensor.Value is not None):
                    frequencies.append(float(sensor.Value))
            if frequencies:
                Cpu1Frequency.value = mean(frequencies)
                Cpu1Frequency.last_val.append(Cpu1Frequency.value)
                Cpu1Frequency.last_val.pop(0)
                return Cpu1Frequency.value
        return math.nan

    def as_string(self) -> str:
        return f'{Cpu1Frequency.value / 1000:>4.2f} GHz'

    def last_values(self) -> List[float]:
        return Cpu1Frequency.last_val


# ---------------------------------------------------------------------------
# Per-CPU Fan Speed (queried from motherboard sub-hardware)
# On dual-socket boards, fan sensors are typically on the motherboard chipset.
# We attempt to match Fan #1 to CPU0 and Fan #2 to CPU1.
# You may need to adjust the fan name matching for your specific motherboard.
# ---------------------------------------------------------------------------
class Cpu0FanSpeed(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0

    def as_numeric(self) -> float:
        _init_lhm()
        if _lhm_handle is None:
            return math.nan
        try:
            for hardware in _lhm_handle.Hardware:
                if hardware.HardwareType == _lhm_Hardware.HardwareType.Motherboard:
                    hardware.Update()
                    for sh in hardware.SubHardware:
                        sh.Update()
                        for sensor in sh.Sensors:
                            if (sensor.SensorType == _lhm_Hardware.SensorType.Fan
                                    and sensor.Value is not None
                                    and ("#1" in str(sensor.Name) or "CPU" in str(sensor.Name))):
                                Cpu0FanSpeed.value = float(sensor.Value)
                                Cpu0FanSpeed.last_val.append(Cpu0FanSpeed.value)
                                Cpu0FanSpeed.last_val.pop(0)
                                return Cpu0FanSpeed.value
        except Exception:
            pass
        return math.nan

    def as_string(self) -> str:
        return f'{Cpu0FanSpeed.value:>4.0f} RPM'

    def last_values(self) -> List[float]:
        return Cpu0FanSpeed.last_val


class Cpu1FanSpeed(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0

    def as_numeric(self) -> float:
        _init_lhm()
        if _lhm_handle is None:
            return math.nan
        try:
            for hardware in _lhm_handle.Hardware:
                if hardware.HardwareType == _lhm_Hardware.HardwareType.Motherboard:
                    hardware.Update()
                    for sh in hardware.SubHardware:
                        sh.Update()
                        for sensor in sh.Sensors:
                            if (sensor.SensorType == _lhm_Hardware.SensorType.Fan
                                    and sensor.Value is not None
                                    and "#2" in str(sensor.Name)):
                                Cpu1FanSpeed.value = float(sensor.Value)
                                Cpu1FanSpeed.last_val.append(Cpu1FanSpeed.value)
                                Cpu1FanSpeed.last_val.pop(0)
                                return Cpu1FanSpeed.value
        except Exception:
            pass
        return math.nan

    def as_string(self) -> str:
        return f'{Cpu1FanSpeed.value:>4.0f} RPM'

    def last_values(self) -> List[float]:
        return Cpu1FanSpeed.last_val


# ---------------------------------------------------------------------------
# RAM Clock Speed (via LHM Memory hardware)
# ---------------------------------------------------------------------------
class MemoryClockSpeed(CustomDataSource):
    value = 0.0

    def as_numeric(self) -> float:
        _init_lhm()
        if _lhm_handle is None:
            return math.nan
        try:
            for hardware in _lhm_handle.Hardware:
                if hardware.HardwareType == _lhm_Hardware.HardwareType.Memory:
                    hardware.Update()
                    for sensor in hardware.Sensors:
                        if (sensor.SensorType == _lhm_Hardware.SensorType.Clock
                                and sensor.Value is not None):
                            MemoryClockSpeed.value = float(sensor.Value)
                            return MemoryClockSpeed.value
        except Exception:
            pass
        return math.nan

    def as_string(self) -> str:
        return f'{MemoryClockSpeed.value:>4.0f} MHz'

    def last_values(self) -> List[float]:
        return None


# ---------------------------------------------------------------------------
# Disk Read/Write Speed (via psutil delta calculation)
# psutil.disk_io_counters() returns cumulative bytes; we compute the rate
# by tracking the delta between calls.
# ---------------------------------------------------------------------------
class DiskReadSpeed(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0
    _prev_bytes = None
    _prev_time = None

    def as_numeric(self) -> float:
        counters = psutil.disk_io_counters()
        now = time.time()
        if DiskReadSpeed._prev_bytes is not None and DiskReadSpeed._prev_time is not None:
            dt = now - DiskReadSpeed._prev_time
            if dt > 0:
                DiskReadSpeed.value = (counters.read_bytes - DiskReadSpeed._prev_bytes) / dt / (1024 * 1024)  # MB/s
        DiskReadSpeed._prev_bytes = counters.read_bytes
        DiskReadSpeed._prev_time = now

        DiskReadSpeed.last_val.append(DiskReadSpeed.value)
        DiskReadSpeed.last_val.pop(0)
        return DiskReadSpeed.value

    def as_string(self) -> str:
        if DiskReadSpeed.value >= 1000:
            return f'{DiskReadSpeed.value / 1024:>5.1f} GB/s'
        return f'{DiskReadSpeed.value:>5.1f} MB/s'

    def last_values(self) -> List[float]:
        return DiskReadSpeed.last_val


class DiskWriteSpeed(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0
    _prev_bytes = None
    _prev_time = None

    def as_numeric(self) -> float:
        counters = psutil.disk_io_counters()
        now = time.time()
        if DiskWriteSpeed._prev_bytes is not None and DiskWriteSpeed._prev_time is not None:
            dt = now - DiskWriteSpeed._prev_time
            if dt > 0:
                DiskWriteSpeed.value = (counters.write_bytes - DiskWriteSpeed._prev_bytes) / dt / (1024 * 1024)  # MB/s
        DiskWriteSpeed._prev_bytes = counters.write_bytes
        DiskWriteSpeed._prev_time = now

        DiskWriteSpeed.last_val.append(DiskWriteSpeed.value)
        DiskWriteSpeed.last_val.pop(0)
        return DiskWriteSpeed.value

    def as_string(self) -> str:
        if DiskWriteSpeed.value >= 1000:
            return f'{DiskWriteSpeed.value / 1024:>5.1f} GB/s'
        return f'{DiskWriteSpeed.value:>5.1f} MB/s'

    def last_values(self) -> List[float]:
        return DiskWriteSpeed.last_val
