# Kentix SmartAPI hardware-validation notes

Use a dedicated, least-privilege Kentix user and a non-critical demo system.
Never share bearer tokens, personal access records, RFID values, email addresses,
phone numbers or camera URLs.

## Validated inventory/configuration routes

The following read-only routes were validated against a real KentixONE demo
system and returned HTTP 200 with JSON:

```text
GET /api/alarmgroups
GET /api/alarmgroups/names
GET /api/alarmgroups/{id}
GET /api/doorlocks
GET /api/doorlocks/names
GET /api/doorlocks/{id}
```

Observed response behavior:

- Collection routes use a Laravel-style `data`, `links`, `meta` envelope and
  are paginated with 25 entries per page.
- `/names` routes return a plain JSON list.
- Alarm-group detail responses are configuration objects. Fields such as
  `arm_delay`, `has_prealarm`, `maintenance`, `webhooks` and `event_id` do not
  describe the current armed/alarm state.
- DoorLock detail responses are configuration objects. `is_active` means the
  object is enabled; `connection.warning.active` configures warning behavior
  and must not be interpreted as current connectivity.
- DoorLock battery values may be categorical, for example `full`.
- A DoorLock without `reed_source_id` and with `reed_assignment: off` has no
  configured door-contact source, so no open/closed entity should be created.

## Runtime alarm state

The live alarm-group armed state is read from:

```text
GET /api/systemvalues
```

Observed/confirmed shape:

```json
{
  "alarmgroups": [
    {"name": "Example group", "armed": true}
  ]
}
```

The integration matches runtime entries by a real alarm-group ID when one is
provided. When the runtime item contains only a name, it matches only a unique
case-insensitive exact name. Duplicate names are deliberately left unknown.
The boolean `armed` maps to Home Assistant `armed_away` or `disarmed`.

`GET /api/state/cell` was validated in both an armed and disarmed test run and
returned the same cellular-modem initialization payload. It is not used for
alarm state.

## Mutating calls

Perform these only on a test alarm group or test door, after confirming the
operation in the SmartAPI documentation for the installed firmware:

- `POST /api/alarmgroups/{id}/arm`
- `POST /api/alarmgroups/{id}/disarm`
- DoorLock remote-open route: verify against installed firmware; the historic
  endpoint is deprecated in newer documentation.
