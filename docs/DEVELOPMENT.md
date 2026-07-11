# Development notes

## Architecture

- `api.py`: HTTP transport, route adapter, response envelopes
- `models.py`: firmware-tolerant normalization into immutable dataclasses
- `coordinator.py`: one coordinated poll shared by all entities
- `alarm_control_panel.py`: native alarm-group controls
- `lock.py`: DoorLock representation and remote-open action
- `button.py`: explicit, automation-friendly door-open action
- `binary_sensor.py`: door-contact state

## Release plan

### 0.1.0 hardware preview

- Confirm API paths and methods on KentixONE 8.5.x and 8.6.x
- Add sanitized response fixtures
- Correct normalization based on fixtures
- Add full Home Assistant config-flow/entity tests
- Replace repository metadata placeholders

### 0.2.0

- Kentix webhook receiver and immediate coordinator refresh
- Dynamic entity creation for objects added after setup
- Reauthentication and reconfiguration flows
- Translatable service/action errors

### 0.3.0

- Active alarms and acknowledgement
- Access events with privacy-conscious opt-in
- Additional MultiSensor and environmental entities
- HACS default-repository submission readiness

## Quality gates

- `python -m compileall custom_components/kentix`
- Ruff formatting and linting
- HACS validation action
- Hassfest action
- Tests using `pytest-homeassistant-custom-component`
- No secrets or personal access data in fixtures
