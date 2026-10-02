# Logbook for Home Assistant

A Home Assistant app (add-on) for recording incidents, faults and recurring events. Entries carry a user, date and time, location, area, category, severity, description and tags. They can be searched and exported as a PDF report.

[![Add this repository to your Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fpdelim73%2Fha-Logbook)

## At a glance

| | |
|---|---|
| Type | Home Assistant app (formerly "add-on"), installed from a custom repository |
| Requires | Home Assistant OS or Supervised (needs the Supervisor) |
| Architectures | `aarch64`, `amd64` |
| UI | Sidebar panel through Home Assistant ingress (HTTPS, uses your HA login) |
| Who can open it | Every Home Assistant user, admin or not (`panel_admin: false`) |
| Storage | SQLite database in the app's persistent `/data` volume |
| Backups | Manual ZIP download/restore in the UI, plus an optional scheduled backup to `/share/logbook/` |
| Reports | PDF export of any search result |
| Stack | Python 3.13, Flask, SQLite, ReportLab, Bootstrap 5 |
| Configuration | None. There are no app options to set |

## Install

1. In Home Assistant open **Settings → Apps → Install app → ⋮ → Repositories**.
2. Add `https://github.com/pdelim73/ha-Logbook` and select **Add**.
3. Install **Logbook**, start it, and open it from the sidebar.

Full steps, including migrating from a locally installed copy: [docs/installation.md](docs/installation.md).

## Documentation

| Document | Contents |
|---|---|
| [docs/installation.md](docs/installation.md) | Prerequisites, install, first start, migration, scheduled backups, updating, troubleshooting, uninstall |
| [docs/user-manual.md](docs/user-manual.md) | Using the Logbook: entries, tags, search, reports, settings, backup and restore |
| [docs/technical-design.md](docs/technical-design.md) | Architecture, design decisions and rejected alternatives, data model, security model, verification, limitations |
| [logbook/CHANGELOG.md](logbook/CHANGELOG.md) | Version history |

## Security note

The app has no login of its own. Access control is whatever Home Assistant provides through ingress, and every user who can open the panel can create, edit and delete all entries and change settings. Do not publish the optional direct port (`8099`) beyond a network you trust. See [docs/technical-design.md](docs/technical-design.md#6-security-model).

## Repository layout

```
repository.yaml        Repository metadata read by Home Assistant
logbook/               The app: config.yaml, Dockerfile, run.sh, app/ (Flask code and templates)
docs/                  Documentation
```
