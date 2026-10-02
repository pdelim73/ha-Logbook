# Technical design

Architecture, decisions, data model, security model and verification status of the Logbook app.

## Contents

1. [Purpose and scope](#1-purpose-and-scope)
2. [Architecture](#2-architecture)
3. [Design decisions and rejected alternatives](#3-design-decisions-and-rejected-alternatives)
4. [Coexistence with Home Assistant](#4-coexistence-with-home-assistant)
5. [Data model](#5-data-model)
6. [Security model](#6-security-model)
7. [Application internals](#7-application-internals)
8. [Build and deployment](#8-build-and-deployment)
9. [Verification performed](#9-verification-performed)
10. [Known limitations](#10-known-limitations)

---

## 1. Purpose and scope

A small multi-user logbook for a household or small team: people record incidents with structured fields and tags, search them, and export PDFs. It runs as a Home Assistant app (container) and does not create any Home Assistant entities, services or integrations.

It is unrelated to Home Assistant's built-in **Logbook** panel, which is an automatic activity history. This app stores entries that people write.

| Layer | Technology |
|---|---|
| Container base | `ghcr.io/home-assistant/base-python:3.13-alpine3.23` (multi-arch, s6 `/init` entrypoint) |
| Web framework | Flask 3.1.3 on Werkzeug 3.1.9, Jinja2 templates |
| Database | SQLite through the standard library `sqlite3` |
| PDF | ReportLab 4.5.1 |
| HA API client | requests 2.34.2 |
| Front end | Bootstrap 5.3.8 from jsDelivr with Subresource Integrity hashes |

## 2. Architecture

```
Browser ── HTTPS ──> Home Assistant ──> ingress proxy ──> [ Logbook container ]
 (HA login)          (authenticates)    adds X-Ingress-Path,    Flask on :8099
                                         X-Remote-User-Name       │
                                                                  ├─ /data/logbook/logbook.db   (persistent volume)
                                                                  ├─ /data/logbook/.secret_key
                                                                  ├─ /share/logbook/*.zip       (mapped HA share, read/write)
                                                                  └─ GET supervisor/core/api/states  (Bearer SUPERVISOR_TOKEN)

Optional:  LAN ── HTTP :8099 ─────────────────────────────────> [ Logbook container ]   (no authentication)
Optional:  HA automation ── POST /backup/auto ───────────────> [ Logbook container ]
```

Repository layout:

```
repository.yaml            Repository metadata
logbook/config.yaml        App manifest
logbook/Dockerfile         Image build
logbook/run.sh             Entrypoint script
logbook/app/app.py         All application code
logbook/app/templates/     Jinja2 templates (base, index, new/edit entry, search, settings, manual, macros)
logbook/app/requirements.txt
```

### Manifest (`logbook/config.yaml`)

| Key | Value | Why |
|---|---|---|
| `arch` | `aarch64`, `amd64` | The architectures Home Assistant currently supports for apps |
| `ingress` / `ingress_port` | `true` / `8099` | Serve the UI behind Home Assistant's authenticated reverse proxy |
| `panel_icon` / `panel_title` | `mdi:notebook-outline` / `Logbook` | Sidebar entry |
| `panel_admin` | `false` | Default is `true` (admins only). `false` makes the sidebar entry available to every HA user |
| `ports` | `8099/tcp: null` | Direct port is **not** published unless the user sets a host port in the Network settings |
| `homeassistant_api` | `true` | Injects `SUPERVISOR_TOKEN` so the app can read `person` entities |
| `map` | `share:rw` | Destination of scheduled backups |
| `init` | `false` | The base image already provides s6 as PID 1 |
| `options` / `schema` | empty | No user-visible configuration |

## 3. Design decisions and rejected alternatives

### 3.1 How the UI is delivered

| Option | Verdict | Reason |
|---|---|---|
| **Ingress** (chosen) | Used | HTTPS and Home Assistant authentication for free, no published port, receives the user name header, works in the mobile apps' sidebar |
| Direct host port | Optional only | No authentication, plain HTTP, no user header. Kept opt-in because some users want an address that bypasses ingress |
| Webpage (iframe) card or `panel_iframe` pointing at the direct port | Rejected as the primary path | Needs the unauthenticated port. In the author's testing the Webpage card did not display in the iOS companion app. The cause was not investigated further |
| In-app login with its own user table | Rejected for now | Duplicates what Home Assistant already provides and adds credential storage. It would only be justified if the app had to be reachable without Home Assistant |
| Custom integration with entities and a Lovelace card | Rejected | A logbook of free text records is not entity state. A web UI is the natural fit |

An earlier revision of these docs said that ingress is restricted to administrators by the Supervisor. That was wrong: visibility of the sidebar entry is controlled by `panel_admin`, which defaults to `true`.

### 3.2 Storage

SQLite in the app's `/data` volume. One writer at a time, a few hundred to a few hundred thousand rows, no network service to run, a single file to back up. A client/server database was rejected as unnecessary operational weight. Free-text copies of lookup values are stored on each entry (see section 5) so deleting a lookup item never alters history.

### 3.3 Web framework and server

Flask with server-rendered Jinja2 pages and Bootstrap. No JavaScript build step, one Python file for the logic. The built-in Flask server is used (`app.run`). A WSGI server such as gunicorn was rejected for now: the load is a handful of occasional users, and one fewer dependency keeps the image small.

### 3.4 Base image

A single explicit `FROM ghcr.io/home-assistant/base-python:<python>-alpine<version>`. The previous per-architecture `build.yaml` with a `BUILD_FROM` argument is deprecated, and the Supervisor no longer supplies `BUILD_FROM` by default. The arch-less image is a multi-arch manifest list covering `amd64` and `arm64`, so one line serves both supported architectures. The image is built on the user's device (no `image:` key), which avoids running a container registry pipeline at the cost of a few minutes on first install and on each update.

### 3.5 Tag governance

Anyone can type a new tag, but it enters a `pending_tags` queue for review. It is attached to the entry immediately so the author sees it, and an administrator can later approve it, or reject it and optionally reassign every affected entry to another tag. This keeps the managed vocabulary clean without blocking people.

## 4. Coexistence with Home Assistant

The app is a separate container and is designed to be a passive neighbour.

| Concern | How it is handled |
|---|---|
| Writes to Home Assistant | None. The only call is `GET /core/api/states` through the Supervisor proxy, read-only, to list `person.*` friendly names. Failure is logged and the form falls back to a text field |
| Credentials | The app uses only the Supervisor-injected `SUPERVISOR_TOKEN`. It has no user credentials, and no token is stored |
| Home Assistant configuration | Nothing is written to `configuration.yaml`, the entity registry or the recorder database |
| Network | Port `8099` exists only inside the container network unless the user publishes it. No clash with another app unless the user chooses a conflicting host port |
| Filesystem | Reads and writes `/data` (private to the app) and `/share/logbook/` (a subfolder of the shared mount). Nothing else is mapped |
| Home Assistant backups | The app's `/data` volume is included in Home Assistant's own backups. The scheduled ZIPs in `/share/logbook/` are an independent second copy |
| Identity of the app | Installed from a repository, the app gets a repository-specific slug and hostname. It does not collide with, and does not share data with, a copy installed from the local `/addons` folder |

## 5. Data model

Database: `/data/logbook/logbook.db`, created idempotently by `init_db()` at start (`CREATE TABLE IF NOT EXISTS`). Foreign keys are enabled per connection.

### Lookup tables

`locations`, `areas`, `categories`, `severities`, `tags`: `id INTEGER PRIMARY KEY AUTOINCREMENT`, `name TEXT UNIQUE NOT NULL`.

`pending_tags`: the same, plus `submitted_at TEXT DEFAULT CURRENT_TIMESTAMP`.

### `log_entries`

| Column | Type | Source | Null/empty handling |
|---|---|---|---|
| `id` | integer PK | autoincrement | |
| `username` | text, NOT NULL | Form `username` (select of HA `person` friendly names, or free text). Pre-selected from the `X-Remote-User-Name` ingress header | Required, rejected server-side if empty after trimming |
| `entry_datetime` | text, NOT NULL | Form `datetime-local`, stored as `YYYY-MM-DDTHH:MM` | Required. Displayed as `DD-MM-YYYY HH:MM`. Date filters compare strings, which sorts correctly in this format |
| `location`, `area`, `category`, `severity` | text | Form selects of lookup values | Empty string when "none" is chosen. Shown as an em dash. Stored as a copy of the name, not a foreign key |
| `description` | text | Form textarea | Trimmed. Rendered with `white-space: pre-wrap` and HTML-escaped |
| `recurrent` | integer 0/1 | Checkbox | Absent means 0 |
| `created_at` | text | `CURRENT_TIMESTAMP` (UTC) | |

### `log_entry_tags`

`(entry_id → log_entries.id ON DELETE CASCADE, tag_name TEXT, PRIMARY KEY (entry_id, tag_name))`. `tag_name` is deliberately **not** a foreign key: an entry may carry a pending tag, or a tag that was later removed from the managed list.

`log_entries` is created before `log_entry_tags` so the reference points at an existing table.

### Files

| Path | Content |
|---|---|
| `/data/logbook/logbook.db` | Database |
| `/data/logbook/.secret_key` | 64 hex characters, generated on first start |
| `/data/logbook/logbook.db.pre_restore` | Copy of the database taken just before a restore overwrites it |
| `/share/logbook/logbook_backup_YYYYMMDD_HHMM.zip` | Scheduled backups, newest 30 kept |

## 6. Security model

**Authentication.** None in the app. The identity boundary is Home Assistant: ingress only forwards requests from authenticated HA sessions. When the optional direct port is enabled, that boundary is gone.

**Authorisation.** None. Any user who can reach the app can do everything: edit and delete any entry, manage lookups and tags, download and restore backups. `panel_admin: false` widens the set of people who can reach it from administrators to all HA users, which is a deliberate trade-off.

**Session secret.** Flask signs its session cookie with a random key generated on first start and stored in `/data/logbook/.secret_key`. It is not part of database backups. Replacing it only invalidates open browser sessions.

**CSRF.** A per-session random token is placed in every `POST` form and checked in a `before_request` hook, which answers `403` on mismatch. `backup_auto` is exempt because it is called by automations that have no browser session.

**Scheduled backup endpoint.** `POST /backup/auto` is unauthenticated by design and reachable by anything that can reach the app. Its only effect is writing a ZIP of the database under `/share/logbook/` and pruning old ones. It never returns the data.

**Injection.** All values reach SQL as bound parameters. The only interpolated identifiers are table names checked against a fixed whitelist (`ALLOWED_TABLES`) and a fixed list of four filter columns. Output is HTML-escaped by Jinja2 autoescaping. The PDF builder escapes text before converting newlines for ReportLab's mini-markup.

**Uploads.** Restore accepts a `.zip` and extracts only the single member `logbook.db` to a fixed directory, so path traversal in member names is not possible. It does not validate that the file is a usable SQLite database.

**Front-end supply chain.** Bootstrap CSS and JS are loaded from jsDelivr with `integrity` and `crossorigin` attributes. A changed file is refused by the browser.

**Dependencies.** Pinned in `requirements.txt` and audited with `pip-audit` (see section 9).

**No secrets in the repository.** The code contains no keys, tokens, addresses or credentials. Secrets are generated or injected at runtime.

## 7. Application internals

`ReverseProxied` (WSGI middleware) reads `X-Ingress-Path` and moves it into `SCRIPT_NAME`, so `url_for` produces links that work under the ingress prefix.

### Routes

| Route | Methods | Purpose |
|---|---|---|
| `/` | GET | All entries (table on desktop, cards on mobile) |
| `/new` | GET, POST | Create an entry |
| `/entry/<id>/edit` | GET, POST | Edit an entry |
| `/entry/<id>/delete` | POST | Delete an entry (tags cascade) |
| `/search` | GET | Basic or advanced search |
| `/report` | GET | PDF of the current search filters |
| `/settings` | GET | Lookup lists, pending tags, backup and restore |
| `/settings/add/<table>`, `/settings/delete/<table>/<id>` | POST | Maintain whitelisted lookup tables |
| `/settings/pending-tags/approve/<id>`, `.../reject/<id>` | POST | Tag review |
| `/backup` | GET | Download a ZIP containing `logbook.db` |
| `/backup/auto` | POST | Write a ZIP to `/share/logbook/`, keep newest 30 |
| `/restore` | POST | Replace the database from an uploaded ZIP |
| `/manual` | GET | In-app user manual |

### Workflows

- **Tags on save.** Checked managed tags plus one optional free-text tag. A new name not in `tags` is inserted into `pending_tags` and attached. On edit, tags that are still pending have no checkbox, so they are read back first and re-attached so that saving does not silently drop them.
- **Tag rejection.** Optionally copies all associations to a replacement tag with `INSERT OR IGNORE ... SELECT` (so entries that already have both do not collide), then removes the old tag everywhere.
- **Search and report share one query builder.** The PDF always matches what the search page shows. Basic mode matches the description. Advanced mode matches six text columns and adds filters for location, area, category, severity, recurrence, date range and tag.
- **Edit form and unknown authors.** The user drop-down is built from the current HA persons. If the entry's author is not in that list, that name is added and pre-selected so saving cannot reassign the entry to the first person in the list.
- **Restore.** Copies the current database to `logbook.db.pre_restore`, then extracts the uploaded `logbook.db`.
- **Scheduled backup.** Refuses to write unless `/share` is a real mount (`os.path.ismount`), so a missing mapping fails loudly rather than writing into the container's own filesystem.

## 8. Build and deployment

1. The Supervisor clones the repository, reads `repository.yaml`, and finds `logbook/config.yaml`.
2. On install, it builds `logbook/Dockerfile` on the device: base image, `pip install -r requirements.txt`, copy of `app/` and `run.sh`.
3. `run.sh` (shebang `with-contenv bashio`) creates `/data/logbook` and runs `python3 /app/app.py`.
4. `app.py` loads or creates the secret key at import, then `init_db()` creates the schema, then Flask listens on `0.0.0.0:8099`.

No compiler is installed in the image: every pinned dependency has a prebuilt musl wheel for CPython 3.13 on both architectures (section 9).

Releasing a change: edit, bump `version` in `logbook/config.yaml`, update `logbook/CHANGELOG.md` and the docs, commit and push to `main`. Home Assistant detects the new version on its next repository refresh.

## 9. Verification performed

| Check | Result |
|---|---|
| Functional test of the Flask app (41 assertions, Flask test client against a copy with data paths redirected to a temporary folder) | 41/41 passed |
| `pip-audit` on the pinned requirements | No known vulnerabilities. The previously pinned Flask 3.0.3, Werkzeug 3.0.6 and requests 2.32.3 had 12 findings, which is why they were upgraded |
| `pip download --only-binary` for `musllinux_1_2_x86_64` and `musllinux_1_2_aarch64`, CPython 3.13 | All requirements resolve to wheels on both, so the image needs no compiler |
| Base image `base-python:3.13-alpine3.23` | Present in the registry as a manifest list with `amd64` and `arm64`. Entrypoint `/init` as expected |
| `docker build` of `logbook/` on amd64 (Docker Desktop, Windows) | Builds; pip compiled no wheels. Python 3.13.15 with Flask 3.1.3, Werkzeug 3.1.9, reportlab 4.5.1, requests 2.34.2, Pillow 12.3.0 |
| Image contents | `/usr/bin/with-contenv` (symlink to `/command/with-contenv`) and `/usr/bin/bashio` resolve. `run.sh` shebang has LF line endings |
| Container started with the default s6 `/init`, named volumes on `/data` and `/share` | Starts and serves on port 8099 |
| HTTP smoke test inside the container (20 checks) | 20/20 passed, including `POST /backup/auto` writing a ZIP to the mounted `/share/logbook`, GET refused with 405 and CSRF rejection |
| Full functional test (41 assertions) run inside the built image | 41/41 passed |
| Container restart | Data kept and the secret key unchanged (same SHA-256 before and after) |
| `SUPERVISOR_TOKEN` pass-through: container started with a dummy token on a network with a fake supervisor answering `GET /core/api/states` only for the correct Bearer token | The token reaches the Python process through `with-contenv`; the app sent the correct header (one `auth=OK`, no `auth=BAD`) and the user drop-down listed the fake persons and no other entities. A control container without a token showed the plain text field |
| `docker buildx build --platform linux/arm64` (QEMU emulation) | Builds with no wheel compilation. `uname -m` is `aarch64`, the app's imports succeed, `with-contenv` present |
| Repository metadata against the Home Assistant developer documentation | `repository.yaml` with `name`; one app folder with `config.yaml`; `panel_admin`, `ports: null`, `ports_description`, `url` are documented keys |
| Sweep of every commit's content, author and committer metadata for private IP ranges, e-mail addresses other than the GitHub noreply address, serial and MAC patterns, secret-like strings and local paths | Run before each push. Result is reported with the release |

The functional test covers: page rendering, CSRF rejection without a token, lookup and tag creation, entry create/edit/delete with tag cascade, validation of required fields, pending-tag preservation and rejection with replacement, the edit-form author regression, HTML escaping, basic and advanced search, PDF generation, manual backup, `/backup/auto` (GET refused, missing mount refused, success without a CSRF token), restore (good and invalid ZIPs, pre-restore snapshot), ingress prefix handling and secret-key persistence.

**Not verified** (no running Home Assistant was available):

- Starting and exercising the app on arm64. Only the arm64 build and the import check were run, under emulation, not on a Raspberry Pi.
- The real Supervisor API. The token path was tested against a stand-in; the real `/core/api/states` response and its authorisation were not.
- Behaviour of `panel_admin: false` for a real non-admin account.
- The hostname shown on the app's Info tab, and name resolution of that hostname from Home Assistant Core.
- The update flow after a version bump.
- The mobile companion apps.

The automated test script is a scratch harness and is not part of this repository.

## 10. Known limitations

- **No roles.** Everyone with access has full rights. There is no ownership of entries and no audit trail of who edited what.
- **Direct port is unauthenticated.** If enabled, treat the network as the access control.
- **Pre-selected user.** The ingress header carries the HA login name, while the drop-down lists person friendly names. When they differ, the login name appears as an extra option instead of matching the person.
- **Flask development server.** Adequate for a few users, not hardened for heavy or hostile traffic.
- **Hot backups.** Home Assistant's own backup copies the database file while the app may be running. The scheduled ZIP is a straight file copy as well, not a SQLite online backup. A write at exactly that moment could in theory produce an inconsistent copy.
- **Restore trusts the uploaded database.** Only the member name is checked.
- **Free-text lookup snapshots.** Renaming a lookup value is not supported; it would need a migration of existing entries.
- **Images are built on the device.** First install and every update take a few minutes on small hardware and need internet access.
- **Bootstrap comes from a CDN.** The browser needs internet access for the UI to be styled.
- **No automated tests in the repository.**
