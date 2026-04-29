# Changelog

All notable changes to this project will be documented in this file.

## [2026.4.1] - 2026-04-23

### Fixed

- **Startup failures after HA restart**: Always fetch a fresh SAS token on startup instead of reusing a potentially expired stored token. This was the primary cause of `Credentials invalid` errors after HA restarts.
- **Platform setup timeout (60s deadline)**: Devices are now pre-fetched in `async_setup_entry` before forwarding to platforms. Previously each platform (climate, select, sensor, switch) attempted to fetch devices independently, risking a timeout.
- **WAF 403 misclassified as auth failure**: HTTP 403 responses from the Azure Application Gateway (rate-limiting at startup) are no longer treated as `ConfigEntryAuthFailed`. They now correctly raise `ConfigEntryNotReady` so HA retries automatically.
- **Startup congestion**: Added a 2-second delay before the first API call to avoid hitting the Toshiba cloud API simultaneously with other integrations starting up.

### Added

- **Event-driven disconnect detection**: Reacts immediately to Azure IoT Hub disconnects via `on_connection_state_change` callback instead of waiting up to 5 minutes for a health-check poll.
- **Backoff reconnect schedule**: Reconnect attempts now use a 10s -> 60s -> 300s backoff instead of flat 5-minute retries.
- **SAS token cleared on reconnect**: On reconnection attempts, the cached SAS token is explicitly cleared so a fresh one is always fetched.

## [2026.1.0] - 2026-01-22

Latest release from upstream `h4de5/home-assistant-toshiba_ac`.

See [upstream releases](https://github.com/h4de5/home-assistant-toshiba_ac/releases) for full history.
