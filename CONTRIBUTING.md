# Contributing

Contributions are welcome through GitHub issues and pull requests.

Before submitting code:

```bash
python -m pip install -r requirements_test.txt
ruff check .
ruff format --check .
python -m compileall custom_components/kentix
pytest
```

Keep API fixtures synthetic or fully sanitized. Do not include tokens, user identities, card identifiers, access histories, real hostnames, camera URLs or physical site details.

For firmware compatibility changes, include the KentixONE version and a minimal description of the response shape, but no customer-specific data.
