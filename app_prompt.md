# Espress View — Repository-Specific UI Redesign and Production Hardening

## Mission

Redesign the existing Espress View desktop application into a premium, production-ready ESP serial monitoring and firmware flashing tool.

The visual quality should reflect the design discipline of Apple and Google developer tools: precise spacing, elegant typography, excellent visual hierarchy, consistent icons, restrained colour, and predictable interactions.

The application must feel like a cohesive, professionally engineered desktop product—not a generic CustomTkinter utility.

This is an implementation task, not a design proposal.

Work directly in the existing repository. Inspect the current source, implement the redesign, run the available tests, launch the GUI if possible, and correct defects discovered during validation.

## 1. Repository-specific instructions

Repository: https://github.com/untold91/espress_view

Primary GUI file:

`src/espress_view/gui/app.py`

The current implementation contains the main application window, navigation, device discovery controls, Monitor workspace, Flash workspace, firmware partition rows, icon loading, log controls, and window-management methods in a large GUI class.

The current GUI includes methods such as:

- `_build_interface()`
- `_build_monitor_view()`
- `_load_icons()`
- `show_monitor()`
- `show_flash()`
- `add_partition()`
- `remove_partition()`
- `toggle_log()`
- `scan_devices()`
- `flash_program()`
- `_drain_events()`
- `close_application()`

These are the actual starting points identified in the public source. Inspect their current implementations before editing them.

Important: Some repository documentation may not perfectly reflect the current source tree. Treat the checked-out source, actual imports, dependency configuration, tests, and runtime behavior as authoritative. Do not create files based on an assumed architecture.

Before making changes, inspect:

- `src/espress_view/gui/app.py`
- The actual modules imported by the GUI.
- `src/espress_view/`
- `assets/icons/`
- `utils/config.py` or the actual configuration module, if present.
- `utils/paths.py` or the actual asset-path implementation, if present.
- `tests/`
- `pyproject.toml`
- `requirements.txt`
- `CHANGELOG.md`
- Packaging configuration and application entry points.

Resolve discrepancies between documentation and source before deciding which modules to modify.

Do not assume the current public branch contains any local, uncommitted changes.

## 2. Non-negotiable constraints

Preserve:

- Python and CustomTkinter.
- PySerial communication.
- Existing device-discovery and ESP bootloader handshake behavior.
- Existing esptool integration and argument construction.
- Firmware validation.
- Firmware partition addresses and supported partition limits.
- Serial Monitor connection and disconnection.
- The existing exact-text serial transmission behavior, including UTF-8 encoding and no automatically appended newline.
- Log clearing and exporting.
- Real flash progress and abort behavior.
- Existing confirmation when the monitored device must be disconnected before flashing.
- Existing theme and settings behavior, where supported.
- Existing application entry points and packaging compatibility.

Do not migrate to PyQt, PySide, Electron, a browser frontend, or another GUI framework.

Do not replace real hardware functionality with dummy data.

Do not rewrite the flashing backend just to improve the appearance.

Keep the scope focused on the GUI, layout reliability, component organization, and any narrowly necessary integration changes.

## 3. Establish the new visual identity

Create a modern, neutral, dark-first design system with a fully supported light theme.

The design direction is a combination of Apple's visual restraint and Google's consistency, adapted to a compact engineering utility.

Do not copy either product literally.

### Dark palette

Use these as initial semantic tokens:

- Window: `#17191D`
- Sidebar: `#1B1E23`
- Primary surface: `#20242A`
- Secondary surface: `#262B32`
- Primary text: `#F2F4F7`
- Secondary text: `#A6AFBC`
- Muted text: `#7F8997`
- Borders: `#353B44`
- Primary accent: `#6C9EFF`
- Success: `#46B881`
- Warning: `#E9B65A`
- Error: `#F07178`

### Light palette

- Window: `#F5F6F8`
- Sidebar: `#EEF0F3`
- Primary surface: `#FFFFFF`
- Secondary surface: `#FFFFFF`
- Primary text: `#20242A`
- Secondary text: `#5F6875`
- Muted text: `#7B8491`
- Borders: `#DDE1E7`
- Primary accent: `#2867D8`
- Success: `#16845B`
- Warning: `#966400`
- Error: `#C53742`

Use semantic tokens rather than scattering hexadecimal values throughout the GUI.

Check contrast and adjust colours when necessary.

Use one primary accent. Most controls should remain neutral. Use semantic status colours only where they communicate meaningful state.

Avoid gradients, neon colours, excessive shadows, oversized cards, excessive rounded corners, and decorative colour blocks.

### Typography

Use a consistent system font for the interface and a readable monospaced font for terminal output.

Suggested desktop sizes:

- Page title: 22–26 px.
- Section heading: 15–17 px.
- Standard labels and body text: 13–14 px.
- Secondary metadata: 12 px.
- Terminal text: 12–13 px.

Use appropriate font weights and consistent line spacing.

### Spacing

Create reusable spacing constants based on 4 px or 8 px increments.

Maintain consistent outer margins, component gaps, label spacing, control heights, and alignment.

Standard controls should generally be approximately 32–38 px high, subject to platform rendering and content requirements.

Create a centralized theme module or equivalent structure that fits the existing codebase.

## 4. Fix the window-management defects first

This is a critical requirement.

The current GUI explicitly changes window geometry in `show_monitor()`, `show_flash()`, and `toggle_log()`.

The Monitor and Flash navigation methods use different fixed heights, while the log toggle forces additional geometry changes. These operations can interfere with the user's current window dimensions and maximize/restore behavior.

Remove the assumption that switching pages or showing logs should force the window to a particular fixed size.

### Required behavior

- Preserve the current window size when switching between Monitor and Flash whenever the existing layout can accommodate both.
- Preserve the user's maximized state.
- Never accidentally unmaximize a maximized window when switching pages.
- Never force a maximized window back to a hardcoded geometry.
- Do not repeatedly change geometry during routine navigation.
- Show or hide logs through layout changes, not by overwriting the user's window dimensions.
- Keep window resizing smooth and predictable.
- Retain a sensible minimum window size.
- Restore a previously saved window size only when persistence is supported and the saved geometry is valid.
- Avoid placing the restored window off-screen.
- Ensure application shutdown and background activity are handled safely.

Inspect `toggle_log()` carefully. Confirm that row weights and geometry configuration are applied to the correct parent container.

The current code configures a row weight on the root window while the expandable log console is nested inside another frame. Correct the actual layout hierarchy rather than adding more arbitrary row weights.

Do not use repeated resize callbacks to compensate for incorrect geometry management.

## 5. Redesign the application shell

Create a consistent application shell with:

1. A compact left sidebar.
2. A shared device-selection area.
3. A consistent main content header.
4. A flexible workspace.
5. A clearly managed console/log area.
6. Shared status and feedback patterns.

### Sidebar

Keep the existing Monitor and Flash destinations.

Use a compact, refined navigation style with:

- Consistent icons.
- Clear labels.
- A restrained selected state.
- Appropriate hover and focus states.
- Consistent alignment and padding.

Use a stable sidebar width where practical, but ensure it does not consume excessive space at smaller window sizes.

Do not add unnecessary navigation pages.

### Shared device selector

Retain the existing device-discovery workflow.

Present the selected device clearly and provide a nearby Rescan action.

The current display format includes chip type, serial port, and MAC address. Preserve access to this information without letting long values break the layout.

Ensure the selected port is parsed and passed to existing operations correctly.

Do not change the device model or hardware-selection semantics merely to simplify the UI.

Show actual discovery status and handle an empty device list gracefully.

## 6. Redesign the Monitor workspace

Create a polished serial terminal with clear connection controls and a spacious output area.

### Connection toolbar

Include:

- Serial device context.
- Baud-rate selector.
- Connection status.
- Connect or Disconnect action.
- Clear output.
- Export output.

Use consistent labels and compact, accessible controls.

Clearly distinguish connected, disconnected, and failed connection states.

Do not rely on colour alone to communicate status.

### Terminal

Use a readable monospaced font and a restrained terminal surface.

Ensure the terminal expands to use available space.

Support sustained incoming serial data without freezing the GUI.

Preserve the existing background reading and event-queue design.

Batch GUI updates when appropriate to prevent excessive widget operations during high-throughput serial traffic.

Retain the current output-clearing and export behavior.

If automatic scrolling is introduced, make it behave predictably and do not repeatedly pull the user away from manually inspected output.

### Command input

Preserve the existing serial input field and Send action.

Keep Enter-key handling.

Preserve the exact transmission semantics: send the entered text without automatically adding a newline.

Provide appropriate disabled states when disconnected.

Do not change encoding or transmission behavior without a demonstrated requirement.

## 7. Redesign the Flash workspace

Make the firmware workflow clear, organized, and efficient.

Use the following hierarchy:

1. Firmware configuration.
2. Flash settings.
3. Primary flashing action.
4. Progress and current status.
5. Console output.

### Firmware configuration

Preserve the current supported maximum of five firmware partitions, or use the actual configured limit if it has changed in the checked-out source.

Each row must clearly align:

- Partition number.
- Firmware path.
- Browse action.
- Flash address.
- Remove action, when permitted.

Maintain the permanent first-row behavior if it is part of the existing implementation.

Ensure Add Partition and Remove Partition update rows correctly without breaking alignment.

Use the available width efficiently. File paths should truncate gracefully without expanding the entire layout.

Retain native file selection and existing `.bin` support.

Keep address validation and flashing argument construction in the existing appropriate backend modules.

Do not silently change user-specified addresses.

### Flash controls

Clearly display the flash baud rate and primary Flash Program action.

Use the existing default value unless there is a demonstrated reason to change it.

Validate before starting.

Prevent duplicate operations.

Keep incompatible controls disabled while flashing.

### Progress

Use the existing progress events.

Display actual progress when available.

Show a suitable running state when the percentage is unknown.

Never invent progress or claim success before receiving a successful result.

Distinguish completed, failed, and aborted operations.

Retain the existing abort behavior and make it clear when abort is unavailable.

### Console

Create a well-designed terminal-style log panel.

Use a monospaced font, consistent padding, restrained colours, and readable status information.

The console should expand and contract through the layout manager.

The log expand/collapse control must not force a fixed window size.

Preserve log clearing and exporting.

Long lines must not expand the entire window horizontally.

## 8. Fix the icon system

Inspect the actual assets in `assets/icons/` before choosing replacements.

The current `_load_icons()` implementation recolours icons white and uses the same image for both light and dark appearance modes. This can make icons difficult to see in light mode.

The existing mapping also assigns an inbox icon to the save action, which is semantically inappropriate.

Correct the icon system.

Requirements:

- Use one coherent outline icon family.
- Prefer a lightweight Lucide-style design language.
- Use appropriate icons for monitor, flash, refresh, clear, save/export, abort, browse, remove, and navigation.
- Keep consistent stroke weight and optical alignment.
- Use suitable sizes for navigation and toolbar actions.
- Use theme-aware rendering.
- Maintain transparency and correct scaling.
- Provide tooltips for icon-only controls.
- Ensure important actions remain accessible through meaningful labels.
- Bundle assets locally so the application works offline.
- Avoid emoji and arbitrary Unicode symbols as icons.
- Do not assume CustomTkinter can render SVG directly.
- Do not introduce a large dependency solely for a few icons if local assets are sufficient.

If existing assets are unsuitable, replace them with a consistent, properly licensed icon set and update packaging/resource handling accordingly.

Verify that all icon assets resolve correctly both in development and in a packaged application.

## 9. Improve the code organization incrementally

The main GUI currently contains a substantial amount of UI construction and behavior in one class.

Refactor only as much as necessary to make the redesigned application maintainable.

A reasonable target is to separate responsibilities into:

- A centralized theme/design system.
- Shared UI components.
- A Monitor workspace component.
- A Flash workspace component.
- A shared device selector or header component.

Use the existing module structure and naming conventions where practical.

Do not create unnecessary abstractions.

Do not move hardware behavior into visual widgets.

Do not duplicate connection state across components.

Keep the existing event queue and backend interfaces intact.

Avoid unrelated backend rewrites.

If introducing new modules, update imports, tests, package discovery, and asset paths as necessary.

## 10. Responsive layout rules

Use appropriate `grid()` or `pack()` layout behavior with correct parent-level weights and `sticky` settings.

Do not mix geometry managers within the same parent.

Avoid using `place()` with absolute coordinates for the primary layout.

Avoid fixed child widths when the controls should adapt to available space.

Keep the sidebar, header, toolbar, terminal, firmware rows, and console aligned.

Make sure all relevant parent containers have the correct row and column weights.

Do not set row weights on the wrong container.

Ensure content areas expand while controls maintain usable dimensions.

At reduced window sizes:

- Preserve access to essential controls.
- Keep text readable.
- Allow suitable scrolling where necessary.
- Avoid overlapping widgets.
- Avoid clipping buttons and labels.
- Avoid shrinking the interface indiscriminately.

Test at:

- 1280 × 720.
- 1366 × 768.
- 1600 × 900.
- 1920 × 1080.
- A restored window around 1000 × 650, where feasible.

Test Windows scaling at 100%, 125%, and 150% when the environment permits.

Use the installed CustomTkinter DPI behavior correctly. Do not layer competing scaling mechanisms.

## 11. Thread safety and operational correctness

Preserve the principle that Tk widgets and Tk variables are only accessed on the GUI thread.

Keep serial reads, discovery handshakes, and flashing work off the main event loop.

Continue using the existing thread-safe queue/event architecture unless a narrowly justified improvement is required.

Ensure the queue-draining callback is scheduled safely.

Avoid excessive UI callbacks and unbounded log-widget growth during sustained output.

Prevent duplicate discovery workers and duplicate flash operations where appropriate.

Ensure disconnection and application shutdown release resources safely.

If a backend error occurs, report it through the existing event mechanism.

Do not silently swallow exceptions.

Do not update Tk widgets directly from worker threads.

Do not introduce animations that compromise responsiveness.

## 12. Theme and component consistency

Ensure both themes use the same design rules.

Audit:

- Navigation.
- Buttons.
- Option menus.
- Text entries.
- Firmware rows.
- Terminal surfaces.
- Progress indicators.
- Status labels.
- Tooltips.
- Dialogs.
- Disabled controls.
- Error and warning states.

Avoid hardcoded one-off colours in methods such as `show_monitor()`, `show_flash()`, and `disconnect_monitor()`.

Use shared component variants and semantic tokens.

Ensure changing themes updates every relevant widget and icon consistently.

Correct visible text inconsistencies and typographical errors encountered during the redesign without changing technical terminology or user-facing behavior unnecessarily.

## 13. Testing and acceptance

Inspect existing tests and the actual package configuration before making changes.

Run the existing test suite:

`python -m unittest discover -s tests`

Run any additional checks supported by the repository.

Add focused tests for newly introduced logic and layout state where practical.

Verify:

- Application startup.
- Monitor/Flash navigation.
- Maximize and restore.
- Window resizing.
- Log expansion and collapse.
- Light and dark themes.
- Device selection and refresh.
- Monitor connection and disconnection.
- Serial output and command transmission.
- Firmware row addition and removal.
- Invalid firmware configuration.
- Flash progress and abort behavior.
- Log clearing and exporting.
- Application shutdown.
- Asset loading and packaging compatibility.

Use mocks for hardware-dependent tests where necessary.

Do not perform real flashing as part of ordinary automated tests.

If the GUI cannot be launched in the available environment, report that limitation honestly and still execute the applicable tests.

Do not claim that a visual or hardware test passed unless it was actually performed.

## 14. Execution strategy

Work in this order:

Phase A: Inspect the current code, dependencies, tests, and assets.

Phase B: Identify the exact layout and geometry defects.

Phase C: Implement the centralized design system and icon system.

Phase D: Correct the application shell and window lifecycle.

Phase E: Redesign Monitor and Flash using shared components.

Phase F: Test responsive behavior, theme consistency, and existing hardware workflows.

Phase G: Run tests, fix regressions, and review packaging.

Make changes incrementally and keep the application runnable.

Do not stop after presenting a plan. Proceed with implementation.

Do not wait for approval for ordinary design decisions.

Before finishing, provide a concise report of modified files, design changes, behavior preserved, tests actually run, test results, and any unresolved limitations.

## Definition of done

The redesign is complete when:

- The interface has a cohesive professional identity.
- Light and dark themes are both polished.
- Icons are consistent, meaningful, and readable.
- Switching between Monitor and Flash does not reset window geometry.
- Maximizing and restoring the window work predictably.
- The terminal and firmware workspace resize correctly.
- No essential controls overlap or disappear at supported sizes.
- All existing serial and flashing workflows remain functional.
- The UI remains responsive during background work.
- The available automated tests pass.
- Remaining limitations are documented honestly.

Begin by inspecting the checked-out repository and identifying the concrete changes needed. Then implement and validate the redesign directly in the current codebase.