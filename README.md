# Kentix for Home Assistant

<p align="center">
  <img src="assets/kentix-homeassistant.png" alt="Kentix for Home Assistant" width="420">
</p>

A local, HACS-compatible Home Assistant custom integration for KentixONE alarm groups and DoorLocks.

> This community project is not affiliated with or endorsed by Kentix GmbH.

## Features

- Automatic discovery of alarm groups visible to the SmartAPI user
- Native `alarm_control_panel` entities for arming and disarming
- Live alarm-group state from `GET /api/systemvalues`
- Automatic DoorLock discovery and one stateless **Release lock** button per DoorLock
- Kentix hierarchy represented as Home Assistant devices: site, building, floor and deeper areas
- Optional local webhook for immediate refreshes, with polling as a fallback
- DoorLock battery information when exposed by KentixONE
- UI setup, options, diagnostics, reauthentication, German and English translations

## Installation

### HACS custom repository

1. In HACS, open **Custom repositories**.
2. Add the GitHub repository URL and select **Integration**.
3. Download **Kentix** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → Kentix**.

### Manual installation

Copy `custom_components/kentix` into your Home Assistant configuration directory:

```text
<config>/custom_components/kentix
```

Restart Home Assistant and add Kentix under **Settings → Devices & services**.

## Configuration

The setup flow asks for:

- KentixONE URL or hostname
- Personal SmartAPI bearer token
- Whether Home Assistant should verify the TLS certificate

TLS certificate verification is disabled by default because many local KentixONE installations use self-signed certificates. Enable verification when the appliance uses a certificate trusted by Home Assistant.

Use a dedicated Kentix user with only the permissions required for the desired alarm groups and DoorLocks.

## API load and refresh schedule

The normal polling interval is adjustable under **Settings → Devices & services → Kentix → Configure**.

- Default: **60 seconds**
- Older Kentix hardware: **60 seconds recommended**
- Modern SiteManagers: **30 seconds is usually suitable**
- Every normal polling cycle requests only `GET /api/systemvalues`
- Alarm-group and DoorLock inventory is read once at startup and then at most every **4 hours**
- DoorLock battery values are refreshed with the same four-hour inventory cycle
- The last successfully received battery value remains visible until KentixONE supplies a newer value
- A Home Assistant restart triggers one immediate inventory refresh

This avoids repeated collection and detail requests during normal state polling.

## KentixONE webhook setup

Polling remains active as a reliable fallback. A KentixONE webhook can additionally notify Home Assistant immediately after an alarm-group event.

### 1. Copy the Home Assistant webhook URL

1. Open **Settings → Devices & services**.
2. Open the configured **Kentix** integration.
3. Select **Configure**.
4. Copy the displayed webhook URL.

The URL contains a secret identifier. Treat it like a credential and do not publish it.

### 2. Create the webhook in KentixONE

1. Open the KentixONE web interface with an administrator account.
2. Go to **Automation → Webhooks**.
3. Create a new active webhook.
4. Use the Home Assistant webhook URL as the destination.
5. Select HTTP method **POST**.
6. Select content type **application/json**.
7. Use a small payload, for example:

```json
{
  "eventType": "kentix_state_changed"
}
```

8. Use the KentixONE test function to verify that Home Assistant receives the request.

### 3. Assign the webhook to events

Assign the webhook to the relevant alarm groups. The recommended event is **Change of switching status** so Home Assistant refreshes immediately when a group is armed or disarmed. Depending on the KentixONE version, additional useful events include **After arming**, **After disarming**, alarm events and system notifications.

The webhook payload is not accepted as the authoritative alarm state. Receiving a webhook only causes the integration to read the current state again from `GET /api/systemvalues`.

The receiver accepts `POST` and `PUT`, is local-only, limits request bodies and does not persist the complete payload.

## Devices and entities

| Kentix data | Home Assistant representation |
|---|---|
| Alarm group | `alarm_control_panel` |
| DoorLock manual-rotation release | stateless `button` |
| Door contact, when actually available | `binary_sensor` |
| DoorLock battery/RSSI, when available | diagnostic `sensor` |
| API and webhook diagnostics | diagnostic entities |

Alarm-group device names follow the hierarchy:

- `Standort - <Name>` for top-level groups
- `Gebäude - <Name>` for their children
- `Etage - <Name>` for the next level
- `Bereich - <Name>` for deeper nested groups

DoorLocks are linked to their parent alarm-group device when KentixONE provides the relationship.

The integration does not create an additional synthetic `KentixONE (IP address)` device. Integration-level diagnostics remain available as standalone entities.

## DoorLock control

Kentix DoorLocks used with a manually rotated cylinder do not provide a persistent Home Assistant locked/unlocked state. The integration therefore exposes one stateless button:

```text
Schloss freigeben
```

Pressing it sends:

```text
PUT /api/doorlocks/{id}/open
```

This briefly authorizes manual cylinder rotation. It does not claim that the physical door is locked or unlocked.

Example automation action:

```yaml
sequence:
  - action: button.press
    target:
      entity_id: button.front_door_release_lock
```

Because this controls physical access, add suitable presence, authorization and confirmation conditions to automations.

## Alarm state mapping

The live alarm-group state is read from:

```text
GET /api/systemvalues
```

The integration maps `alarmgroups[].armed` as follows:

| KentixONE | Home Assistant |
|---|---|
| `false` | `disarmed` |
| `true` | `armed_away` |

Runtime groups are matched by ID when available, otherwise by an unambiguous exact name.

## Security and privacy

- Keep Home Assistant and KentixONE on trusted networks.
- Do not expose the webhook URL publicly.
- Use a least-privilege Kentix API user.
- Restrict that user to the DoorLocks that Home Assistant may release.
- Tokens, hosts, object names and raw Kentix payloads are excluded from diagnostics.
- Webhook payloads are not treated as trusted state.

Security reports can be submitted as described in [SECURITY.md](SECURITY.md).

## HACS icon note

The repository contains the required HACS brand asset at `brand/icon.png` and the Home Assistant local brand files under `custom_components/kentix/brand/`. The icon may still be missing in the HACS dashboard because current HACS frontend versions do not yet display locally shipped custom-integration brand icons. The same icon should appear correctly in Home Assistant itself.

## License

Licensed under the [Apache License 2.0](LICENSE).

Copyright 2026 [@konstantinrudi](https://github.com/konstantinrudi). Attribution and license notices must be preserved when redistributing the project. See [NOTICE](NOTICE).


DoorLock battery data and signal strength are refreshed at startup and then at most every **4 hours**. Last known values remain visible across sparse or temporarily failed refreshes.
