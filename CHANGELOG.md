# Changelog

## 0.4.4

- Detect real KentixONE alarm states from `/api/systemvalues`.
- Normalize nested `active_alarms` and `active_warnings` counters.
- Return alarm groups from `triggered` to `armed` after an alarm is acknowledged.
- Add regression tests for the observed KentixONE alarm lifecycle.

## 0.4.3

- AccessManager and DoorLock discovery fixes.
