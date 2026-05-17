# Changelog

All notable changes to this project will be documented in this file.

## [2026.5.4] - 2026-05-17

### Fixed

- **Dependency install failure on HA 2026.5+**: Reordered `manifest.json` requirements so `azure-iot-device==2.15.0rc1` installs before `toshiba-ac==0.3.13`. Home Assistant installs requirements in list order; with `toshiba-ac` first, `uv` refused the pre-release transitive dependency and setup failed (`Requirements for toshiba_ac not found`).

## [2026.5.3] - 2026-05-17

> **Note:** If setup fails after upgrading to 2026.5.3, upgrade to **2026.5.4** or later.

### Changed

- **toshiba-ac 0.3.13**: HTTP API pacing, smarter retries on 403/401, and AMQP handler fixes from [KaSroka/Toshiba-AC-control](https://github.com/KaSroka/Toshiba-AC-control/releases/tag/v0.3.13). HA-layer startup/reconnect fixes in this fork are unchanged.
- **azure-iot-device 2.15.0rc1**: Explicit manifest pin (required for HA to install the library's pre-release MQTT dependency).

### Documentation

- **README**: New [About this fork](https://github.com/vmvelev/home-assistant-toshiba_ac#about-this-fork) section explaining the relationship to [h4de5/home-assistant-toshiba_ac](https://github.com/h4de5/home-assistant-toshiba_ac) and when to use which repository.

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
