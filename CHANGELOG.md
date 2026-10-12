# Changelog

All notable changes to Espress View are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A theme-aware outline icon system, semantic light/dark design tokens, and persistent appearance and window-size preferences.
- Bounded, batched terminal output with scroll-position preservation and clearer discovery, connection, and flash statuses.

### Changed

- Redesigned the Monitor and Flash workspaces with a responsive shared shell and consistent device selection.
- Workspace navigation and flash-log expansion now preserve the current window size and maximized state.

## [0.4.0] - 2026-09-03

### Added

- Serial Monitor workspace with an independent baud rate, connection controls, exact-text sending, and retained serial logs.
- Shared device discovery and Monitor/Flash sidebar navigation.
- Flash progress reporting, abort control, persistent logs, icon controls, and tooltips.
- Safe terminal `Ctrl+C` shutdown and packaged esptool worker support.
- A `2000000` default Flash baud rate and `115200` default Monitor baud rate.

## [0.1.0] - Initial release

### Added

- Initial release of `espress_view`.
