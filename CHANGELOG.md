# Changelog

## 0.2.6 - 2026-07-12

- Fix Home Assistant hassfest manifest key ordering
- Preserve the required `domain`, `name`, then alphabetical manifest order when configuring repository metadata
- Add regression coverage for manifest ordering
- Document required GitHub repository description and topics for HACS validation

## 0.2.5 - 2026-07-12

- Fix the local webhook module name collision with Home Assistant's webhook component
- Disable TLS certificate verification by default for new entries
- Add original MIT-licensed repository and integration artwork
- Update GitHub Actions to Node.js 24-compatible action versions

## 0.2.4 - 2026-07-12

- Change the default SmartAPI polling interval from 30 to 60 seconds
- Keep the polling interval configurable from 5 to 3600 seconds
- Add UI guidance: use 60 seconds for older hardware; modern SiteManagers can usually use 30 seconds
- Document that existing installations keep their saved interval after updating

## 0.2.3 - 2026-07-12

- Read live alarm-group armed state from `/api/systemvalues`
- Map `alarmgroups[].armed` to Home Assistant armed/disarmed states
- Match runtime groups by ID where available and otherwise by unique exact name
- Stop using `/api/state/cell` for alarm state

## 0.2.2 - Unreleased

- Validate real alarm-group and DoorLock detail payloads
- Treat detail responses as configuration rather than live state
- Stop reporting DoorLocks as reachable without an explicit runtime field
- Record parent alarm groups, arming group, arm delay and door-contact capability

## 0.2.1 - Unreleased

- Validate KentixONE collection and names responses against a real demo system
- Follow paginated SmartAPI collection responses via same-origin `links.next`
- Normalize categorical DoorLock battery values such as `full`
- Add coverage for real KentixONE alarm-group and DoorLock payload shapes

## 0.2.0

- Dynamic alarm-group and DoorLock discovery
- Alarm and door state events
- Local webhook refresh support with polling fallback
- Reauthentication, diagnostics and release automation

## 0.1.0 - Unreleased

- Initial HACS-compatible custom integration scaffold
- UI setup with Kentix SmartAPI Bearer Token
- Alarm-group discovery, state, arm and disarm
- DoorLock discovery and remote-open adapter
- Lock, button and door-contact entities
- Diagnostics, translations and validation workflows
