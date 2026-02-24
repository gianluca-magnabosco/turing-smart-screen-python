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
# Dual-CPU Custom Sensors (Cross-platform: Linux + Windows)
# =============================================================================
# These custom sensor classes support dual-CPU (multi-socket) systems.
# On Linux: uses psutil + /sys/class/hwmon for per-CPU data
# On Windows: uses LibreHardwareMonitor .NET API
# Also includes RAM clock speed and disk I/O speed sensors.
# =============================================================================

import glob
import subprocess

_is_windows = platform.system() == 'Windows'
_is_linux = platform.system() == 'Linux'

# ---------------------------------------------------------------------------
# LHM lazy-load (Windows only)
# ---------------------------------------------------------------------------
_lhm_handle = None
_lhm_Hardware = None
_lhm_initialized = False


def _init_lhm():
    """Lazy-load the LHM handle (Windows only)."""
    global _lhm_handle, _lhm_Hardware, _lhm_initialized
    if _lhm_initialized:
        return
    _lhm_initialized = True
    if not _is_windows:
        return
    try:
        from library.sensors.sensors_librehardwaremonitor import handle, Hardware
        _lhm_handle = handle
        _lhm_Hardware = Hardware
    except ImportError:
        pass


def _get_cpus_lhm():
    """Return all CPU hardware objects from LHM, updated."""
    _init_lhm()
    if _lhm_handle is None:
        return []
    cpus = []
    for hardware in _lhm_handle.Hardware:
        if hardware.HardwareType == _lhm_Hardware.HardwareType.Cpu:
            hardware.Update()
            cpus.append(hardware)
    return cpus


def _get_cpu_by_index_lhm(index):
    cpus = _get_cpus_lhm()
    return cpus[index] if index < len(cpus) else None


def _find_sensor_lhm(hw, sensor_type, name_contains=None, name_startswith=None):
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
# Linux helpers: per-CPU temperature, frequency, fan via /sys and psutil
# ---------------------------------------------------------------------------
def _linux_get_cpu_temperatures():
    """Return a dict of {physical_package_id: temperature} from coretemp or k10temp."""
    temps = {}
    try:
        sensor_temps = psutil.sensors_temperatures()
        # coretemp (Intel) reports per-package temperatures
        if 'coretemp' in sensor_temps:
            for entry in sensor_temps['coretemp']:
                label = entry.label.lower()
                # "Package id 0", "Package id 1" etc.
                if 'package' in label:
                    try:
                        pkg_id = int(label.split()[-1])
                        temps[pkg_id] = entry.current
                    except (ValueError, IndexError):
                        pass
            # If no package entries found, fall back to physical_package grouping
            if not temps:
                for entry in sensor_temps['coretemp']:
                    if entry.label.startswith('Core'):
                        temps.setdefault(0, entry.current)
        # k10temp or zenpower (AMD)
        for key in ['k10temp', 'zenpower']:
            if key in sensor_temps and not temps:
                for i, entry in enumerate(sensor_temps[key]):
                    temps[i] = entry.current
    except Exception:
        pass
    return temps


def _linux_get_per_cpu_frequencies():
    """Return a dict of {cpu_package_index: avg_frequency_mhz}.
    Groups logical CPUs by physical package ID."""
    pkg_freqs = {}
    try:
        # Read per-CPU frequencies and group by physical package
        per_cpu = psutil.cpu_freq(percpu=True)
        if per_cpu:
            # Try to map logical CPU -> physical package via sysfs
            pkg_map = {}  # logical_cpu_id -> package_id
            for i in range(len(per_cpu)):
                try:
                    pkg_path = f'/sys/devices/system/cpu/cpu{i}/topology/physical_package_id'
                    with open(pkg_path) as f:
                        pkg_map[i] = int(f.read().strip())
                except (FileNotFoundError, ValueError):
                    pkg_map[i] = 0  # fallback: all on package 0

            # Group frequencies by package
            from collections import defaultdict
            grouped = defaultdict(list)
            for i, freq in enumerate(per_cpu):
                pkg_id = pkg_map.get(i, 0)
                grouped[pkg_id].append(freq.current)

            for pkg_id, freqs in grouped.items():
                pkg_freqs[pkg_id] = mean(freqs)
    except Exception:
        pass
    return pkg_freqs


def _linux_get_per_cpu_max_frequencies():
    """Return a dict of {cpu_package_index: max_frequency_mhz}.
    Groups logical CPUs by physical package ID and takes the max."""
    pkg_max_freqs = {}
    try:
        per_cpu = psutil.cpu_freq(percpu=True)
        if per_cpu:
            pkg_map = {}
            for i in range(len(per_cpu)):
                try:
                    with open(f'/sys/devices/system/cpu/cpu{i}/topology/physical_package_id') as f:
                        pkg_map[i] = int(f.read().strip())
                except (FileNotFoundError, ValueError):
                    pkg_map[i] = 0

            from collections import defaultdict
            grouped = defaultdict(list)
            for i, freq in enumerate(per_cpu):
                pkg_id = pkg_map.get(i, 0)
                max_mhz = freq.max if freq.max else 0
                if max_mhz <= 0:
                    # Fallback: read from sysfs (value is in KHz)
                    for path in [
                        f'/sys/devices/system/cpu/cpu{i}/cpufreq/cpuinfo_max_freq',
                        f'/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_max_freq'
                    ]:
                        try:
                            with open(path) as f:
                                max_mhz = int(f.read().strip()) / 1000
                                break
                        except Exception:
                            pass
                if max_mhz > 0:
                    grouped[pkg_id].append(max_mhz)

            for pkg_id, maxes in grouped.items():
                pkg_max_freqs[pkg_id] = max(maxes)
    except Exception:
        pass
    return pkg_max_freqs


def _linux_get_per_cpu_usage():
    """Return a dict of {cpu_package_index: usage_percent}.
    Groups logical CPUs by physical package ID. Uses cached interval."""
    pkg_usage = {}
    try:
        per_cpu = psutil.cpu_percent(interval=None, percpu=True)
        if per_cpu:
            pkg_map = {}
            for i in range(len(per_cpu)):
                try:
                    pkg_path = f'/sys/devices/system/cpu/cpu{i}/topology/physical_package_id'
                    with open(pkg_path) as f:
                        pkg_map[i] = int(f.read().strip())
                except (FileNotFoundError, ValueError):
                    pkg_map[i] = 0

            from collections import defaultdict
            grouped = defaultdict(list)
            for i, pct in enumerate(per_cpu):
                pkg_id = pkg_map.get(i, 0)
                grouped[pkg_id].append(pct)

            for pkg_id, pcts in grouped.items():
                pkg_usage[pkg_id] = mean(pcts)
    except Exception:
        pass
    return pkg_usage


def _linux_get_memory_clock():
    """Try to read memory clock speed on Linux via dmidecode or /sys."""
    # Method 1: Try dmidecode directly (works if running as root)
    try:
        output = subprocess.check_output(
            ['dmidecode', '-t', 'memory'], stderr=subprocess.DEVNULL, timeout=2
        ).decode('utf-8', errors='replace')
        speeds = []
        for line in output.splitlines():
            line = line.strip()
            if line.startswith('Configured Memory Speed:') or line.startswith('Configured Clock Speed:'):
                val = line.split(':')[1].strip().split()[0]
                if val.isdigit() and int(val) > 0:
                    speeds.append(int(val))
        if speeds:
            return max(speeds)
    except Exception:
        pass
    # Method 2: Try sudo -n dmidecode (works if NOPASSWD is configured)
    try:
        output = subprocess.check_output(
            ['sudo', '-n', 'dmidecode', '-t', 'memory'], stderr=subprocess.DEVNULL, timeout=3
        ).decode('utf-8', errors='replace')
        speeds = []
        for line in output.splitlines():
            line = line.strip()
            if line.startswith('Configured Memory Speed:') or line.startswith('Configured Clock Speed:'):
                val = line.split(':')[1].strip().split()[0]
                if val.isdigit() and int(val) > 0:
                    speeds.append(int(val))
        if speeds:
            return max(speeds)
    except Exception:
        pass
    # Method 3: Try decode-dimms from i2c-tools
    try:
        output = subprocess.check_output(
            ['decode-dimms'], stderr=subprocess.DEVNULL, timeout=5
        ).decode('utf-8', errors='replace')
        for line in output.splitlines():
            if 'Maximum module speed' in line:
                parts = line.split()
                for p in parts:
                    if p.isdigit() and int(p) > 100:
                        return int(p)
    except Exception:
        pass
    # Method 4: Fallback - return 0 (not available without root)
    return 0


# ---------------------------------------------------------------------------
# Per-CPU Percentage (Load %)
# ---------------------------------------------------------------------------
class Cpu0Percentage(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0

    def as_numeric(self) -> float:
        if _is_linux:
            usage = _linux_get_per_cpu_usage()
            if 0 in usage:
                Cpu0Percentage.value = usage[0]
                Cpu0Percentage.last_val.append(Cpu0Percentage.value)
                Cpu0Percentage.last_val.pop(0)
                return Cpu0Percentage.value
        elif _is_windows:
            _init_lhm()
            cpu = _get_cpu_by_index_lhm(0)
            if cpu:
                sensor = _find_sensor_lhm(cpu, _lhm_Hardware.SensorType.Load, name_startswith="CPU Total")
                if sensor:
                    Cpu0Percentage.value = float(sensor.Value)
                    Cpu0Percentage.last_val.append(Cpu0Percentage.value)
                    Cpu0Percentage.last_val.pop(0)
                    return Cpu0Percentage.value
        return math.nan

    def as_string(self) -> str:
        return f'{Cpu0Percentage.value:.0f}%'

    def last_values(self) -> List[float]:
        return Cpu0Percentage.last_val


class Cpu1Percentage(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0

    def as_numeric(self) -> float:
        if _is_linux:
            usage = _linux_get_per_cpu_usage()
            if 1 in usage:
                Cpu1Percentage.value = usage[1]
                Cpu1Percentage.last_val.append(Cpu1Percentage.value)
                Cpu1Percentage.last_val.pop(0)
                return Cpu1Percentage.value
        elif _is_windows:
            _init_lhm()
            cpu = _get_cpu_by_index_lhm(1)
            if cpu:
                sensor = _find_sensor_lhm(cpu, _lhm_Hardware.SensorType.Load, name_startswith="CPU Total")
                if sensor:
                    Cpu1Percentage.value = float(sensor.Value)
                    Cpu1Percentage.last_val.append(Cpu1Percentage.value)
                    Cpu1Percentage.last_val.pop(0)
                    return Cpu1Percentage.value
        return math.nan

    def as_string(self) -> str:
        return f'{Cpu1Percentage.value:.0f}%'

    def last_values(self) -> List[float]:
        return Cpu1Percentage.last_val


# ---------------------------------------------------------------------------
# Per-CPU Temperature
# ---------------------------------------------------------------------------
class Cpu0Temperature(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0

    def as_numeric(self) -> float:
        if _is_linux:
            temps = _linux_get_cpu_temperatures()
            if 0 in temps:
                Cpu0Temperature.value = temps[0]
                Cpu0Temperature.last_val.append(Cpu0Temperature.value)
                Cpu0Temperature.last_val.pop(0)
                return Cpu0Temperature.value
        elif _is_windows:
            _init_lhm()
            cpu = _get_cpu_by_index_lhm(0)
            if cpu:
                for name_prefix in ["Core Average", "Core Max", "CPU Package", "Core"]:
                    sensor = _find_sensor_lhm(cpu, _lhm_Hardware.SensorType.Temperature, name_startswith=name_prefix)
                    if sensor:
                        Cpu0Temperature.value = float(sensor.Value)
                        Cpu0Temperature.last_val.append(Cpu0Temperature.value)
                        Cpu0Temperature.last_val.pop(0)
                        return Cpu0Temperature.value
        return math.nan

    def as_string(self) -> str:
        return f'{Cpu0Temperature.value:.0f}\u00b0C'

    def last_values(self) -> List[float]:
        return Cpu0Temperature.last_val


class Cpu1Temperature(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0

    def as_numeric(self) -> float:
        if _is_linux:
            temps = _linux_get_cpu_temperatures()
            if 1 in temps:
                Cpu1Temperature.value = temps[1]
                Cpu1Temperature.last_val.append(Cpu1Temperature.value)
                Cpu1Temperature.last_val.pop(0)
                return Cpu1Temperature.value
        elif _is_windows:
            _init_lhm()
            cpu = _get_cpu_by_index_lhm(1)
            if cpu:
                for name_prefix in ["Core Average", "Core Max", "CPU Package", "Core"]:
                    sensor = _find_sensor_lhm(cpu, _lhm_Hardware.SensorType.Temperature, name_startswith=name_prefix)
                    if sensor:
                        Cpu1Temperature.value = float(sensor.Value)
                        Cpu1Temperature.last_val.append(Cpu1Temperature.value)
                        Cpu1Temperature.last_val.pop(0)
                        return Cpu1Temperature.value
        return math.nan

    def as_string(self) -> str:
        return f'{Cpu1Temperature.value:.0f}\u00b0C'

    def last_values(self) -> List[float]:
        return Cpu1Temperature.last_val


# ---------------------------------------------------------------------------
# Per-CPU Frequency (Clock Speed)
# ---------------------------------------------------------------------------
class Cpu0Frequency(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0
    max_freq = 0.0  # Cached max frequency in MHz
    _max_freq_loaded = False

    def as_numeric(self) -> float:
        if not Cpu0Frequency._max_freq_loaded:
            Cpu0Frequency._max_freq_loaded = True
            if _is_linux:
                max_freqs = _linux_get_per_cpu_max_frequencies()
                if 0 in max_freqs:
                    Cpu0Frequency.max_freq = max_freqs[0]
        if _is_linux:
            freqs = _linux_get_per_cpu_frequencies()
            if 0 in freqs:
                Cpu0Frequency.value = freqs[0]
                Cpu0Frequency.last_val.append(Cpu0Frequency.value)
                Cpu0Frequency.last_val.pop(0)
                return Cpu0Frequency.value
        elif _is_windows:
            _init_lhm()
            cpu = _get_cpu_by_index_lhm(0)
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
        current_ghz = Cpu0Frequency.value / 1000
        if Cpu0Frequency.max_freq > 0:
            max_ghz = Cpu0Frequency.max_freq / 1000
            return f'{current_ghz:.2f}/{max_ghz:.2f} GHz'
        return f'{current_ghz:>4.2f} GHz'

    def last_values(self) -> List[float]:
        return Cpu0Frequency.last_val


class Cpu1Frequency(CustomDataSource):
    last_val = [math.nan] * 10
    value = 0.0
    max_freq = 0.0  # Cached max frequency in MHz
    _max_freq_loaded = False

    def as_numeric(self) -> float:
        if not Cpu1Frequency._max_freq_loaded:
            Cpu1Frequency._max_freq_loaded = True
            if _is_linux:
                max_freqs = _linux_get_per_cpu_max_frequencies()
                if 1 in max_freqs:
                    Cpu1Frequency.max_freq = max_freqs[1]
        if _is_linux:
            freqs = _linux_get_per_cpu_frequencies()
            if 1 in freqs:
                Cpu1Frequency.value = freqs[1]
                Cpu1Frequency.last_val.append(Cpu1Frequency.value)
                Cpu1Frequency.last_val.pop(0)
                return Cpu1Frequency.value
        elif _is_windows:
            _init_lhm()
            cpu = _get_cpu_by_index_lhm(1)
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
        current_ghz = Cpu1Frequency.value / 1000
        if Cpu1Frequency.max_freq > 0:
            max_ghz = Cpu1Frequency.max_freq / 1000
            return f'{current_ghz:.2f}/{max_ghz:.2f} GHz'
        return f'{current_ghz:>4.2f} GHz'

    def last_values(self) -> List[float]:
        return Cpu1Frequency.last_val


# ---------------------------------------------------------------------------
# RAM Clock Speed
# Linux: reads via dmidecode (needs root) or returns 0
# Windows: reads from LHM Memory hardware
# ---------------------------------------------------------------------------
class MemoryClockSpeed(CustomDataSource):
    value = 0.0
    _cached = False

    def as_numeric(self) -> float:
        # Memory clock rarely changes, cache after first read
        if MemoryClockSpeed._cached and MemoryClockSpeed.value > 0:
            return MemoryClockSpeed.value

        if _is_linux:
            speed = _linux_get_memory_clock()
            if speed > 0:
                MemoryClockSpeed.value = float(speed)
                MemoryClockSpeed._cached = True
                return MemoryClockSpeed.value
        elif _is_windows:
            _init_lhm()
            if _lhm_handle is not None:
                try:
                    for hardware in _lhm_handle.Hardware:
                        if hardware.HardwareType == _lhm_Hardware.HardwareType.Memory:
                            hardware.Update()
                            for sensor in hardware.Sensors:
                                if (sensor.SensorType == _lhm_Hardware.SensorType.Clock
                                        and sensor.Value is not None):
                                    MemoryClockSpeed.value = float(sensor.Value)
                                    MemoryClockSpeed._cached = True
                                    return MemoryClockSpeed.value
                except Exception:
                    pass
        return math.nan

    def as_string(self) -> str:
        if MemoryClockSpeed.value > 0:
            return f'{MemoryClockSpeed.value:>4.0f} MHz'
        return 'N/A'

    def last_values(self) -> List[float]:
        return None


# ---------------------------------------------------------------------------
# Disk Read/Write Speed (via psutil delta calculation - cross platform)
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
                DiskReadSpeed.value = (counters.read_bytes - DiskReadSpeed._prev_bytes) / dt / (1024 * 1024)
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
                DiskWriteSpeed.value = (counters.write_bytes - DiskWriteSpeed._prev_bytes) / dt / (1024 * 1024)
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


# ---------------------------------------------------------------------------
# CPU Fan Speeds (via psutil sensors_fans - nct6779 chip on X99 dual-CPU)
# ---------------------------------------------------------------------------
def _linux_get_fan_speeds() -> dict:
    """Get fan speeds from nct6779 chip via psutil."""
    try:
        fans = psutil.sensors_fans()
        if 'nct6779' in fans:
            return {fan.label: fan.current for fan in fans['nct6779']}
    except Exception:
        pass
    return {}


class Cpu0FanSpeed(CustomDataSource):
    """Fan speed for CPU 0 (nct6779 fan1)."""
    last_val = [math.nan] * 10
    value = 0.0

    def as_numeric(self) -> float:
        if platform.system() == "Linux":
            fans = _linux_get_fan_speeds()
            Cpu0FanSpeed.value = fans.get('fan1', 0)
        Cpu0FanSpeed.last_val.append(Cpu0FanSpeed.value)
        Cpu0FanSpeed.last_val.pop(0)
        return Cpu0FanSpeed.value

    def as_string(self) -> str:
        return f'{Cpu0FanSpeed.value:.0f} RPM'

    def last_values(self) -> List[float]:
        return Cpu0FanSpeed.last_val


class Cpu1FanSpeed(CustomDataSource):
    """Fan speed for CPU 1 (nct6779 fan2)."""
    last_val = [math.nan] * 10
    value = 0.0

    def as_numeric(self) -> float:
        if platform.system() == "Linux":
            fans = _linux_get_fan_speeds()
            Cpu1FanSpeed.value = fans.get('fan2', 0)
        Cpu1FanSpeed.last_val.append(Cpu1FanSpeed.value)
        Cpu1FanSpeed.last_val.pop(0)
        return Cpu1FanSpeed.value

    def as_string(self) -> str:
        return f'{Cpu1FanSpeed.value:.0f} RPM'

    def last_values(self) -> List[float]:
        return Cpu1FanSpeed.last_val


# ---------------------------------------------------------------------------
# NVMe Temperature (via psutil sensors_temperatures - Composite reading)
# ---------------------------------------------------------------------------
class NvmeTemperature(CustomDataSource):
    """NVMe drive Composite temperature."""
    last_val = [math.nan] * 10
    value = 0.0

    def as_numeric(self) -> float:
        if platform.system() == "Linux":
            try:
                temps = psutil.sensors_temperatures()
                if 'nvme' in temps:
                    for t in temps['nvme']:
                        if t.label == 'Composite':
                            NvmeTemperature.value = t.current
                            break
            except Exception:
                pass
        NvmeTemperature.last_val.append(NvmeTemperature.value)
        NvmeTemperature.last_val.pop(0)
        return NvmeTemperature.value

    def as_string(self) -> str:
        return f'{NvmeTemperature.value:.0f}\u00b0C'

    def last_values(self) -> List[float]:
        return NvmeTemperature.last_val
