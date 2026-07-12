# Changelog

## 0.3.2 - 2026-07-12

- Use the documented `PUT /api/doorlocks/{id}/open` method for DoorLock release.
- Rewrite the public README without maintainer-only setup, test or release instructions.
- Add the project image to the README.
- Document the known HACS frontend limitation for locally shipped custom-integration icons.
- Remove temporary upgrade documents while the integration is in private testing.

## 0.3.1 - 2026-07-12

- Poll only `/api/systemvalues` at the configured short interval.
- Refresh alarm-group and DoorLock inventory, including battery data, at startup and at most every four hours.
- Remove periodic per-object detail requests.
- Expand the KentixONE webhook setup documentation.
- Update `actions/setup-python` to the Node.js 24 based v6 action.

## 0.3.0 - 2026-07-12

- Register every discovered alarm group and DoorLock automatically in the Home Assistant device registry.
- Represent the alarm-group hierarchy through parent/child device relationships.
- Prefix alarm-group device names with `Standort`, `Gebäude`, `Etage`, or `Bereich` according to hierarchy depth.
- Replace the misleading stateful lock entity and duplicate open button with one stateless **Release lock** button.
- Enable DoorLock release controls automatically from first setup.
- Remove obsolete Kentix lock entities from the Home Assistant entity registry during setup.

## 0.2.8 - 2026-07-12

- Configure pytest-asyncio in `auto` mode, matching Home Assistant Core.
- Set the default async fixture loop scope to `function`.
- Fix CI failures caused by Home Assistant's async `enable_event_loop_debug` fixture under pytest 9.
- Add regression coverage for the pytest asyncio configuration.

## 0.2.7

- Fixed the GitHub Actions test dependency conflict by allowing
  `pytest-homeassistant-custom-component` to install its matching pytest version.
- Limited test and validation workflows to pushes to `main` and pull requests.
  Release tag pushes now run only the release workflow.
- Added workflow concurrency so superseded runs on the same ref are cancelled.

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
