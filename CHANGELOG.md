# Changelog

## 0.4.0

- Add automatic runtime-device and MultiSensor discovery from `/api/systemvalues`.
- Add temperature, humidity, dew point, CO/CO₂, pressure, motion, door contact, external power, battery, signal strength and connectivity entities when exposed by KentixONE.
- Reuse the existing system-values request, adding no extra recurring measurement request.
- Preserve last-known battery and signal values when later responses omit them.
- Add automatic KentixONE webhook creation, update and alarm-group assignment.
- Use validated event codes for all alarms, system alarms and completed switching operations.
- Keep polling as a fallback and for environmental measurements.
- Add an option to enable or disable automatic webhook management.
- Add webhook-management diagnostics.

## 0.3.4

- Always create DoorLock battery and signal-strength sensors.
- Preserve last-known slow telemetry across temporary omissions and inventory errors.
