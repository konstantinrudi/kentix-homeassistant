# Upgrade to 0.3.0

Version 0.3.0 changes the DoorLock representation and adds automatic device hierarchy discovery.

## Important change

Kentix does not expose a persistent locked/unlocked state for the validated DoorLock setup. The previous `lock` entity was therefore misleading and has been replaced by one stateless button named **Release lock** / **Schloss freigeben**.

The button briefly enables manual rotation of the cylinder. It does not claim that the door is locked, unlocked, open, or closed.

## Updating a source checkout

When copying the release over an existing Git checkout, delete the obsolete platform file explicitly:

```bash
rm -f custom_components/kentix/lock.py
```

Then copy the new release, run the repository configuration script, commit all changes with `git add -A`, and restart Home Assistant.

## Existing Home Assistant entities

During setup, the integration removes obsolete `lock.*` registry entries belonging to Kentix. The existing DoorLock button keeps its previous unique ID, so Home Assistant should reuse the prior button entity instead of creating a duplicate.

## Automatic devices and hierarchy

Visible alarm groups and DoorLocks are registered automatically as Home Assistant devices. Alarm groups are named by hierarchy depth:

- `Standort - <Name>`
- `Gebäude - <Name>`
- `Etage - <Name>`
- `Bereich - <Name>` for deeper nesting

The device registry links children to their parent device. User-assigned custom device names are preserved by Home Assistant.
