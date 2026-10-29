# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Industrial USB Serial Sensor Receiver Module.
Phase 1: Real-time telemetry receiver for ESP32 controller over USB Serial.

Architecture:
  ESP32 -> USB Serial -> SerialSensorReceiver -> Data Validation -> Hazard Assessment -> Dashboard & Reports

Safety & Calibration Notice:
- gas_raw is an uncalibrated MQ-135 ADC count (NOT ppm).
- noise_raw is an uncalibrated microphone ADC count (NOT dB).
- These raw values must NEVER be converted to ppm or dB without validated physical calibration.
- Raw values are never classified as SAFE.
"""

import atexit
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import logging
import math
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

try:
    import serial
    import serial.tools.list_ports
    PYSERIAL_AVAILABLE = True
except ImportError:
    PYSERIAL_AVAILABLE = False
    serial = None

logger = logging.getLogger("safeedge.serial_receiver")


class SerialConnectionStatus(str, Enum):
    """Connection states for the USB serial link."""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    STALE = "STALE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ESP32ParsedData:
    """
    Validated telemetry payload received from an ESP32 microcontroller.
    All sensor readings have undergone validation against schema and bounds.
    """
    device_id: str
    temperature_c: Optional[float]
    humidity_pct: Optional[float]
    gas_raw: Optional[float]      # Raw MQ-135 ADC count (uncalibrated)
    noise_raw: Optional[float]    # Raw microphone ADC count (uncalibrated)
    raw_json: str
    pm1_0: Optional[float] = None
    pm2_5: Optional[float] = None
    pm10: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    iso_timestamp: str = ""

    def __post_init__(self):
        if not self.iso_timestamp:
            object.__setattr__(self, "iso_timestamp", self.timestamp.isoformat())

    @property
    def has_gas_raw(self) -> bool:
        return self.gas_raw is not None

    @property
    def has_noise_raw(self) -> bool:
        return self.noise_raw is not None

    def to_dict(self) -> Dict[str, Any]:
        """Returns structured dictionary for dashboard integration and logging."""
        d = {
            "device_id": self.device_id,
            "temperature_c": self.temperature_c,
            "humidity_pct": self.humidity_pct,
            "gas_raw": self.gas_raw,
            "noise_raw": self.noise_raw,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "iso_timestamp": self.iso_timestamp,
            "data_source": "live_esp32",
            "gas_calibrated": False,
            "noise_calibrated": False,
        }
        if self.pm10 is not None:
            d["pm10"] = self.pm10
        return d


class SerialSensorReceiver:
    """
    Thread-safe, non-blocking USB Serial telemetry receiver for ESP32.
    Spawns a single background daemon thread to read newline-delimited JSON
    telemetry strings from a configurable COM port.
    """

    def __init__(
        self,
        default_baud_rate: int = 115200,
        stale_timeout_seconds: float = 5.0,
        on_reading_callback: Optional[Callable[[ESP32ParsedData], None]] = None,
    ):
        self.default_baud_rate = default_baud_rate
        self.stale_timeout_seconds = stale_timeout_seconds
        self.on_reading_callback = on_reading_callback

        self._port: Optional[str] = None
        self._baud_rate: int = default_baud_rate
        self._serial_conn: Optional[Any] = None

        self._status: SerialConnectionStatus = SerialConnectionStatus.DISCONNECTED
        self._status_message: str = "Serial link is disconnected."
        self._last_error: Optional[str] = None

        self._latest_reading: Optional[ESP32ParsedData] = None
        self._last_message_time: Optional[float] = None
        self._last_message_raw: str = ""

        # Counters
        self._messages_received: int = 0
        self._errors_count: int = 0

        # Concurrency management
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._reader_thread: Optional[threading.Thread] = None
        self._mock_connected: bool = False

        # Register cleanup on interpreter shutdown
        atexit.register(self.disconnect)

    @classmethod
    def list_available_ports(cls) -> List[Dict[str, str]]:
        """
        Enumerates all available serial / COM ports on the system.
        Returns a list of dictionaries with port name, description, and hwid.
        """
        if not PYSERIAL_AVAILABLE:
            return []

        try:
            ports = serial.tools.list_ports.comports()
            port_list = []
            for p in ports:
                port_list.append({
                    "port": p.device,
                    "description": p.description or p.device,
                    "hwid": p.hwid or "",
                })
            return port_list
        except Exception as e:
            logger.warning(f"Error enumerating serial ports: {e}")
            return []

    # -------------------------------------------------------------------------
    # Connection Lifecycle Operations
    # -------------------------------------------------------------------------

    def connect(self, port: str, baud_rate: Optional[int] = None) -> bool:
        """
        Opens connection to the specified serial port and starts background reader thread.
        Thread-safe: safely disconnects any existing connection before opening new one.
        """
        with self._lock:
            # If already connected to the exact same port and thread is alive, return True
            if (
                self._status == SerialConnectionStatus.CONNECTED
                and self._port == port
                and self._reader_thread
                and self._reader_thread.is_alive()
            ):
                return True

            # Disconnect any active connection first
            self.disconnect()

            if not PYSERIAL_AVAILABLE:
                self._status = SerialConnectionStatus.ERROR
                self._status_message = "pyserial library is not available in environment."
                self._last_error = self._status_message
                return False

            self._port = port.strip()
            self._baud_rate = baud_rate or self.default_baud_rate
            self._status = SerialConnectionStatus.CONNECTING
            self._status_message = f"Connecting to {self._port} at {self._baud_rate} baud..."

            try:
                self._serial_conn = serial.Serial(
                    port=self._port,
                    baudrate=self._baud_rate,
                    timeout=1.0,
                    write_timeout=1.0,
                )
                # Flush input buffers
                self._serial_conn.reset_input_buffer()

                self._stop_event.clear()
                self._reader_thread = threading.Thread(
                    target=self._reader_loop,
                    name=f"SerialReader-{self._port}",
                    daemon=True,
                )
                self._reader_thread.start()

                self._status = SerialConnectionStatus.CONNECTED
                self._status_message = f"Connected to {self._port} at {self._baud_rate} baud."
                self._last_error = None
                logger.info(f"Connected to {self._port} at {self._baud_rate} baud.")
                return True

            except Exception as e:
                self._status = SerialConnectionStatus.ERROR
                self._status_message = f"Failed to connect to {self._port}: {str(e)}"
                self._last_error = str(e)
                if self._serial_conn and self._serial_conn.is_open:
                    try:
                        self._serial_conn.close()
                    except Exception:
                        pass
                self._serial_conn = None
                logger.error(f"Serial connection error: {e}")
                return False

    def disconnect(self) -> None:
        """
        Gracefully terminates background reading thread and releases serial port resources.
        """
        with self._lock:
            self._stop_event.set()

            # Close serial port handle to unblock any pending readline()
            if self._serial_conn is not None:
                try:
                    if hasattr(self._serial_conn, "is_open") and self._serial_conn.is_open:
                        self._serial_conn.close()
                except Exception as e:
                    logger.debug(f"Exception during serial close: {e}")
                finally:
                    self._serial_conn = None

            # Join reader thread
            if self._reader_thread and self._reader_thread.is_alive():
                # Avoid joining if current thread is the reader thread
                if threading.current_thread() != self._reader_thread:
                    self._reader_thread.join(timeout=1.5)
            self._reader_thread = None
            self._mock_connected = False

            self._status = SerialConnectionStatus.DISCONNECTED
            self._status_message = "Serial port disconnected."
            logger.info("Serial receiver disconnected.")

    # -------------------------------------------------------------------------
    # Background Reading Loop
    # -------------------------------------------------------------------------

    def _reader_loop(self) -> None:
        """
        Runs in background thread: continuously reads lines, validates JSON,
        and atomically updates latest reading.
        """
        logger.debug(f"Serial reader loop started for {self._port}.")
        while not self._stop_event.is_set():
            try:
                conn = self._serial_conn
                if conn is None or not getattr(conn, "is_open", False):
                    break

                # Read line with timeout
                line_bytes = conn.readline()
                if not line_bytes:
                    continue  # Timeout occurred, loop back to check stop_event

                raw_line = line_bytes.decode("utf-8", errors="replace").strip()
                if not raw_line:
                    continue

                self.process_incoming_line(raw_line)

            except (serial.SerialException, OSError) as e:
                # Handle USB unplug or hardware disconnection
                if not self._stop_event.is_set():
                    logger.warning(f"Hardware serial disconnection detected: {e}")
                    with self._lock:
                        self._status = SerialConnectionStatus.ERROR
                        self._status_message = f"USB hardware disconnected: {str(e)}"
                        self._last_error = str(e)
                break

            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"Unexpected error in serial read loop: {e}")
                    with self._lock:
                        self._errors_count += 1
                        self._last_error = str(e)
                time.sleep(0.1)

        # Cleanup if exited loop unexpectedly
        with self._lock:
            if self._serial_conn:
                try:
                    self._serial_conn.close()
                except Exception:
                    pass
                self._serial_conn = None
            if self._status == SerialConnectionStatus.CONNECTED:
                self._status = SerialConnectionStatus.DISCONNECTED
                self._status_message = "Serial connection terminated."

    # -------------------------------------------------------------------------
    # Data Processing & Validation
    # -------------------------------------------------------------------------

    def process_incoming_line(self, raw_line: str) -> Optional[ESP32ParsedData]:
        """
        Parses and validates a single raw JSON string line from ESP32.
        Thread-safe: updates counters and latest reading.
        """
        self._last_message_raw = raw_line
        parsed_data = self.parse_and_validate_message(raw_line)

        with self._lock:
            if parsed_data is not None:
                self._latest_reading = parsed_data
                self._last_message_time = time.time()
                self._messages_received += 1
                self._last_error = None

                # Fire callback if registered
                if self.on_reading_callback:
                    try:
                        self.on_reading_callback(parsed_data)
                    except Exception as cb_err:
                        logger.error(f"Error in on_reading_callback: {cb_err}")
                return parsed_data
            else:
                self._errors_count += 1
                return None

    @classmethod
    def parse_and_validate_message(cls, raw_text: str) -> Optional[ESP32ParsedData]:
        """
        Validates message structure and data types:
        1. Reject non-string or empty input.
        2. Reject malformed JSON.
        3. Validate message is a dictionary.
        4. Validate numeric fields (type check, reject NaN, Inf, impossible bounds).
        5. Does NOT fabricate missing values.
        6. Keeps gas_raw and noise_raw as uncalibrated raw ADC values.

        Returns ESP32ParsedData on success, None on invalid/malformed data.
        """
        if not raw_text or not isinstance(raw_text, str):
            return None

        clean_text = raw_text.strip()
        if not clean_text or not (clean_text.startswith("{") and clean_text.endswith("}")):
            return None

        try:
            data = json.loads(clean_text)
        except (json.JSONDecodeError, ValueError):
            return None

        if not isinstance(data, dict):
            return None

        # At least one recognized sensor reading or device_id must be present
        recognized_keys = {
            "device_id", "temperature_c", "humidity_pct",
            "pm1_0", "pm2_5", "pm10", "gas_raw", "noise_raw"
        }
        if not recognized_keys.intersection(data.keys()):
            return None

        # Helper to validate numerical fields
        def validate_numeric(
            key: str,
            min_val: Optional[float] = None,
            max_val: Optional[float] = None
        ) -> Tuple[bool, Optional[float]]:
            if key not in data:
                return True, None
            val = data[key]
            if val is None:
                return True, None
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                return False, None
            num = float(val)
            if math.isnan(num) or math.isinf(num):
                return False, None
            if min_val is not None and num < min_val:
                return False, None
            if max_val is not None and num > max_val:
                return False, None
            return True, round(num, 2)

        # Validate temperature: -40°C to 85°C (standard industrial sensor range)
        ok, temp_val = validate_numeric("temperature_c", -40.0, 85.0)
        if not ok:
            return None

        # Validate humidity: 0.0% to 100.0%
        ok, hum_val = validate_numeric("humidity_pct", 0.0, 100.0)
        if not ok:
            return None

        # Validate PM particulate concentrations: >= 0.0, <= 1000.0 µg/m³
        ok, pm1_val = validate_numeric("pm1_0", 0.0, 1000.0)
        if not ok:
            return None

        ok, pm25_val = validate_numeric("pm2_5", 0.0, 1000.0)
        if not ok:
            return None

        ok, pm10_val = validate_numeric("pm10", 0.0, 1000.0)
        if not ok:
            return None

        # Validate raw gas ADC reading: >= 0, <= 65535 (10-bit, 12-bit, or 16-bit ADC)
        # MQ-135 raw sensor output
        ok, gas_raw_val = validate_numeric("gas_raw", 0.0, 65535.0)
        if not ok:
            return None

        # Validate raw microphone ADC reading: >= 0, <= 65535
        ok, noise_raw_val = validate_numeric("noise_raw", 0.0, 65535.0)
        if not ok:
            return None

        # Device ID
        device_id_raw = data.get("device_id")
        if device_id_raw is not None:
            if not isinstance(device_id_raw, str) or not device_id_raw.strip():
                return None
            device_id = str(device_id_raw).strip()
        else:
            device_id = "esp32-unidentified"

        return ESP32ParsedData(
            device_id=device_id,
            temperature_c=temp_val,
            humidity_pct=hum_val,
            gas_raw=gas_raw_val,
            noise_raw=noise_raw_val,
            raw_json=clean_text,
            pm1_0=pm1_val,
            pm2_5=pm25_val,
            pm10=pm10_val,
            timestamp=datetime.now(),
        )

    # -------------------------------------------------------------------------
    # State Inspection & Query APIs
    # -------------------------------------------------------------------------

    def get_latest_reading(self) -> Optional[ESP32ParsedData]:
        """Returns the most recent validated ESP32 telemetry snapshot."""
        with self._lock:
            return self._latest_reading

    def is_connected(self) -> bool:
        """Returns True if the serial port connection is currently open or mock connected."""
        with self._lock:
            if self._mock_connected:
                return True
            return (
                self._status == SerialConnectionStatus.CONNECTED
                and self._serial_conn is not None
                and getattr(self._serial_conn, "is_open", False)
            )

    def is_data_stale(self, timeout_seconds: Optional[float] = None) -> bool:
        """
        Returns True if no valid message has been received within the stale timeout.
        If never received any message, returns True.
        """
        with self._lock:
            if self._last_message_time is None:
                return True
            limit = timeout_seconds if timeout_seconds is not None else self.stale_timeout_seconds
            return (time.time() - self._last_message_time) > limit

    def get_status(self) -> Dict[str, Any]:
        """
        Returns a complete diagnostic status dictionary of the serial receiver.
        """
        with self._lock:
            now = time.time()
            is_conn = self.is_connected()
            stale = self.is_data_stale()

            # Determine composite status
            if not is_conn:
                if self._status == SerialConnectionStatus.ERROR:
                    active_status = SerialConnectionStatus.ERROR
                else:
                    active_status = SerialConnectionStatus.DISCONNECTED
            elif stale:
                active_status = SerialConnectionStatus.STALE
            else:
                active_status = SerialConnectionStatus.CONNECTED

            last_msg_age = (
                round(now - self._last_message_time, 1)
                if self._last_message_time is not None
                else None
            )

            last_ts_str = (
                self._latest_reading.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if self._latest_reading
                else None
            )

            device_id = self._latest_reading.device_id if self._latest_reading else None

            return {
                "status": active_status.value,
                "is_connected": is_conn,
                "is_stale": stale,
                "port": self._port,
                "baud_rate": self._baud_rate,
                "status_message": self._status_message,
                "last_error": self._last_error,
                "messages_received": self._messages_received,
                "errors_count": self._errors_count,
                "last_message_time": last_ts_str,
                "last_message_age_seconds": last_msg_age,
                "last_message_raw": self._last_message_raw,
                "device_id": device_id,
            }

    # -------------------------------------------------------------------------
    # Mock / Testing Hook
    # -------------------------------------------------------------------------

    def feed_mock_message(self, json_str: str, set_connected: bool = True) -> Optional[ESP32ParsedData]:
        """
        Directly injects a simulated serial JSON message for unit tests and offline testing.
        Allows full testing of data validation, mapping, and dashboard integration without physical ESP32.
        """
        if set_connected:
            with self._lock:
                self._mock_connected = True
                self._status = SerialConnectionStatus.CONNECTED
                self._last_message_time = time.time()
                self._port = self._port or "COM3 (Mock)"
        return self.process_incoming_line(json_str)


# -----------------------------------------------------------------------------
# Global Singleton Accessor (Prevents Duplicate Threads on Streamlit Reruns)
# -----------------------------------------------------------------------------

_serial_receiver_instance: Optional[SerialSensorReceiver] = None
_instance_lock = threading.Lock()


def get_serial_receiver(
    default_baud_rate: int = 115200,
    stale_timeout_seconds: float = 5.0,
) -> SerialSensorReceiver:
    """
    Returns the persistent application-wide SerialSensorReceiver singleton.
    Guarantees that Streamlit rerun triggers do NOT create duplicate reader threads.
    """
    global _serial_receiver_instance
    with _instance_lock:
        if _serial_receiver_instance is None:
            _serial_receiver_instance = SerialSensorReceiver(
                default_baud_rate=default_baud_rate,
                stale_timeout_seconds=stale_timeout_seconds,
            )
        return _serial_receiver_instance

