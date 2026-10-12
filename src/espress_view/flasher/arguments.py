"""Validation and argument construction for firmware programming."""

from pathlib import Path


def build_flash_arguments(
    port: str,
    baud_rate: str,
    partitions: list[tuple[str, str]],
) -> list[str]:
    """Validate firmware rows and build the corresponding esptool arguments."""
    arguments = ["--chip", "auto", "--port", port, "--baud", baud_rate, "write-flash"]
    for file_path, address_text in partitions:
        try:
            address = int(address_text, 0)
        except ValueError as error:
            raise ValueError(f"Invalid flash address: {address_text}") from error
        binary = Path(file_path)
        if not binary.is_file():
            raise ValueError(f"Firmware file not found: {binary}")
        arguments.extend([f"0x{address:x}", str(binary)])
    return arguments
