# Changelog

All notable changes to this project will be documented in this file.

## [2026.9.0] - 2026-07-10

### Added - Indoor temperature sensor

New **Indoor temperature** sensor entity per AC, exposing the room temperature measured by the unit as a standalone sensor (requested in [discussion #20](https://github.com/vmvelev/home-assistant-toshiba_ac/discussions/20)). The value was previously only accessible as the `current_temperature` attribute of the climate entity; a dedicated sensor makes it directly usable on dashboard cards, in history graphs and in automations. Existing outdoor temperature sensors are unchanged.

## [2026.8.0] - 2026-07-10

### Added - Wireless LED switch

New **Wireless LED** switch entity (in the Configuration section of the device page) controlling the unit's wireless/status LED - the same control as "Wireless LED" in the official Toshiba app. Unlike the other switches, it stays available while the AC is off.

Requires protocol library **`toshiba-ac-community` 0.5.0**, which adds Wireless LED state and control support. The LED maps to a previously unmapped byte of the AC state protocol (`0x01` = on, `0x02` = off), discovered by diffing state pushes while toggling the LED in the official app, and verified end-to-end on real hardware.

**Note:** the Toshiba cloud only starts reporting the LED state after it has been changed at least once. If the switch does not appear for your unit, toggle "Wireless LED" once in the official Toshiba app, then reload the integration.

## [2026.7.0] - 2026-07-09

### Changed - protocol library now maintained in this project's own fork

The integration now depends on **`toshiba-ac-community`** (0.4.1) instead of upstream `toshiba-ac`. This is a fork of [KaSroka/Toshiba-AC-control](https://github.com/KaSroka/Toshiba-AC-control) maintained at [vmvelev/Toshiba-AC-control](https://github.com/vmvelev/Toshiba-AC-control), so library-level fixes (HTTP/AMQP behaviour) can ship without waiting on upstream.

Library `0.4.1` is upstream `toshiba-ac` 0.3.13 plus packaging modernization (versioneer replaced with `setuptools-scm`) and one log-noise fix: transient Toshiba WAF `403` rate-limit responses (already retried internally, and covered by AMQP push) are now logged at `INFO`/`WARNING` instead of `WARNING`/`ERROR`, so they no longer spam the Home Assistant log. The Python import name is unchanged (`toshiba_ac`).

## [2026.6.0] - 2026-06-25

### ⚠️ Breaking change - integration domain renamed

The Home Assistant **domain** changed from `toshiba_ac` to **`toshiba_ac_community`**. This was required to be accepted into the default HACS catalog - two default integrations cannot share a domain, and the original [h4de5/home-assistant-toshiba_ac](https://github.com/h4de5/home-assistant-toshiba_ac) already ships `toshiba_ac` (see [hacs/default#7350](https://github.com/hacs/default/pull/7350)).

Home Assistant has no automatic way to move a configured integration to a new domain, so **existing users must remove and re-add the integration once** after updating. Your Toshiba account credentials need to be entered again.

> ⚠️ **Important - the UI cannot preserve your entity IDs.** When you delete the old config entry, its entities stay behind in the registry still holding their IDs (e.g. `climate.living_room`). But once the old integration is gone, Home Assistant **hides those leftover entities from the Entities UI**, so you cannot delete them there to free the IDs. A UI-only re-add therefore comes back with new IDs (a `_2` suffix). Pick the path below that matches whether you need to keep your IDs/devices/history.

**Option A - UI only (simplest, but you get NEW entities):**

No file access needed, but your **original entity IDs, devices, and history are not kept** - you'll have to point automations/dashboards at the new IDs, and energy statistics restart.

1. Update to **2026.6.0** in HACS, then **restart Home Assistant**. (HACS may leave the old `toshiba_ac` folder behind, so the old entry can keep working instead of showing as *not loaded* - that's fine.)
2. **Settings -> Devices & Services** -> open the old **Toshiba AC (Community)** entry -> **delete it**.
3. **Add integration -> Toshiba AC (Community)** -> enter your Toshiba credentials. The new entities come back with a `_2` suffix (the old IDs are still silently held). Update your automations and dashboards to the new IDs.

**Option B - registry edit (preserves entity IDs, devices, and history; requires file access):**

Rewrite the registry so your existing rows adopt the new domain and are reclaimed on re-add. This is the **only** way to keep your IDs, devices, areas, and history. **Take a full backup first.**

1. Update to **2026.6.0** in HACS, restart, then delete the old config entry. (Leave the entities alone.)
2. Make a full backup, then **stop Home Assistant Core** (e.g. `ha core stop` over SSH, or stop the container).
3. In `.storage/core.entity_registry`, replace every `toshiba_ac"` with `toshiba_ac_community"` (the trailing quote matters - it targets the old `"platform":"toshiba_ac"` values without touching already-renamed ones).
4. In `.storage/core.device_registry`, do the same replacement in the Toshiba device `identifiers` tuples (`["toshiba_ac", …]` -> `["toshiba_ac_community", …]`).
5. Delete the leftover `custom_components/toshiba_ac` folder if HACS left it behind.
6. **Start Home Assistant**, then **Add integration -> Toshiba AC (Community)** and enter your credentials. Entities **and** devices reclaim their original identities with full history preserved.

> The `reconnect` service is now `toshiba_ac_community.reconnect` (was `toshiba_ac.reconnect`). Update any automations/scripts that call it.

Nothing else changed in this release - the underlying `toshiba-ac` library and all HA-layer reliability fixes are identical to 2026.5.5.

## [2026.5.5] - 2026-05-17

### Changed

- **HACS / UI name**: Renamed to **Toshiba AC (Community)** in `hacs.json` and `manifest.json` so it can coexist in HACS alongside [h4de5/home-assistant-toshiba_ac](https://github.com/h4de5/home-assistant-toshiba_ac) (**Toshiba AC**) without replacing the original listing.

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
