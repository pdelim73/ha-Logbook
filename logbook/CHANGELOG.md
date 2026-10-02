# Changelog

## 1.2.2

- Add the versioning policy (`docs/versioning.md`).
- Add a GitHub Actions workflow that checks the version and changelog on every push and pull request, and creates the tag and release automatically for a new version.
- No functional change to the app.

## 1.2.1

- Add the MIT license. No functional change.

## 1.2.0

Packaging for publication as a custom app repository, plus security and dependency updates.

- Repository layout: `repository.yaml` at the root, the app lives in `logbook/`.
- Dockerfile uses an explicit multi-arch base image (`ghcr.io/home-assistant/base-python`, Python 3.13, Alpine 3.23). `build.yaml` removed because it is deprecated.
- Supported architectures are now `aarch64` and `amd64`. The deprecated `armv7`, `armhf` and `i386` are not supported.
- `panel_admin: false`: the sidebar panel is visible to non-admin Home Assistant users.
- The direct port `8099` is no longer published by default. It can be enabled under the app's Network settings.
- Dependencies updated to versions without known vulnerabilities (Flask 3.1.3, Werkzeug 3.1.9, requests 2.34.2, reportlab 4.5.1).
- Documentation moved to `docs/` and corrected (the automated backup endpoint is POST-only).

## 1.1.0

- Session secret key is generated on first start and persisted instead of being hardcoded.
- CSRF protection on all state-changing forms.
- Server-side validation of the required user and date/time fields.
- `/backup/auto` accepts POST only (CSRF-exempt so automations can call it).
- Editing an entry no longer silently reassigns it to another user when the original author is not in the Home Assistant person list.
- Bootstrap loaded with Subresource Integrity hashes (5.3.8).
- Failures fetching Home Assistant users are logged.
- Database tables are created in dependency order.

## 1.0.0 - Initial Release

- Log entry creation with all fields
- Basic and advanced search
- PDF report export
- Database backup and restore
- Lookup table management (Locations, Areas, Categories, Severities)
