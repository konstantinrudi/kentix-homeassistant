# GitHub metadata required by HACS

HACS validation reads repository metadata from GitHub, not from files in this repository.

Recommended description:

> Home Assistant custom integration for KentixONE alarm groups and DoorLocks via the local SmartAPI.

Recommended topics:

- `home-assistant`
- `homeassistant`
- `hacs`
- `kentix`
- `kentixone`
- `alarm-system`
- `smart-home`
- `door-lock`

Using GitHub CLI from the repository directory:

```bash
gh repo edit \
  --description "Home Assistant custom integration for KentixONE alarm groups and DoorLocks via the local SmartAPI." \
  --add-topic home-assistant \
  --add-topic homeassistant \
  --add-topic hacs \
  --add-topic kentix \
  --add-topic kentixone \
  --add-topic alarm-system \
  --add-topic smart-home \
  --add-topic door-lock
```
