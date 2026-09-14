# Contributing

This is a community fork of the abandoned [briis/securityspy](https://github.com/briis/securityspy) integration. Contributions are welcome!

## Reporting Bugs

Open an [issue](https://github.com/JoshADC/securityspy/issues) with:
- Your SecuritySpy version and Home Assistant version
- Steps to reproduce
- Relevant logs (see [Debug Logging](README.md#debug-logging) in the README)

## Submitting Changes

1. Fork the repo and create a branch from `master`.
2. Make your changes and test them with a real SecuritySpy instance if possible.
3. Run the linter and tests: `python3 -m ruff check . && python3 -m pytest`
4. Open a pull request.

## Local Testbed

`scripts/ha-testbed.sh up` runs Home Assistant in Docker with this repo's `custom_components/securityspy` bind-mounted, so code edits go live after `scripts/ha-testbed.sh restart`. HA state lives in `config/` (gitignored). Open http://localhost:8123 (set `HA_TESTBED_PORT` if that port is taken), finish onboarding, then add the SecuritySpy integration pointed at your NVR. `logs` tails the container; `down` removes it but keeps `config/`.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
