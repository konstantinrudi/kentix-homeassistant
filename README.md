# Kentix for Home Assistant

<p align="center">
  <img src="assets/kentix-homeassistant.png" alt="Kentix for Home Assistant" width="420">
</p>

A local, HACS-compatible Home Assistant custom integration for KentixONE alarm groups, DoorLocks and MultiSensors.

> This community project is not affiliated with or endorsed by Kentix GmbH.

## Features

- Automatic discovery of alarm groups, DoorLocks and Kentix runtime devices
- Native `alarm_control_panel` entities with arm/disarm support
- Stateless **Release lock** button for Kentix DoorLocks
- MultiSensor values from the existing `GET /api/systemvalues` request
- Temperature, humidity, dew point, CO/CO₂, pressure, motion, door contact, external power, battery, signal strength and connectivity when exposed by KentixONE
- Automatic KentixONE webhook creation and alarm-group assignment
- Immediate refresh after alarms and completed switching operations
- Polling remains active as a fallback and for continuously changing environmental values
- Kentix hierarchy represented as Home Assistant devices
- UI setup, options, diagnostics, reauthentication, German and English translations

## Installation

### HACS custom repository

1. In HACS, open **Custom repositories**.
2. Add the GitHub repository URL and select **Integration**.
3. Download **Kentix** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → Kentix**.

### Manual installation

Copy `custom_components/kentix` into:

```text
<config>/custom_components/kentix
```

Restart Home Assistant and add Kentix under **Settings → Devices & services**.

## Configuration

The setup flow asks for:

- KentixONE URL or hostname
- Personal SmartAPI bearer token
- Whether Home Assistant should verify the TLS certificate

TLS certificate verification is disabled by default because many local KentixONE installations use self-signed certificates.

Use a dedicated Kentix user with only the permissions required for the desired alarm groups, DoorLocks and webhook configuration.

## Refresh schedule and API load

The **System values polling interval** is configurable under **Settings → Devices & services → Kentix → Configure**.

- Default: **60 seconds**
- Older Kentix hardware: **60 seconds recommended**
- Modern SiteManagers: **30 seconds is usually suitable**
- Every normal cycle uses one `GET /api/systemvalues` request
- Alarm-group and DoorLock inventory is read at startup and at most every **4 hours**
- DoorLock inventory battery values are refreshed in that four-hour cycle
- Runtime battery and signal values found in `/api/systemvalues` are updated with the normal cycle
- The last known battery and signal value is retained when Kentix temporarily omits it

Alarm groups and MultiSensor values share the same system-values request. A separate MultiSensor polling interval would therefore not reduce API load.

## Automatic KentixONE webhooks

Automatic webhook management is enabled by default and can be disabled in the integration options. The generated object is visible in KentixONE under **Automation → Webhooks**.

When enabled, the integration:

1. Creates one active webhook with a unique name containing the Home Assistant config-entry ID.
2. Uses the local Home Assistant webhook URL as its destination.
3. Assigns the webhook to every visible alarm group for:
   - all alarms and warnings,
   - system alarms and warnings,
   - completed switching operations.
4. Reconciles the webhook and assignments at startup and then at most every four hours.
5. Leaves all unrelated Kentix webhooks unchanged.
6. Removes only its own webhook and assignments when the integration is deleted.

The validated Kentix event codes are:

| Event | Code |
|---|---:|
| All alarms | `0` |
| Armed-active alarms | `1` |
| Always-active alarms | `2` |
| Fire alarms | `3` |
| Sabotage alarms | `4` |
| System alarms | `5` |
| After every switching operation | `50` |
| After successful arming | `55` |
| After successful disarming | `56` |
| Before arming | `57` |
| Before disarming | `58` |

The managed setup intentionally uses codes `0`, `5` and `50` to avoid redundant duplicate notifications.

A received webhook does not blindly overwrite Home Assistant state. It triggers an immediate fresh `GET /api/systemvalues` request, and that API response remains authoritative.

Automatic management requires Home Assistant to have an internal URL reachable from KentixONE. If that is unavailable, the integration continues to work through polling and exposes the webhook setup status as a diagnostic entity.

## MultiSensor and runtime-device entities

The integration reads `devices[]` and `units` from `/api/systemvalues`. It creates one Home Assistant device per physical Kentix device and adds only measurements that Kentix exposes and has enabled.

Common mappings:

| Kentix measurement | Home Assistant entity |
|---|---|
| `temperature` | temperature sensor |
| `humidity` | humidity sensor |
| `dewpoint` | dew-point sensor |
| `co` / `co2` | gas concentration sensor |
| `pressure` | pressure sensor |
| `motion` | motion binary sensor |
| `reed` | door-contact binary sensor |
| `ext_power` | external-power binary sensor |
| `battery_level` | battery sensor |
| `signal_strength` | signal-strength sensor |
| `connection` | connectivity binary sensor |

Measurements with `assignment: off` or `status: inactive` are not created until Kentix enables them.

Known type mappings currently include:

- `2` → MultiSensor-RF-BAT
- `3` → MultiSensor-DOOR
- `21` → DoorLock
- `101` → AlarmManager
- `105` → AccessManager

Unknown types still appear as generic Kentix devices when they expose supported measurements.

## DoorLock control

Kentix DoorLocks used with a manually rotated cylinder do not provide a persistent locked/unlocked state. The integration exposes one stateless button:

```text
Schloss freigeben
```

It sends:

```text
PUT /api/doorlocks/{id}/open
```

This briefly authorizes manual cylinder rotation.

## Alarm control

```text
PUT /api/alarmgroups/{id}/arm
PUT /api/alarmgroups/{id}/disarm
```

The live state is read from `/api/systemvalues` and maps `alarmgroups[].armed` to Home Assistant `armed_away` or `disarmed`.

## Device hierarchy

Alarm-group names follow:

- `Standort - <Name>`
- `Gebäude - <Name>`
- `Etage - <Name>`
- `Bereich - <Name>` for deeper levels

Runtime devices use their physical parent device when Kentix provides `device_id`; otherwise they are attached to their alarm group. DoorLocks remain represented by their dedicated DoorLock device.

The integration does not create an additional synthetic `KentixONE (IP address)` device.

## Security and privacy

- Keep Home Assistant and KentixONE on trusted networks.
- Treat the Home Assistant webhook URL as a credential.
- Use a least-privilege Kentix API user.
- Restrict that user to the DoorLocks and alarm groups Home Assistant may control.
- Tokens, hosts, object names and raw Kentix payloads are excluded from diagnostics.
- Webhook payloads are not treated as authoritative state.

Security reports can be submitted as described in [SECURITY.md](SECURITY.md).

## HACS icon note

The repository includes HACS brand assets under `brand/` and Home Assistant local brand files under `custom_components/kentix/brand/`. The icon may still be missing in some HACS frontend versions even though it appears correctly in Home Assistant.

## License

Licensed under the [Apache License 2.0](LICENSE).

Copyright 2026 [@konstantinrudi](https://github.com/konstantinrudi). Attribution and license notices must be preserved when redistributing the project. See [NOTICE](NOTICE).
