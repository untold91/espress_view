# User Manual

## Start the application

Install the package in a virtual environment and run:

```sh
python -m espress_view
```

Monitor is the default workspace. Use the sidebar to switch to Flash.

## Discover and select a device

1. Connect and power the ESP device. It must be able to respond to an esptool ROM bootloader handshake.
2. Espress View scans serial ports automatically when it opens.
3. Select the device from the shared Device Discovery list. Entries show `Chip Type | COM ID | MAC Address`.
4. Use **Rescan** after connecting, disconnecting, or resetting hardware.

Ports that do not respond to `read-mac` are not listed. Discovery may briefly open each port, so close other tools that have an exclusive connection.

## Use the Serial Monitor

1. Select a discovered device.
2. Choose the Monitor baud rate. Its default is `115200`; it is independent of the Flash baud rate.
3. Select **Connect**. Received serial bytes are decoded as UTF-8 (invalid sequences are replaced) and appended to the console.
4. Type into the input and choose **Send** or press Enter. The entered string is sent as UTF-8 exactly as written—no LF or CR newline is added.
5. Select **Disconnect** before another application needs that port or before flashing.

The Monitor console's clear control erases the visible retained text. Its save/download control exports the current console text to `.log` or `.txt`.

## Flash firmware

1. Switch to **Flash** and select a discovered ESP.
2. In Firmware Layout, browse to the firmware `.bin` file and enter its flash address in hexadecimal (the row defaults to `0x0000`).
3. Add up to four additional image rows if needed. The first row cannot be removed; additional rows can be removed.
4. Choose the Flash baud rate (default `2000000`) and select **Flash Program**.
5. Follow the streamed output and progress. Select Abort to request termination of the worker.

The app accepts `.bin` files. **Direct `.hex` upload is not currently supported**: the picker only accepts `.bin`, and esptool's write-flash command is given binary images and explicit target addresses. Convert Intel HEX to a correctly addressed binary using a trusted tool and the firmware vendor's memory map before flashing; do not assume a HEX file can be renamed to `.bin`.

Only flash images intended for the exact chip/board and at the correct offsets. Incorrect images or addresses can make the device unbootable or overwrite calibration/configuration data. Keep a known recovery image and follow the hardware vendor's flashing instructions.

If Monitor is connected to the same device, the app asks whether to disconnect and proceed. Choose **Disconnect and Proceed** to close Monitor, or **Cancel** to leave it connected. The app blocks flashing another port while Monitor owns a serial connection.

## Logs and progress

The Flash log panel starts collapsed. Expand it to read esptool output; clear and save controls are available while expanded. Save exports the displayed console as `.log` or `.txt`. Progress is derived from percentage lines in esptool's output, so the log and final process status provide additional detail.

## Common problems

| Problem | Things to check |
|---|---|
| Device is not listed | Power, USB data cable, USB-to-UART driver, correct port, boot/download mode; select Rescan |
| Permission denied | Close other serial tools; on Linux check device-node/group permissions such as `dialout`/`uucp` |
| Port busy | Disconnect Monitor and close terminal, IDE, or vendor tools that may hold the port |
| Handshake timeout | Confirm boot/reset wiring and device download mode; try a lower Flash baud rate |
| Invalid address | Enter a valid integer address such as `0x1000`; check the board's partition map |
| Firmware not found | Re-select an existing `.bin` file; check removable/network drive availability |
| Flash abort/failure | Treat flash as incomplete; reconnect/reset and flash the complete, correct image again |

For more detail, see Espressif's [esptool troubleshooting guide](https://docs.espressif.com/projects/esptool/en/latest/troubleshooting.html).
