# Changelog

All notable changes to this project will be documented in this file.

## [2026.6.0] - 2026-06-25

### ⚠️ Breaking change - integration domain renamed

The Home Assistant **domain** changed from `toshiba_ac` to **`toshiba_ac_community`**. This was required to be accepted into the default HACS catalog - two default integrations cannot share a domain, and the original [h4de5/home-assistant-toshiba_ac](https://github.com/h4de5/home-assistant-toshiba_ac) already ships `toshiba_ac` (see [hacs/default#7350](https://github.com/hacs/default/pull/7350)).

Home Assistant has no automatic way to move a configured integration to a new domain, so **existing users must remove and re-add the integration once** after updating. Your Toshiba account credentials need to be entered again.

> ⚠️ **Important:** deleting the old config entry does **not** delete its entities - they stay behind as *unavailable* and keep holding their entity IDs (e.g. `climate.living_room`). If you re-add the integration without clearing them first, the new entities collide and come back with a `_2` suffix, breaking automations, dashboards, and energy history. Follow the steps below to avoid that.

**Migration - standard (UI only, works for everyone):**

This reclaims your original **entity IDs** (no `_2`), so automations, dashboards, and long-term energy statistics keep working. Your **devices** are recreated fresh, so any per-device *area* or *name* customisation must be reapplied afterwards.

1. Update to **2026.6.0** in HACS, then **restart Home Assistant**. The old entry will show as *not loaded* ("integration not found") - this is expected.
2. **Settings -> Devices & Services** -> open the old **Toshiba AC (Community)** entry -> **delete it**.
3. **Settings -> Devices & Services -> Entities** tab -> filter **Status: Unavailable** -> identify the leftover Toshiba entities by their names (your AC names, e.g. *Living Room*) and **delete them**. This frees the entity IDs. (Their entity IDs may not contain "toshiba", so filter by status rather than searching.)
4. **Restart Home Assistant**.
5. **Add integration -> Toshiba AC (Community)** -> enter your Toshiba credentials. Your entities return with their original IDs.
6. (Optional) Reapply any area/name customisation on the new devices; the old, now-hidden devices can be ignored.

**Migration - advanced (preserves devices too, requires file access):**

If you also want to keep your **devices** (area, name, and device-level history) intact, rewrite the registry so the existing rows adopt the new domain instead of being recreated. **Take a full backup first.**

1. Update to **2026.6.0**, restart, then delete the old config entry (step 2 above). Do **not** delete the entities.
2. Make a full backup, then **stop Home Assistant Core** (e.g. `ha core stop` over SSH, or stop the container).
3. In `.storage/core.entity_registry`, replace every `toshiba_ac"` with `toshiba_ac_community"` (the trailing quote matters - it targets the old `"platform":"toshiba_ac"` values without touching already-renamed ones).
4. In `.storage/core.device_registry`, do the same replacement in the Toshiba device `identifiers` tuples (`["toshiba_ac", …]` -> `["toshiba_ac_community", …]`).
5. **Start Home Assistant**, then **Add integration -> Toshiba AC (Community)** and enter your credentials. Entities **and** devices reclaim their original identities with full history preserved.

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
