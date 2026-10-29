# Changelog

All notable changes to this project will be documented in this file.

## [2026.8.4] - 2026-08-29

This release bundles protocol library **`toshiba-ac-community` 0.7.2**.

### Added - reauthentication flow

When your stored credentials stop working (for example after a password change), Home Assistant now prompts for the new password instead of failing silently until you delete and re-add the integration ([#42](https://github.com/vmvelev/home-assistant-toshiba_ac/pull/42) by [@lackas](https://github.com/lackas)).

### Fixed

- The device registry showed an internal account-derived id as the device model; it now shows the real model id, e.g. "Model 3" ([#41](https://github.com/vmvelev/home-assistant-toshiba_ac/pull/41) by [@lackas](https://github.com/lackas), closing the last part of [#4](https://github.com/vmvelev/home-assistant-toshiba_ac/issues/4)).
- The same Toshiba account could be added twice, producing duplicate devices ([#43](https://github.com/vmvelev/home-assistant-toshiba_ac/pull/43) by [@lackas](https://github.com/lackas)).
- Library 0.7.2: a wrong password is no longer retried. Previously three rapid login attempts counted toward Toshiba's account lockout.

## [2026.8.3] - 2026-08-20

This release bundles protocol library **`toshiba-ac-community` 0.7.1**.

### Added - self-cleaning is now visible

Units that support self-cleaning get a new **Self cleaning** binary sensor, on while the unit runs its post-operation clean cycle (typically ~30 minutes of fan drying after you turn the AC off). Previously the cycle was only visible as the climate entity's "cleaning" preset, which was easy to miss.

The climate entity now also shows the unit as **off** during self-cleaning, matching the Toshiba app, instead of appearing stuck on in its last mode. Selecting a mode while cleaning powers the unit back on, which aborts the cycle - same as the app.

### Fixed - full 5-16 °C range in 8 °C mode on model 3 units

In 8 °C frost-protection mode the target temperature was capped at 13 °C for all units, but model 3 units (e.g. Shorai Edge) genuinely accept 5-16 °C ([#35](https://github.com/vmvelev/home-assistant-toshiba_ac/issues/35), reported by [@ThomasRobertFr](https://github.com/ThomasRobertFr)). The ceiling is now per-model: 16 °C on model 3, 13 °C otherwise. Verified on the reporter's Shorai Edge data and live on three additional model 3 units.

### Changed - diagnostics include model identification

The diagnostics download now includes each unit's `merit_feature` and `ac_model_id` - the exact data device-support investigations keep asking reporters to dig out of debug logs.

## [2026.8.2] - 2026-08-15

### Fixed - adding the integration works again

2026.8.1 broke the config flow: every login attempt during setup ended in "Unexpected error", even with correct credentials ([Toshiba-AC-control#13](https://github.com/vmvelev/Toshiba-AC-control/issues/13), reported by [@AndreasKzk](https://github.com/AndreasKzk)). The access token introduced in 2026.8.1 was read from the connection object *after* it had already been torn down, which crashed validation right after a successful login. Existing entries were unaffected - only new setups and re-adds failed. The token is now captured before teardown, and a regression test covers the flow.

Because each failed attempt still performed a real login on Toshiba's side, repeated retries could bring an account close to lockout - if you saw "attempts remaining before account lockout", wait an hour before trying again with this version.

## [2026.8.1] - 2026-08-14

This release bundles protocol library **`toshiba-ac-community` 0.7.0**.

### Fixed - energy consumption polling works again

Toshiba's WAF rejects the browser-like User-Agent the library used to send, answering HTTP 403 on the energy endpoint (and recently on state reads too), which left energy sensors at `unknown`. The library no longer sends it. Devices without metering are now also skipped individually instead of aborting the readings of every unit in the account. Contributed by [@Biohospitalix](https://github.com/Biohospitalix) in [Toshiba-AC-control#6](https://github.com/vmvelev/Toshiba-AC-control/pull/6).

### Fixed - unrecognised swing values no longer break entities (2026 Shorai Curve)

2026 Shorai Curve units report vertical and horizontal vane positions combined in one new byte range, which the library decoded with a bare table lookup - one unrecognised value raised `KeyError`, broke command handling, and could leave the entity unavailable until a known value was reported again ([#32](https://github.com/vmvelev/home-assistant-toshiba_ac/issues/32), [Toshiba-AC-control#2](https://github.com/vmvelev/Toshiba-AC-control/issues/2)). The new encoding is now decoded onto the existing swing modes, and any future unknown value degrades to a logged warning instead of a crash. Independent per-axis swing control remains tracked in the library issue. Thanks to [@devcide](https://github.com/devcide) for the protocol reverse engineering and to [@harmpert](https://github.com/harmpert) and [@simontaen](https://github.com/simontaen) for detailed reports.

### Fixed - fractional target temperatures are applied instead of silently dropped

Home Assistant sends temperatures as floats, and external thermostats produce half-degree targets such as 22.5; the library only accepted whole numbers and raised `KeyError`, so such setpoints never reached the unit. Fractional values now round to the nearest whole degree (half up). Contributed by [@neoKushan](https://github.com/neoKushan) in [Toshiba-AC-control#10](https://github.com/vmvelev/Toshiba-AC-control/pull/10).

### Changed - login is skipped on restart by reusing the cached access token

The long-lived access token is now stored in the config entry and reused, so `/api/Consumer/Login` - the most aggressively rate-limited endpoint on Toshiba's API - is only called on first setup or when the token expires ([Toshiba-AC-control#8](https://github.com/vmvelev/Toshiba-AC-control/issues/8)). HTTP 429 responses are also classified as rate limits and retried with the slow backoff policy instead of three rapid attempts ([Toshiba-AC-control#4](https://github.com/vmvelev/Toshiba-AC-control/issues/4), reported by [@KohleIT2023](https://github.com/KohleIT2023)).

## [2026.8.0] - 2026-08-01

### Changed - energy consumption is polled hourly instead of every 10 minutes

Protocol library **`toshiba-ac-community` 0.6.3** now reads energy consumption once an hour rather than every 10 minutes. Energy requests drop from 144 to 24 per day per unit, taking the integration's total steady-state requests to Toshiba's cloud from roughly 192 to 72 per day - about a 62% reduction.

Nothing is lost: energy is reported as a year-to-date cumulative total, and Home Assistant aggregates it into hourly statistics, so a 10-minute poll never produced any resolution the energy dashboard could use. The poll stays aligned to the top of each hour, so hourly energy attribution is unchanged, and the first reading is still fetched immediately when the integration starts.

Fewer requests also means less exposure to the rate limiting that has repeatedly broken this integration ([#25](https://github.com/vmvelev/home-assistant-toshiba_ac/issues/25), [#13](https://github.com/vmvelev/home-assistant-toshiba_ac/issues/13)): when a poll was rejected, its retry chain ran longer than the 10-minute interval itself, so a failing poll overlapped the next one and kept the rate limit warm.

### Fixed - energy sensor stuck at `unknown` after startup

The energy sensor now reads any consumption value that was already fetched during setup, instead of waiting for the next one to arrive. The integration begins fetching energy as soon as it discovers your units, which can finish before the sensor is ready to listen - and because the library only reports energy when the total *changes*, an unchanged total on later polls left the sensor at `unknown`. On a unit that was not running, it could stay that way indefinitely.

Contributed by [@Biohospitalix](https://github.com/Biohospitalix) in [#28](https://github.com/vmvelev/home-assistant-toshiba_ac/pull/28).

## [2026.7.7] - 2026-07-21

### Fixed - stable Device-ID for Toshiba API requests

Protocol library **`toshiba-ac-community` 0.6.2** now reuses Home Assistant's persisted per-installation device ID for every HTTP session, matching the official app's stable identity and avoiding repeated HTTP 403 responses when sessions are recreated.

## [2026.7.6] - 2026-07-19

### Fixed - HACS download tracking

HACS now installs a `toshiba_ac_community.zip` release asset, allowing GitHub's asset download counter to track installations and updates. Previous releases were installed from GitHub's automatically generated source archives, whose downloads are not counted; tracking starts with this release.

## [2026.7.5] - 2026-07-18

### Fixed - "429 Too Many Requests" blocking login for all users

Since around 2026-07-17 the Toshiba cloud rejects any login attempt that does not carry a `Device-ID` header with **HTTP 429 Too Many Requests**, so adding, reloading or restarting the integration failed for everyone - while the official app kept working, because it logs in once and reuses its token for years ([#25](https://github.com/vmvelev/home-assistant-toshiba_ac/issues/25), [h4de5#297](https://github.com/h4de5/home-assistant-toshiba_ac/issues/297)). Protocol library **`toshiba-ac-community` 0.6.1** now sends a `Device-ID` header on every request, which restores login. Verified against the live API on real hardware.

Root cause identified by [@Dirkske71](https://github.com/Dirkske71) in [h4de5/home-assistant-toshiba_ac#297](https://github.com/h4de5/home-assistant-toshiba_ac/issues/297#issuecomment-5008015523).

## [2026.7.4] - 2026-07-10

### Fixed - complete brand image set shipped locally

Since the 2026.6.0 domain rename the brands CDN does not know this integration's domain, and [home-assistant/brands no longer accepts custom integration submissions](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api) - so anything that loads images from the CDN shows an "icon not available" placeholder. A base `icon.png` already shipped inside the integration (served locally by Home Assistant 2026.3+ and preferred over the CDN); this release completes the local set with `icon@2x.png`, `logo.png`, and `logo@2x.png`, fixing missing images on high-DPI displays and in logo placements.

**Known limitation:** the image in the **HACS update dialog** cannot be fixed from this repository. Current HACS builds that URL directly against the brands CDN instead of Home Assistant's local brands endpoint, so it 404s for every custom integration added after the brands repository closed to submissions (February 2026). This needs a fix in HACS itself.

## [2026.7.3] - 2026-07-10

### Added - H.DA swing mode

New **H.DA** swing mode, selectable like any other swing mode on units that support fixed swing positions (e.g. Daiseikai 10) - the same airflow mode as "H.DA" on the remote. Contributed at the library level by [@Madalinbv](https://github.com/Madalinbv) in [Toshiba-AC-control#1](https://github.com/vmvelev/Toshiba-AC-control/pull/1), following up on [#15](https://github.com/vmvelev/home-assistant-toshiba_ac/pull/15).

Requires protocol library **`toshiba-ac-community` 0.6.0**, which also fixes a state-parsing crash (`KeyError`) when a unit reported H.DA already engaged via the IR remote or the official app.

### Changed - available in the default HACS catalog

The integration is now part of the default HACS store ([hacs/default#7350](https://github.com/hacs/default/pull/7350)) - no custom repository needed, just search for **Toshiba AC (Community)** in HACS. Existing installs added as a custom repository keep working and updating as before.

## [2026.7.2] - 2026-07-10

### Added - Indoor temperature sensor

New **Indoor temperature** sensor entity per AC, exposing the room temperature measured by the unit as a standalone sensor (requested in [discussion #20](https://github.com/vmvelev/home-assistant-toshiba_ac/discussions/20)). The value was previously only accessible as the `current_temperature` attribute of the climate entity; a dedicated sensor makes it directly usable on dashboard cards, in history graphs and in automations. Existing outdoor temperature sensors are unchanged.

## [2026.7.1] - 2026-07-10

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
