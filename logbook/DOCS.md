# Logbook

Record incidents and events with a user, date and time, location, area, category, severity, description and tags. Search them and export a PDF report.

## First steps

1. Start the app and open **Logbook** in the sidebar.
2. Open **Settings** inside the Logbook and add your Locations, Areas, Categories, Severities and Tags.
3. Create entries with **New Entry**.

There is nothing to configure on this page.

## Access

The sidebar entry is available to every Home Assistant user. The Logbook has no roles: everyone who can open it can create, edit and delete all entries and change settings.

The direct port `8099` is not published by default. If you enable it under **Network**, it has no authentication.

## Backups

- **Settings → Backup & Restore** downloads or restores a ZIP of the database.
- Uninstalling the app deletes its database. Download a backup first.
- A scheduled backup to `/share/logbook/` can be set up with a `rest_command` that sends `POST` to `http://<app hostname>:8099/backup/auto`. The hostname is shown on the **Info** tab.

## More

Full documentation: https://github.com/pdelim73/ha-Logbook/tree/main/docs
