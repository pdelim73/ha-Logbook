# Installation

How to install the Logbook app from this repository, move data over from an earlier local installation, and keep it updated.

Home Assistant now calls add-ons "apps". This document uses "app" and means the same thing as "add-on".

## Contents

1. [Prerequisites](#1-prerequisites)
2. [Add the repository and install](#2-add-the-repository-and-install)
3. [First start](#3-first-start)
4. [Who can open it](#4-who-can-open-it)
5. [Migrating from a locally installed copy](#5-migrating-from-a-locally-installed-copy)
6. [Scheduled backups (optional)](#6-scheduled-backups-optional)
7. [The optional direct port](#7-the-optional-direct-port)
8. [Updating](#8-updating)
9. [Troubleshooting](#9-troubleshooting)
10. [Uninstalling](#10-uninstalling)

---

## 1. Prerequisites

| Requirement | Detail |
|---|---|
| Home Assistant installation type | **Home Assistant OS** or **Supervised**. Apps need the Supervisor, so Container and Core-only installs cannot run this app |
| Architecture | `aarch64` (Raspberry Pi 4/5 and other 64-bit ARM) or `amd64` (x86-64). 32-bit ARM (`armv7`, `armhf`) and `i386` are not supported |
| Internet access on the Home Assistant host | Installing builds the image on your device. It pulls the base image from `ghcr.io` and Python packages from PyPI, and the web UI loads Bootstrap from `cdn.jsdelivr.net` in your browser. Allow roughly 2 to 10 minutes for the first build on a Raspberry Pi |
| Repository visibility | The GitHub repository must be **public**. Home Assistant clones it anonymously |
| Persons (recommended) | At least one `person` entity under **Settings → People**. It fills the user drop-down on the entry form. Without one the form shows a free-text user field |
| `/share` folder | Present by default on Home Assistant OS and Supervised. Only needed for [scheduled backups](#6-scheduled-backups-optional) |

There are no app options to configure.

## 2. Add the repository and install

1. Open **Settings → Apps → Install app**.
2. Select the three dots (⋮) at the top right, then **Repositories**.
3. Paste `https://github.com/pdelim73/ha-Logbook` and select **Add**, then close the dialog.
4. Reload the page if needed. **Logbook** appears under the repository's name.
5. Open **Logbook**, select **Install** and wait for the build to finish.

Shortcut: the badge at the top of the [README](../README.md) opens the same dialog through My Home Assistant.

## 3. First start

1. Select **Start**. Optionally enable **Start on boot** and **Show in sidebar**.
2. Open the **Log** tab. A healthy start shows Flask listening on port 8099 and no traceback.
3. Open **Logbook** from the sidebar, or select **Open Web UI**.

On the first start the app creates, inside its own persistent `/data` volume:

| Item | Purpose |
|---|---|
| `/data/logbook/logbook.db` | The SQLite database with all tables |
| `/data/logbook/.secret_key` | A random key used to sign session cookies |

Next, open **Settings** inside the Logbook and add your Locations, Areas, Categories, Severities and Tags. The entry form is empty until you do.

## 4. Who can open it

The app sets `panel_admin: false`, so the sidebar entry is available to **all Home Assistant users**, not only administrators. Each user can still hide sidebar items in their own profile.

The Logbook has no roles. Every user who can open it can create, edit and delete any entry, change the lookup lists, and restore or download backups. If that is too permissive for some of your users, do not let them open it.

## 5. Migrating from a locally installed copy

Use this if you previously ran Logbook as a local app from the `/addons` folder.

The repository version is a **different app** to Home Assistant. Its identifier and hostname change (`local_logbook` becomes `<hash>_logbook`) and it has its own empty data volume. Nothing moves across automatically, and anything that referred to the old app (a `rest_command` URL, a `panel_iframe`, a dashboard link) must be updated.

1. In the **old** Logbook open **Settings → Backup & Restore → Download Backup**. Keep the ZIP.
2. Install the new app as described above and start it.
3. In the **new** Logbook open **Settings → Backup & Restore**, choose the ZIP and select **Restore**.
4. Check your entries, tags and lookup lists.
5. Update the references listed above (see [section 6](#6-scheduled-backups-optional)).
6. Stop and uninstall the old local app. Uninstalling deletes its database, so only do this once step 4 looks right.
7. Remove the old copy from the `/addons` folder.

The restore keeps the new app's previous (empty) database as `logbook.db.pre_restore`.

## 6. Scheduled backups (optional)

The app can write a timestamped ZIP of the database to `/share/logbook/` when `POST /backup/auto` is called. It keeps the 30 most recent files. This is separate from Home Assistant's own backups, which include the app's data volume.

### 6.1 Find the app hostname

Open the Logbook app page in **Settings → Apps**. The **Info** tab shows the app's **Hostname**, of the form `<hash>-logbook`. Home Assistant can reach the app at `http://<hostname>:8099` on its internal network. This works without publishing any port.

### 6.2 Add a REST command

In `configuration.yaml`:

```yaml
rest_command:
  logbook_backup:
    url: "http://<app hostname>:8099/backup/auto"
    method: POST
```

If you have [enabled the direct port](#7-the-optional-direct-port), `http://localhost:8099/backup/auto` also works.

Then run **Developer tools → YAML → Check configuration** and restart Home Assistant (or reload REST commands). Confirm that `rest_command.logbook_backup` is listed under **Developer tools → Actions**.

### 6.3 Add an automation

```yaml
alias: Logbook - Daily Backup
description: Writes a Logbook database backup to /share/logbook/
triggers:
  - trigger: time
    at: "03:00:00"
conditions: []
actions:
  - action: rest_command.logbook_backup
mode: single
```

### 6.4 Test it

Run the automation once and open its trace.

| Response | Meaning |
|---|---|
| `Backup saved to /share/logbook/logbook_backup_....zip` | Success |
| `No database found` (HTTP 204) | No entry has been saved yet |
| `Share folder not mounted ...` (HTTP 503) | The `/share` mapping is not active. Restart the app, or reinstall it if that does not help |
| `Backup failed: ...` (HTTP 500) | A write error. The message says why |
| `Action rest_command.logbook_backup not found` | The REST command is not loaded. Check `configuration.yaml` and restart or reload |
| HTTP 405 | The request used GET. The endpoint accepts **POST** only |

The files are visible in the `share` folder from the File editor, Samba or SSH apps.

## 7. The optional direct port

By default the web UI is reachable only through Home Assistant ingress (HTTPS, protected by your HA login). The app can also publish port `8099` on the host:

**Settings → Apps → Logbook → Configuration → Network**, enter a host port (for example `8099`) and save.

Be aware of the trade-offs:

- There is **no authentication** on this port. Anyone on the network who can reach it has full access.
- It is plain HTTP.
- The user field is **not pre-filled**, because the HA user name only arrives through ingress.

Use it only if you need it, for example for a `panel_iframe` entry. Embedding it with a Webpage card did not display in the iOS companion app in the author's setup, while the sidebar panel did work.

## 8. Updating

Updates are delivered by bumping `version` in `logbook/config.yaml` in this repository.

1. Home Assistant refreshes repositories periodically. To force it, open **Settings → Apps → Install app → ⋮ → Check for updates**.
2. When a newer version exists, an **Update** button appears on the Logbook app page. Select it. The image is rebuilt on your device.
3. The app restarts automatically after the update. Your data in `/data` is kept.

Read [logbook/CHANGELOG.md](../logbook/CHANGELOG.md) first. No GitHub release is required for updates to be detected.

## 9. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| The repository will not add | The repository is private, or the URL is wrong. Use the plain HTTPS URL of a public repository |
| Logbook is not listed after adding the repository | Reload the page. Check **Settings → System → Logs → Supervisor** for a message about the repository. Confirm `repository.yaml` is in the repository root |
| Install fails while building | The host needs internet access to `ghcr.io` and PyPI. Read the Supervisor log for the failing step. Check the host architecture is `aarch64` or `amd64` |
| The app starts but the panel shows a blank page or error | Open the **Log** tab. Make sure the app has been restarted after an update |
| A non-admin user does not see the panel | They may have hidden it in their sidebar settings. Also check they are signed in with their own account |
| Form actions return "403 Forbidden" | The page was open for a long time or the session cookie was cleared. Reload the page and retry |
| User field is empty or shows the login name | The name comes from the HA ingress header and is matched against `person` friendly names. Add the person under **Settings → People**, or pick the name manually |
| `rest_command.logbook_backup` not found | See [section 6.4](#64-test-it) |
| HTTP 405 from `/backup/auto` | Change the REST command to `method: POST` |

## 10. Uninstalling

Uninstalling the app **deletes its database** (`/data/logbook/`). First download a backup in **Settings → Backup & Restore**. Backups written to `/share/logbook/` by the scheduled job stay on the host until you delete them.

To remove the repository as well, use **Settings → Apps → Install app → ⋮ → Repositories** and delete the entry.
