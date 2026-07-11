# Kentix for Home Assistant

A local, HACS-compatible Home Assistant custom integration for KentixONE alarm groups and DoorLocks.

> This project is community-maintained and is not affiliated with or endorsed by Kentix GmbH.

## Features

- Automatic discovery of all alarm groups visible to the SmartAPI user
- Native `alarm_control_panel` entities with arm/disarm actions; runtime states are exposed only when a Kentix runtime response provides them
- Automatic discovery of DoorLocks; door-contact entities are created only when a configured contact and runtime value are available
- Optional, explicitly enabled door control using `lock.open` and a dedicated **Open door** button
- Dynamic creation of entities when Kentix objects are added later; no integration reload required
- Local webhook endpoint for immediate refreshes, with polling as a reliable fallback
- Home Assistant events for alarm changes, door changes, door opening and received Kentix webhooks
- Battery, signal-strength, alarm-count and warning-count sensors when exposed by the appliance
- Partial operation when the API account may access only alarm groups or only DoorLocks
- UI configuration, options, reauthentication, reconfiguration, diagnostics, German and English translations
- HACS, Hassfest, Ruff and pytest GitHub Actions

## Installation

### HACS custom repository

1. Publish this project as a public GitHub repository.
2. In HACS, open **Custom repositories**.
3. Enter the repository URL and select **Integration**.
4. Download **Kentix** and restart Home Assistant.
5. Open **Settings → Devices & services → Add integration → Kentix**.

### Manual installation

Copy `custom_components/kentix` into your Home Assistant configuration directory as:

```text
<config>/custom_components/kentix
```

Restart Home Assistant and add the integration from **Settings → Devices & services**.

## Configuration

The setup flow asks for:

- KentixONE URL or hostname
- Personal SmartAPI bearer token
- Whether Home Assistant should verify the TLS certificate

Use a dedicated Kentix user with only the permissions required for the desired alarm groups and doors.

Door control is **disabled by default**. Enable it under the integration's options only after the read-only entities work and the Kentix account has intentionally limited remote-open permissions.

### Polling interval

The polling interval is adjustable under **Settings → Devices & services → Kentix → Configure**.

- The default is **60 seconds**.
- For older Kentix hardware, **60 seconds is recommended**.
- Modern SiteManagers can usually be polled every **30 seconds**.
- Shorter intervals increase the request load on KentixONE.
- A configured Kentix webhook can trigger immediate refreshes while polling remains the fallback.

Existing installations keep their previously saved interval after an update. Change it manually in the integration options when needed.

## Webhook setup

The integration polls KentixONE. A local webhook can additionally trigger an immediate SmartAPI refresh.

1. Open the Kentix integration in Home Assistant.
2. Choose **Configure**.
3. Copy the displayed webhook URL.
4. Create a KentixONE HTTP webhook for the desired alarm/switching events and use that URL as the target.

The receiver accepts `POST` and `PUT`, is registered as local-only, limits request bodies to 256 KiB and does not trust webhook state. It records only an optional event ID/type, then refreshes the available SmartAPI data.

## Entities

| Kentix data | Home Assistant entity |
|---|---|
| Alarm group | `alarm_control_panel` |
| DoorLock | `lock` when door control is enabled |
| Door remote-open action | `button` when door control is enabled |
| Door contact | `binary_sensor` |
| DoorLock reachability | diagnostic `binary_sensor` |
| Alarm-group/DoorLock API availability | diagnostic `binary_sensor` |
| Active alarms/warnings | disabled-by-default `sensor` |
| DoorLock battery/RSSI | diagnostic `sensor` |
| Webhook count/last reception | disabled-by-default diagnostic `sensor` |

Entities are created only when their corresponding value is available in the API response.

## Events

The integration emits these Home Assistant events:

- `kentix_alarm_changed`
- `kentix_door_changed`
- `kentix_door_opened`
- `kentix_webhook_received`

Example:

```yaml
alias: Notify on Kentix alarm change
triggers:
  - trigger: event
    event_type: kentix_alarm_changed
conditions:
  - condition: template
    value_template: "{{ trigger.event.data.new_state == 'triggered' }}"
actions:
  - action: notify.notify
    data:
      title: Kentix alarm
      message: >-
        {{ trigger.event.data.object_name }} changed from
        {{ trigger.event.data.previous_state }} to
        {{ trigger.event.data.new_state }}.
```

Opening a door from an automation:

```yaml
sequence:
  - action: lock.open
    target:
      entity_id: lock.front_door_lock
```

Because this controls physical access, add your own confirmation, presence and authorization conditions around such an automation.

## SmartAPI adapter

The integration currently targets these documented route families and falls back from collection routes to the older `/names` variants where necessary:

```text
GET  /api/alarmgroups
GET  /api/alarmgroups/names
GET  /api/alarmgroups/{id}
POST /api/alarmgroups/{id}/arm
POST /api/alarmgroups/{id}/disarm

GET  /api/doorlocks
GET  /api/doorlocks/names
GET  /api/doorlocks/{id}
POST /api/doorlocks/{id}/open
```

Response normalization accepts common top-level envelopes, nested status objects and camelCase/PascalCase variations. Sparse list responses are enriched through per-object detail requests with bounded concurrency. Real KentixONE validation shows that the list and detail routes above primarily provide inventory and configuration. They must not be interpreted as proof of current armed, alarm, door-contact or reachability state. The live alarm-group state is read from `GET /api/systemvalues` and mapped from `alarmgroups[].armed`. `GET /api/state/cell` is not used for alarm state.

Kentix marks the currently documented DoorLock remote-open operation as deprecated in newer KentixONE documentation. It is isolated in `KentixRoutes`, so a successor endpoint can be changed without touching the entity layer.

## Security and privacy

- Keep Home Assistant and KentixONE on trusted networks.
- Keep TLS certificate verification enabled where possible.
- Never expose the Home Assistant webhook path publicly.
- Use a least-privilege Kentix API user.
- Door control is opt-in.
- Tokens are redacted from diagnostics.
- Raw Kentix payloads and access records are not included in diagnostics.
- Webhook payloads are not persisted and are not treated as authoritative state.

Report security issues privately as described in [SECURITY.md](SECURITY.md).

## Repository setup before publishing

No Kentix installation data is required. The only repository-specific value is the GitHub owner. After creating the repository, run:

```bash
python scripts/configure_repository.py YOUR_GITHUB_USERNAME
```

This updates the documentation URL, issue tracker and Home Assistant `codeowners` field. Commit the changes and push them.

To create release `0.2.4`:

```bash
git tag v0.2.4
git push origin v0.2.4
```

The release workflow validates that the tag matches `manifest.json` and publishes a GitHub release. HACS installs the integration from the repository release using the standard `custom_components/kentix` structure.

## Development

Home Assistant 2026.7 uses Python 3.14. The included CI uses that runtime.

```bash
python -m pip install -r requirements_test.txt
ruff check .
ruff format --check .
python -m compileall custom_components/kentix
python scripts/check_imports.py
pytest
```

See [development notes](docs/DEVELOPMENT.md) and the [SmartAPI compatibility notes](docs/KENTIX_API.md).

## Compatibility status

The repository is an actively validated release candidate. Inventory and configuration payloads are covered by real KentixONE samples and automated checks. Runtime alarm-group armed state is validated through `/api/systemvalues`; optional alarm, transition, door-contact and reachability fields remain dependent on what the installed Kentix system exposes. Unsupported or absent values are intentionally reported as unknown rather than guessed.

## License

MIT
