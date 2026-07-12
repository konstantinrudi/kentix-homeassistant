# KentixONE SmartAPI behavior

The integration uses different schedules for runtime state and inventory data.

## Frequent runtime request

At the user-configured polling interval, the integration performs only:

```text
GET /api/systemvalues
```

The current alarm-group state is read from `alarmgroups[].armed`. A KentixONE webhook also triggers this same lightweight request immediately.

## Infrequent inventory requests

At startup and then at most every four hours, the integration performs:

```text
GET /api/alarmgroups
GET /api/doorlocks
```

The older `/names` variants are fallback routes when the collection route is unavailable. These inventory responses are used for names, hierarchy, DoorLock discovery, and DoorLock battery values.

No periodic per-object detail requests are made. In particular, the integration does not routinely call:

```text
GET /api/alarmgroups/{id}
GET /api/doorlocks/{id}
```

## Commands

User actions use the corresponding command endpoint:

```text
POST /api/alarmgroups/{id}/arm
POST /api/alarmgroups/{id}/disarm
PUT /api/doorlocks/{id}/open
```

The DoorLock command is represented as a stateless button because the tested Kentix configuration releases manual cylinder rotation rather than reporting a persistent lock state.
