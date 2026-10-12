# Contributing to Espress View

Thanks for helping improve Espress View. Changes should keep the GUI responsive, make serial/flash errors visible, and preserve a strict boundary between the UI and backend.

## Development setup

Use Python 3.10 or later. From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -r scripts/requirements.txt
```

On macOS or Linux, create the environment with `python3 -m venv .venv` and activate it with `source .venv/bin/activate`.

Launch the app with `python -m espress_view`. Run tests with `python -m unittest discover -s tests`. Build the executable with `python scripts/build.py build`.

## Code style and design

- Follow PEP 8; use descriptive names, focused functions, and type annotations for public/internal interfaces where useful.
- Keep Tk and CustomTkinter widget operations on the main thread. Pass worker results through a thread-safe `queue.Queue`; poll it with `CTk.after()`.
- **No Tkinter/CustomTkinter imports inside `core/` or `flasher/`.** Keep these packages UI-independent. Report backend outcomes through return values, exceptions, callbacks, or thread-safe messages—not widget references.
- Keep firmware programming delegated to `esptool`; do not duplicate chip-specific bootloader protocol implementations without a separate, reviewed requirement.
- Add or update tests for backend behavior and user-visible changes. Document behavior and limitations accurately.
- Keep runtime dependencies in `requirements.txt`; build-only dependencies belong in `scripts/requirements.txt`.

## Pull requests

1. Use a focused branch and keep the change set scoped to one purpose.
2. Explain the problem, the change, and any user-visible behavior in the PR description. Link related issues.
3. Include tests or a clear reason why they cannot be automated. Do not claim physical-device validation unless it was actually performed.
4. Run the unit tests and check the diff for unintended files, generated artifacts, credentials, or machine-specific paths.
5. Update the README or relevant document when setup, supported firmware, packaging, or UI behavior changes.
6. Request review before merging; do not include unrelated formatting or generated build output.

## Reporting serial/firmware bugs

Include the operating system, Python version, device/chip, serial adapter/driver if known, selected baud rate, concise logs, and reproduction steps. Remove MAC addresses, firmware contents, and other sensitive data before posting.
