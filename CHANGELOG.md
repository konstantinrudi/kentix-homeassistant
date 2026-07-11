# Changelog

## 0.3.1

- Reduced normal polling to one `GET /api/systemvalues` request per configured interval.
- Moved alarm-group and DoorLock discovery to startup and a maximum frequency of once every four hours.
- DoorLock battery values now refresh at most once every four hours.
- Removed periodic alarm-group and DoorLock detail requests.
- Expanded the README with exact KentixONE webhook configuration and event-assignment steps.
- Removed repository-maintainer/internal setup instructions from the public README.
- Updated `actions/setup-python` to v6 for Node.js 24 runners.

## 0.3.0

- Added automatic Home Assistant device-registry discovery for alarm groups and DoorLocks.
- Added hierarchical alarm-group names and parent-device links.
- Replaced the misleading lock entity with one stateless DoorLock release button.
- Enabled DoorLock controls automatically.
