"""Serial-port operations used by the Monitor workspace."""

import serial


def connect(port: str, baud_rate: int) -> serial.Serial:
    """Open a serial port for monitoring."""
    return serial.Serial(port=port, baudrate=baud_rate, timeout=0.2)


def read(connection: serial.Serial) -> bytes:
    """Read currently available bytes, waiting briefly when the port is idle."""
    return connection.read(connection.in_waiting or 1)


def send(connection: serial.Serial, message: str) -> None:
    """Send the exact UTF-8 message without adding line endings."""
    connection.write(message.encode("utf-8"))
