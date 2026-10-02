# Logbook — User Manual

A Home Assistant app (add-on) for logging and tracking incidents and events.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Navigation](#2-navigation)
3. [Log Entries](#3-log-entries)
   - [Viewing entries](#31-viewing-entries)
   - [Creating an entry](#32-creating-an-entry)
   - [Editing an entry](#33-editing-an-entry)
   - [Deleting an entry](#34-deleting-an-entry)
4. [Tags](#4-tags)
   - [Using managed tags](#41-using-managed-tags)
   - [Submitting a new tag](#42-submitting-a-new-tag)
   - [Pending tags on edited entries](#43-pending-tags-on-edited-entries)
5. [Search & Report](#5-search--report)
   - [Basic search](#51-basic-search)
   - [Advanced search](#52-advanced-search)
   - [Exporting a PDF report](#53-exporting-a-pdf-report)
6. [Settings](#6-settings)
   - [Managing lookup tables](#61-managing-lookup-tables)
   - [Managing tags](#62-managing-tags)
   - [Reviewing pending tags](#63-reviewing-pending-tags)
7. [Backup & Restore](#7-backup--restore)
   - [Manual backup](#71-manual-backup)
   - [Restoring a backup](#72-restoring-a-backup)
   - [Automated backup](#73-automated-backup)
8. [Setting Up Automated Backups in Home Assistant](#8-setting-up-automated-backups-in-home-assistant)
9. [Accessing from an HA Dashboard](#9-accessing-from-an-ha-dashboard)

---

## 1. Overview

Logbook is a lightweight web application that runs as a Home Assistant app (add-on). It provides a structured way to record incidents, faults, or any recurring events — with support for categorisation, tagging, full-text search, and PDF reporting.

Data is stored in a SQLite database at `/data/logbook/logbook.db` inside the add-on container. This location persists across add-on restarts and updates but is **deleted if the add-on is uninstalled** — always download a backup before uninstalling.

---

## 2. Navigation

The top navigation bar is available on every page:

| Link | Purpose |
|---|---|
| **Logbook** (logo) | Go to the entries list |
| **Entries** | View all log entries |
| **New Entry** | Create a new log entry |
| **Search & Report** | Search entries and export PDF |
| **Settings** | Manage lookup tables, tags, and backups |
| **Manual** | This page |

On mobile the navigation collapses into a hamburger menu.

---

## 3. Log Entries

### 3.1 Viewing Entries

The **Entries** page lists all log entries sorted by date/time, newest first.

- **Desktop:** displayed as a table with all fields visible.
- **Mobile:** displayed as individual cards, one per entry.

Tags attached to an entry appear as grey badges below the description.

### 3.2 Creating an Entry

Click **New Entry** in the navigation bar. Fill in the form fields:

| Field | Required | Description |
|---|---|---|
| **Username** | Yes | Pre-populated with the logged-in HA user's name when accessed via HA ingress. If accessed via a dashboard card (direct port), the field is blank and must be filled manually. If no HA persons are configured, a free-text input is shown instead of a dropdown. |
| **Date and Time** | Yes | Defaults to the current date and time. |
| **Location** | No | Select from the configured locations list. |
| **Area** | No | Select from the configured areas list. |
| **Category** | No | Select from the configured categories list. |
| **Severity** | No | Select from the configured severities list. |
| **Description** | Yes | Free-text description of the event. Newlines are preserved. |
| **Tags** | No | See [Section 4](#4-tags). |
| **Recurrent event** | No | Check if this is a recurring issue. |

Click **Save Entry** to save, or **Cancel** to go back.

### 3.3 Editing an Entry

On the Entries page or Search results, click **Edit ✏** on any row/card. All fields are pre-filled with the current values and can be changed. Click **Save Changes** when done.

> Pending (unreviewed) tags assigned to the entry are automatically preserved when saving an edit, even though they do not appear as checkboxes.

### 3.4 Deleting an Entry

Click **Delete 🗑** on any row/card. A confirmation dialog will appear before the entry is permanently removed. Deletion also removes all tag associations for that entry.

---

## 4. Tags

Tags are short labels that can be attached to entries for filtering and categorisation.

There are two kinds of tags:

- **Managed tags** — approved by an admin. Appear as checkboxes in the entry form.
- **Pending tags** — submitted by a user, awaiting admin review. Shown with a ⏳ indicator.

### 4.1 Using Managed Tags

In the Tags section of the entry form, tick one or more checkboxes to attach managed tags to the entry. Untick to remove them.

### 4.2 Submitting a New Tag

Type a new tag name in the **New ✏** text field and save the entry. The tag is:

1. Immediately attached to the entry.
2. Added to the **Pending Tags** queue in Settings for admin review.

New tags are lowercased automatically.

### 4.3 Pending Tags on Edited Entries

If an entry has a pending tag and you edit that entry, the pending tag is silently kept even though it has no checkbox. It will remain until an admin approves or rejects it.

---

## 5. Search & Report

### 5.1 Basic Search

Searches the **description** field only. Type a keyword and click **Search**. Results are displayed below in the same desktop/mobile layout as the Entries page.

### 5.2 Advanced Search

Searches across **all text fields** and supports additional filters:

| Filter | Description |
|---|---|
| **Keyword** | Matches against description, username, location, area, category, and severity. |
| **From date / To date** | Restricts results to a date range (inclusive). |
| **Location / Area / Category / Severity** | Exact match dropdowns. |
| **Recurrent** | Filter by recurrent flag: All / Yes / No. |
| **Tag** | Filter entries that have a specific tag attached. |

Leave any filter blank to ignore it. Click **Advanced Search** to run.

### 5.3 Exporting a PDF Report

After running a search (basic or advanced), click **Download PDF for these results**. The PDF contains the same filters applied to the current search and includes all matching entries in a formatted table. The file is named `logbook_YYYYMMDD_HHMM.pdf`.

---

## 6. Settings

### 6.1 Managing Lookup Tables

The Settings page provides editable lists for the four dropdown fields used in entries:

- **Locations**
- **Areas**
- **Categories**
- **Severities**

For each list:

- **Add:** Type a name in the input field and click **Add**.
- **Delete:** Click **✕** next to any item and confirm. Note that deleting a lookup value does not change existing entries that already use it — the value remains in those entries as stored text.

### 6.2 Managing Tags

The **Tags** card works the same way as the lookup tables above. Tags added here become immediately available as checkboxes in the entry form.

Deleting a managed tag does **not** automatically remove it from entries — those entries will continue to display the tag as a badge, but it will no longer appear as a checkbox option.

### 6.3 Reviewing Pending Tags

The **Pending Tags** section (highlighted in yellow) lists all user-submitted tags awaiting review, with their submission date.

**Approve:** Moves the tag from the pending queue into the managed tags list. It will appear as a checkbox in future entry edits.

**Reject:** Opens a dialog with two options:

| Option | Result |
|---|---|
| *No replacement selected* | The tag is removed from all entries it was attached to and deleted. |
| *Select an existing managed tag* | The tag is replaced by the chosen managed tag in all associated entries, then deleted. |
| *Type a new replacement tag name* | A new managed tag is created, the pending tag is replaced by it in all associated entries, then deleted. (New name takes priority over the dropdown if both are filled.) |

---

## 7. Backup & Restore

> **Warning:** Uninstalling the add-on deletes the database. Always download a backup before uninstalling.

### 7.1 Manual Backup

In **Settings → Backup & Restore**, click **⬇ Download Backup**. A ZIP file containing `logbook.db` is downloaded to your browser. The file is named `logbook_backup_YYYYMMDD_HHMM.zip`.

### 7.2 Restoring a Backup

In **Settings → Backup & Restore**, click **Choose File**, select a previously downloaded `.zip` backup, then click **Restore**. A confirmation dialog will appear.

The current database is automatically copied to `logbook.db.pre_restore` before being overwritten, providing a one-level safety net.

### 7.3 Automated Backup

The app exposes a `POST /backup/auto` HTTP endpoint that creates a timestamped backup ZIP in the **Home Assistant share folder** at `/share/logbook/`. This folder is accessible from the HA File editor, Samba or SSH apps.

- Files are named `logbook_backup_YYYYMMDD_HHMM.zip`.
- The 30 most recent backups are kept automatically; older ones are deleted.
- The endpoint accepts **POST only**. A GET request is answered with HTTP 405.

This endpoint is designed to be called from a Home Assistant automation on a schedule. See [Section 8](#8-setting-up-automated-backups-in-home-assistant) for the setup procedure.

---

## 8. Setting Up Automated Backups in Home Assistant

Automated backups are triggered by calling the app's `/backup/auto` endpoint from a HA automation. The steps below use the built-in `rest_command` integration.

### Step 1 — Find the app hostname

Open **Settings → Apps → Logbook**. The **Info** tab shows the app's **Hostname**, of the form `<hash>-logbook`. Home Assistant reaches the app at `http://<hostname>:8099` on its internal network; no port has to be published.

### Step 2 — Add a REST command

Add the following to your `configuration.yaml`:

```yaml
rest_command:
  logbook_backup:
    url: "http://<app hostname>:8099/backup/auto"
    method: POST
```

If you have enabled the optional direct port (see [Section 9](#9-accessing-from-an-ha-dashboard)), `http://localhost:8099/backup/auto` works as well.

Restart Home Assistant (or reload REST commands) after saving.

### Step 3 — Create an automation

In **Settings → Automations & Scenes → Automations**, create a new automation, or add the following YAML directly:

```yaml
alias: Logbook - Daily Backup
description: Creates a daily backup of the Logbook database to /share/logbook/
triggers:
  - trigger: time
    at: "03:00:00"
conditions: []
actions:
  - action: rest_command.logbook_backup
mode: single
```

Adjust the time (`03:00:00`) to your preference. Save the automation.

### Step 4 — Verify

Trigger the automation manually once (**Run** in the automation editor). Open the automation **Trace** to inspect the response from the endpoint:

| Response | Meaning |
|---|---|
| `Backup saved to /share/logbook/logbook_backup_....zip` | Success — check `/share/logbook/` in the File editor. |
| `Share folder not mounted — rebuild or reinstall the app...` | The `/share` mapping is not active. Restart the app; if it persists, reinstall it. |
| `Backup failed: [error message]` | A write or permission error — check the error details. |
| `No database found` | The database does not exist yet (no entries have been saved). |
| `Action rest_command.logbook_backup not found` | The REST command is not loaded. Check `configuration.yaml` and restart or reload. |
| HTTP 405 | The request used GET. Set `method: POST`. |

### Notes

- The backup file is saved to `/share/logbook/` on the HA host, visible from any app that can access the share folder (File editor, Samba, SSH).
- Only the 30 most recent backup files are kept. Older files are deleted automatically each time the endpoint is called.
- The manual download backup in Settings is separate and independent — it streams the ZIP directly to your browser and is not saved to the share folder.

---

## 9. Accessing from an HA Dashboard

### The sidebar panel (default)

The Logbook appears in the Home Assistant sidebar for **all HA users**, administrators and non-administrators alike. It is served through Home Assistant ingress, so it uses HTTPS and your normal HA login, works in the mobile companion apps, and **pre-selects your name** on new entries. This is the recommended way to use it.

Each user can hide the sidebar entry in their own profile settings.

### Optional: the direct port

If you need an address that bypasses ingress, publish the port: **Settings → Apps → Logbook → Configuration → Network**, enter a host port (for example `8099`) and save. You can then open `http://<HA address>:8099`, or add it as a sidebar entry in `configuration.yaml`:

```yaml
panel_iframe:
  logbook:
    title: Logbook
    icon: mdi:notebook-outline
    url: http://<HA address>:8099
    require_admin: false
```

### Notes

- The direct port has **no authentication**. Anyone on the network who can reach it has full access. It is plain HTTP.
- Through the direct port the **Username field is not pre-populated**; users must select or type their name.
- In the author's testing, embedding the direct port in a Webpage card did not display in the iOS companion app. Use the sidebar panel on mobile.
- All other functionality works identically on both paths.
