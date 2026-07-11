# Upgrade from 0.2.4 to 0.2.5

Version 0.2.5 fixes a setup failure where the local `webhook.py` module shadowed Home Assistant's webhook component.

1. Extract the 0.2.5 archive next to your existing Git repository.
2. From your existing repository, copy the new files over it (adjust the source path):

   ```bash
   rsync -a ~/Downloads/kentix-homeassistant-v0.2.5/ ./
   rm -f custom_components/kentix/webhook.py
   ```

3. Restore your repository-specific metadata:

   ```bash
   python3 scripts/configure_repository.py YOUR_GITHUB_USERNAME
   ```

4. Commit, push, and publish the release:

   ```bash
   git add -A
   git commit -m "Release v0.2.5"
   git push
   git tag -a v0.2.5 -m "Kentix Home Assistant v0.2.5"
   git push origin v0.2.5
   ```

5. Update Kentix through HACS and restart Home Assistant.

New configurations default TLS certificate verification to off. Existing config entries retain the value already stored in Home Assistant; use **Settings → Devices & services → Kentix → Reconfigure** to change it.
