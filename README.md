[![HACS Validate](https://github.com/vmvelev/home-assistant-toshiba_ac/actions/workflows/validate.yml/badge.svg)](https://github.com/vmvelev/home-assistant-toshiba_ac/actions/workflows/validate.yml)
[![hassfest Validate](https://github.com/vmvelev/home-assistant-toshiba_ac/actions/workflows/hassfest.yml/badge.svg)](https://github.com/vmvelev/home-assistant-toshiba_ac/actions/workflows/hassfest.yml)
[![Github Release](https://img.shields.io/github/release/vmvelev/home-assistant-toshiba_ac.svg)](https://github.com/vmvelev/home-assistant-toshiba_ac/releases)
[![Github Commit since](https://img.shields.io/github/commits-since/vmvelev/home-assistant-toshiba_ac/latest?sort=semver)](https://github.com/vmvelev/home-assistant-toshiba_ac/releases)
[![Github Open Issues](https://img.shields.io/github/issues/vmvelev/home-assistant-toshiba_ac.svg)](https://github.com/vmvelev/home-assistant-toshiba_ac/issues)
[![Github Open Pull Requests](https://img.shields.io/github/issues-pr/vmvelev/home-assistant-toshiba_ac.svg)](https://github.com/vmvelev/home-assistant-toshiba_ac/pulls)

# Toshiba - Air conditioning

Toshiba AC integration into home-assistant.io

> ### ⚠️ Upgrading from 2026.5.5 or earlier? (one-time action required)
>
> In **2026.6.0** the integration domain changed from `toshiba_ac` to **`toshiba_ac_community`** (required to join the default HACS catalog - see [hacs/default#7350](https://github.com/hacs/default/pull/7350)). Home Assistant can't move a configured integration to a new domain automatically, so you must **remove and re-add the integration once**:
>
> 1. Update in HACS and **restart HA** - the old entry will show as *not loaded* (expected).
> 2. **Settings -> Devices & Services** -> delete the old **Toshiba AC (Community)** entry -> **restart HA**.
> 3. **Add integration -> Toshiba AC (Community)** and re-enter your Toshiba credentials.
> 4. Reuse the **same entity IDs** (delete any leftover that forces a `_2` suffix) to keep automations, dashboards, and energy history intact.
>
> The service is now `toshiba_ac_community.reconnect`. Full details in the [changelog](CHANGELOG.md).

## About this fork

This project is a maintained fork of [h4de5/home-assistant-toshiba_ac](https://github.com/h4de5/home-assistant-toshiba_ac), the original Home Assistant integration for Toshiba AC. Full credit to @h4de5 and all upstream contributors for the base integration.

When upstream activity slowed, this fork was created to keep a **working, stable** integration for the community. Upstream has since become active again (for example with `toshiba-ac` 0.3.13 in their `2026.5.1` release). Both projects now share the same underlying library version; the difference is mainly in **Home Assistant integration behaviour**.

### Two layers

| Layer | Repository | What it does |
|-------|------------|--------------|
| **Protocol library** | [KaSroka/Toshiba-AC-control](https://github.com/KaSroka/Toshiba-AC-control) (`toshiba-ac` on PyPI) | HTTP login, device list, AMQP/MQTT push updates |
| **HA integration** | This fork, or [h4de5's repo](https://github.com/h4de5/home-assistant-toshiba_ac) | Config flow, entities, startup, reconnect, how HA talks to the library |

Library fixes (HTTP pacing, 403 retries, and similar) belong in **Toshiba-AC-control** and are tracked in both integrations when the dependency is bumped. This fork adds extra logic in `custom_components/toshiba_ac` for problems that showed up in Home Assistant specifically.

### What this fork adds (on top of upstream)

These are **HA-layer** changes; see the [changelog](https://github.com/vmvelev/home-assistant-toshiba_ac/blob/main/CHANGELOG.md) and [releases](https://github.com/vmvelev/home-assistant-toshiba_ac/releases) for version history.

- **Fresh SAS token on every HA startup** - avoids `Credentials invalid` after a restart when a stored token has expired
- **Device list pre-fetched before platforms load** - avoids the 60-second platform setup timeout when climate, sensor, and other platforms each tried to fetch devices separately
- **Startup rate-limit (403) handling** - transient WAF/rate-limit responses at boot are retried by Home Assistant instead of prompting reconfiguration
- **Short startup delay** - reduces simultaneous API calls when many integrations start at once
- **Event-driven reconnect** - detects Azure IoT Hub disconnects and reloads the integration only if the SDK does not recover on its own (typically within 30 seconds)

Current releases use **`toshiba-ac` 0.3.13** (HTTP/API stability in the library) plus the items above. Use **2026.5.5** or later.

### Which repository should I use?

| Your situation | Suggestion |
|----------------|------------|
| Failures after every HA restart, false "reconfigure" after 403 at startup, or disconnect/reload issues | **Toshiba AC (Community)** - this fork (install via HACS custom repository below) |
| You prefer the original integration and upstream is responding to issues | **Toshiba AC** - [h4de5/home-assistant-toshiba_ac](https://github.com/h4de5/home-assistant-toshiba_ac) in HACS |
| Not sure | Pick one, note the **integration version** in bug reports (for example `2026.5.5`), and check whether the [official Toshiba app](https://play.google.com/store/apps/details?id=jp.co.toshiba_carrier.ac_control) works |

### Upstream and maintenance

I track upstream releases and merge shared changes (such as dependency bumps). If @h4de5 wants to merge the HA-layer fixes back or align maintenance, that is welcome - the goal is one healthy integration for users, not two competing codebases.

For discussion about this fork on the original repo, see [h4de5#285](https://github.com/h4de5/home-assistant-toshiba_ac/issues/285).

## Requirements

You need a supported (or compatible) Toshiba AC device with either a built-in Wifi module or an adapter. See [list of compatible devices](#compatible-devices)

## Installation

### Installation with HACS

> **Note:** This fork is not yet in the default HACS catalog. You need to add it as a custom repository first.

1. In HACS, click the three-dot menu (⋮) in the top-right corner and select **Custom repositories**
2. Enter the repository URL: `https://github.com/vmvelev/home-assistant-toshiba_ac`
3. Select **Integration** as the category and click **Add**
4. Search for **Toshiba AC (Community)** in HACS integrations and click **Install**
5. Reboot Home Assistant
6. Follow the common integration manual below

### or: Manual installation

- Download [latest release](https://github.com/vmvelev/home-assistant-toshiba_ac/releases)
- Create a folder: `custom_components` in your home-assistant config directory
- Extract content (the folder `toshiba_ac_community`) of the release zip into the newly created directory
- Reboot Home Assistant
- Follow common integration manual

### Common manual to activate the integration

- The integration should be available as `Toshiba AC (Community)` in the `Add integration dialog`
- You need to enter your Toshiba AC account credentials (same as within the app)
- There is no bounding/registering of new AC units possible with this code - please continue to use the app for this

### Upgrading from an older version (domain rename in 2026.6.0)

In **2026.6.0** the Home Assistant domain changed from `toshiba_ac` to `toshiba_ac_community`. Existing users must remove and re-add the integration once. **Do not just delete and re-add** - deleting the config entry leaves orphaned entities that hold your entity IDs and cause `_2` suffixes. Follow the step-by-step migration (standard UI path, plus an advanced path that also preserves devices) in the [CHANGELOG](CHANGELOG.md#202660---2026-06-25).

## Troubleshooting

### Setup Tips

- **Avoid long or complex passwords**: Some users report issues with passwords that are too long or contain special characters. If you have trouble setting up, try using a simpler password in the Toshiba app first.
- **Use the official app first**: Make sure your AC unit is properly set up and working in the official Toshiba app before adding it to Home Assistant.

### Connection Issues

Most connection problems are caused by **Toshiba's cloud service being temporarily unavailable**.

**Important:**
- A single failed setup after a Home Assistant restart is **not a bug** - the cloud may just be temporarily unreachable
- **Do NOT restart Home Assistant repeatedly** - this will trigger rate limiting on Toshiba's servers and make things worse
- **Best approach:** Wait 1-2 hours and try again

If you continue to have issues:
1. Enable debug logging (see below)
2. Check if the official Toshiba app works
3. Wait and retry after some time

### Debug Logging

Add this to your `configuration.yaml` to enable detailed logging:

```yaml
logger:
  default: warning
  logs:
    custom_components.toshiba_ac_community: debug
    toshiba_ac: debug
```

### Reporting Issues

- **Home Assistant integration issues**: [Open an issue here](https://github.com/vmvelev/home-assistant-toshiba_ac/issues)
- **API/Device communication issues**: [Open an issue at the API repository](https://github.com/KaSroka/Toshiba-AC-control/issues)

## Compatible devices

If your device is compatible with the [official Toshiba AC mobile app](https://play.google.com/store/apps/details?id=jp.co.toshiba_carrier.ac_control) or [Toshiba Home AC Control](https://play.google.com/store/apps/details?id=com.toshibatctc.SmartAC) it has good chances to be supported by this integration. The community maintains a list of confirmed hardware in the [Compatible Devices discussion](https://github.com/vmvelev/home-assistant-toshiba_ac/discussions/2) - feel free to add your device!

> **⚠️ North America Users:** Toshiba distributes their AC devices with a **completely different app and system** in the US: [Toshiba AC NA](https://play.google.com/store/apps/details?id=com.midea.toshiba&hl=de_AT). **This integration will NOT work with North American devices.** Instead, try [midea-ac-py](https://github.com/mill1000/midea-ac-py) which may be able to control NA-edition AC units without requiring an account.


## More links and resources

- Feature Request in the [home-assistant community](https://community.home-assistant.io/t/toshiba-home-ac-control/137698)
- my first draft to communicate with the rest service using an [Toshiba API client in PHP](https://gist.github.com/vmvelev/7f97db0f4efc265e48904d4a84dab4fb)
- extended example to retrieve state of the AC unit and update the timeprogram using an [Toshiba API client in python](https://github.com/vmvelev/home-assistant-toshiba_ac/tree/keep-http-api/custom_components/toshiba_ac/toshiba_ac_api)
- finally using AMQP interface to send state changes directly in [updated python package](https://github.com/KaSroka/Toshiba-AC-control)
