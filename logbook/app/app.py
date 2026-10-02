import os, io, glob, html, sqlite3, zipfile, shutil, secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, abort

import requests as req
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import cm

app = Flask(__name__)

# ── Secret key ─────────────────────────────────────────────────────────────────
# Auto-generated on first run and persisted so flash messages survive restarts.
_KEY_FILE = '/data/logbook/.secret_key'

def _load_or_create_secret_key():
    os.makedirs('/data/logbook', exist_ok=True)
    try:
        key = open(_KEY_FILE).read().strip()
        if key:
            return key
    except FileNotFoundError:
        pass
    key = secrets.token_hex(32)
    with open(_KEY_FILE, 'w') as fh:
        fh.write(key)
    return key

app.secret_key = _load_or_create_secret_key()

DB_PATH          = "/data/logbook/logbook.db"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
HA_API           = "http://supervisor/core/api"
ALLOWED_TABLES   = ['locations', 'areas', 'categories', 'severities', 'tags']

# Endpoints bypassing browser CSRF checks (called programmatically by automations).
_CSRF_EXEMPT = {'backup_auto'}


# ── CSRF protection ────────────────────────────────────────────────────────────
def _csrf_token():
    """Return (and lazily create) the per-session CSRF token."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

app.jinja_env.globals['csrf_token'] = _csrf_token

@app.before_request
def _csrf_protect():
    if request.method == 'POST' and request.endpoint not in _CSRF_EXEMPT:
        token = session.get('_csrf_token')
        form_token = request.form.get('_csrf_token')
        if not token or token != form_token:
            abort(403)


# ── Ingress path middleware ────────────────────────────────────────────────────
# Makes url_for() work correctly behind HA Ingress proxy
class ReverseProxied:
    def __init__(self, application):
        self.app = application

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_INGRESS_PATH', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ.get('PATH_INFO', '')
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]
        return self.app(environ, start_response)

app.wsgi_app = ReverseProxied(app.wsgi_app)


@app.template_filter('fmt_dt')
def fmt_dt(s):
    """Reformat 'YYYY-MM-DDTHH:MM' → 'DD-MM-YYYY HH:MM' for display."""
    if not s or len(s) < 16:
        return s or ''
    try:
        return datetime.strptime(s[:16], '%Y-%m-%dT%H:%M').strftime('%d-%m-%Y %H:%M')
    except ValueError:
        return s[:16]


# ── Database ───────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    os.makedirs('/data/logbook', exist_ok=True)
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS locations
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS areas
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS categories
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS severities
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)''')
    # Managed tags (approved, curated list)
    conn.execute('''CREATE TABLE IF NOT EXISTS tags
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)''')
    # Pending tags submitted by users (awaiting admin review)
    conn.execute('''CREATE TABLE IF NOT EXISTS pending_tags
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     name TEXT UNIQUE NOT NULL,
                     submitted_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    # log_entries must be created before log_entry_tags (FK reference)
    conn.execute('''CREATE TABLE IF NOT EXISTS log_entries
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     username TEXT NOT NULL,
                     entry_datetime TEXT NOT NULL,
                     location TEXT,
                     area TEXT,
                     category TEXT,
                     severity TEXT,
                     description TEXT,
                     recurrent INTEGER DEFAULT 0,
                     created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    # Many-to-many: log entries ↔ tags
    conn.execute('''CREATE TABLE IF NOT EXISTS log_entry_tags
                    (entry_id INTEGER NOT NULL,
                     tag_name TEXT NOT NULL,
                     PRIMARY KEY (entry_id, tag_name),
                     FOREIGN KEY (entry_id) REFERENCES log_entries(id) ON DELETE CASCADE)''')
    conn.commit()
    conn.close()


def get_lookup_context():
    """Fetch all lookup-table data in a single connection for template rendering."""
    conn = get_db()
    ctx = {
        'locations':  conn.execute('SELECT * FROM locations  ORDER BY name').fetchall(),
        'areas':      conn.execute('SELECT * FROM areas      ORDER BY name').fetchall(),
        'categories': conn.execute('SELECT * FROM categories ORDER BY name').fetchall(),
        'severities': conn.execute('SELECT * FROM severities ORDER BY name').fetchall(),
        'tags':       conn.execute('SELECT * FROM tags       ORDER BY name').fetchall(),
    }
    conn.close()
    return ctx


def get_tags_for_entry(conn, entry_id):
    """Return list of tag names attached to a log entry."""
    return [
        r['tag_name']
        for r in conn.execute(
            'SELECT tag_name FROM log_entry_tags WHERE entry_id = ? ORDER BY tag_name',
            (entry_id,)
        ).fetchall()
    ]


def save_tags_for_entry(conn, entry_id, selected_tags, new_tag_raw):
    """
    Persist tags for an entry.
    - selected_tags: list of managed tag names chosen from checkboxes
    - new_tag_raw:   free-text tag typed by the user (may be empty)
    New free-text tags go into pending_tags for review.
    """
    # Preserve any tags that are still awaiting admin review —
    # they have no checkbox in the form so would otherwise be lost on save.
    pending_entry_tags = [
        r['tag_name']
        for r in conn.execute(
            '''SELECT tag_name FROM log_entry_tags
               WHERE entry_id = ?
               AND tag_name IN (SELECT name FROM pending_tags)''',
            (entry_id,)
        ).fetchall()
    ]

    conn.execute('DELETE FROM log_entry_tags WHERE entry_id = ?', (entry_id,))
    all_tags = [t.strip() for t in selected_tags if t.strip()]

    # Re-add the preserved pending tags
    for tag in pending_entry_tags:
        if tag not in all_tags:
            all_tags.append(tag)

    new_tag = new_tag_raw.strip().lower()
    if new_tag:
        if not conn.execute('SELECT 1 FROM tags WHERE name = ?', (new_tag,)).fetchone():
            conn.execute('INSERT OR IGNORE INTO pending_tags (name) VALUES (?)', (new_tag,))
        if new_tag not in all_tags:
            all_tags.append(new_tag)

    for tag in all_tags:
        conn.execute(
            'INSERT OR IGNORE INTO log_entry_tags (entry_id, tag_name) VALUES (?, ?)',
            (entry_id, tag)
        )


def build_search_query(args, mode):
    """Build a parameterised SQL query from request args for search and report."""
    sql    = 'SELECT * FROM log_entries WHERE 1=1'
    params = []

    query = args.get('q', '').strip()
    if query:
        if mode == 'basic':
            sql += ' AND description LIKE ?'
            params.append(f'%{query}%')
        else:
            sql += (' AND (description LIKE ? OR username LIKE ?'
                    ' OR location LIKE ? OR area LIKE ?'
                    ' OR category LIKE ? OR severity LIKE ?)')
            params.extend([f'%{query}%'] * 6)

    if mode == 'advanced':
        for field in ['location', 'area', 'category', 'severity']:
            val = args.get(field, '').strip()
            if val:
                sql += f' AND {field} = ?'
                params.append(val)

        recurrent_val = args.get('recurrent', '')
        if recurrent_val == '1':
            sql += ' AND recurrent = 1'
        elif recurrent_val == '0':
            sql += ' AND recurrent = 0'

        date_from = args.get('date_from', '')
        date_to   = args.get('date_to', '')
        if date_from:
            sql += ' AND entry_datetime >= ?'
            params.append(date_from)
        if date_to:
            sql += ' AND entry_datetime <= ?'
            params.append(date_to + 'T23:59')

        tag_filter = args.get('tag', '').strip()
        if tag_filter:
            sql += ' AND id IN (SELECT entry_id FROM log_entry_tags WHERE tag_name = ?)'
            params.append(tag_filter)

    sql += ' ORDER BY entry_datetime DESC'
    return sql, params


# ── Home Assistant users ───────────────────────────────────────────────────────
def get_ha_users():
    """Get user names from HA 'person' entities via the Supervisor API."""
    if not SUPERVISOR_TOKEN:
        return []
    headers = {'Authorization': f'Bearer {SUPERVISOR_TOKEN}'}
    try:
        r = req.get(f'{HA_API}/states', headers=headers, timeout=5)
        if r.ok:
            return sorted(
                state.get('attributes', {}).get('friendly_name', state['entity_id'])
                for state in r.json()
                if state['entity_id'].startswith('person.')
            )
    except Exception as e:
        app.logger.warning("HA user fetch failed: %s", e)
    return []


# ── Routes: Entries ────────────────────────────────────────────────────────────
@app.route('/')
def index():
    conn = get_db()
    entries = conn.execute('SELECT * FROM log_entries ORDER BY entry_datetime DESC').fetchall()
    tag_map = {}
    for row in conn.execute('SELECT entry_id, tag_name FROM log_entry_tags ORDER BY tag_name'):
        tag_map.setdefault(row['entry_id'], []).append(row['tag_name'])
    conn.close()
    return render_template('index.html', entries=entries, tag_map=tag_map)


@app.route('/new', methods=['GET', 'POST'])
def new_entry():
    if request.method == 'POST':
        username       = request.form.get('username', '').strip()
        entry_datetime = request.form.get('entry_datetime', '').strip()
        if not username or not entry_datetime:
            flash('Username and Date/Time are required.', 'danger')
            return render_template('new_entry.html',
                                   ha_users=get_ha_users(),
                                   current_user=request.headers.get('X-Remote-User-Name', ''),
                                   now=entry_datetime or datetime.now().strftime('%Y-%m-%dT%H:%M'),
                                   **get_lookup_context())
        conn = get_db()
        cur = conn.execute(
            '''INSERT INTO log_entries
               (username, entry_datetime, location, area, category,
                severity, description, recurrent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (username,
             entry_datetime,
             request.form.get('location', '').strip(),
             request.form.get('area', '').strip(),
             request.form.get('category', '').strip(),
             request.form.get('severity', '').strip(),
             request.form.get('description', '').strip(),
             1 if request.form.get('recurrent') else 0))
        save_tags_for_entry(conn, cur.lastrowid,
                            request.form.getlist('tags'),
                            request.form.get('new_tag', '').strip())
        conn.commit()
        conn.close()
        flash('Entry saved successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('new_entry.html',
                           ha_users=get_ha_users(),
                           current_user=request.headers.get('X-Remote-User-Name', ''),
                           now=datetime.now().strftime('%Y-%m-%dT%H:%M'),
                           **get_lookup_context())


@app.route('/entry/<int:entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(entry_id):
    conn = get_db()
    entry = conn.execute('SELECT * FROM log_entries WHERE id = ?', (entry_id,)).fetchone()
    if entry is None:
        conn.close()
        flash('Entry not found.', 'danger')
        return redirect(url_for('index'))
    entry_tags = get_tags_for_entry(conn, entry_id)
    conn.close()

    if request.method == 'POST':
        username       = request.form.get('username', '').strip()
        entry_datetime = request.form.get('entry_datetime', '').strip()
        if not username or not entry_datetime:
            flash('Username and Date/Time are required.', 'danger')
            return render_template('edit_entry.html',
                                   entry=entry,
                                   entry_tags=entry_tags,
                                   ha_users=get_ha_users(),
                                   **get_lookup_context())
        conn = get_db()
        conn.execute(
            '''UPDATE log_entries
               SET username=?, entry_datetime=?, location=?, area=?,
                   category=?, severity=?, description=?, recurrent=?
               WHERE id=?''',
            (username,
             entry_datetime,
             request.form.get('location', '').strip(),
             request.form.get('area', '').strip(),
             request.form.get('category', '').strip(),
             request.form.get('severity', '').strip(),
             request.form.get('description', '').strip(),
             1 if request.form.get('recurrent') else 0,
             entry_id))
        save_tags_for_entry(conn, entry_id,
                            request.form.getlist('tags'),
                            request.form.get('new_tag', '').strip())
        conn.commit()
        conn.close()
        flash('Entry updated successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('edit_entry.html',
                           entry=entry,
                           entry_tags=entry_tags,
                           ha_users=get_ha_users(),
                           **get_lookup_context())


@app.route('/entry/<int:entry_id>/delete', methods=['POST'])
def delete_entry(entry_id):
    conn = get_db()
    conn.execute('DELETE FROM log_entries WHERE id = ?', (entry_id,))
    conn.commit()
    conn.close()
    flash('Entry deleted.', 'info')
    return redirect(url_for('index'))


# ── Routes: Search ─────────────────────────────────────────────────────────────
@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    mode  = request.args.get('mode', 'basic')
    results, tag_map = [], {}

    if query or mode == 'advanced':
        conn = get_db()
        sql, params = build_search_query(request.args, mode)
        results = conn.execute(sql, params).fetchall()

        if results:
            ids = [e['id'] for e in results]
            placeholders = ','.join('?' * len(ids))
            for row in conn.execute(
                f'SELECT entry_id, tag_name FROM log_entry_tags'
                f' WHERE entry_id IN ({placeholders}) ORDER BY tag_name',
                ids
            ):
                tag_map.setdefault(row['entry_id'], []).append(row['tag_name'])
        conn.close()

    return render_template('search.html',
                           results=results,
                           query=query,
                           mode=mode,
                           tag_map=tag_map,
                           tag_filter=request.args.get('tag', ''),
                           **get_lookup_context())


# ── Routes: Manual ─────────────────────────────────────────────────────────────
@app.route('/manual')
def manual():
    return render_template('manual.html')


# ── Routes: Settings ───────────────────────────────────────────────────────────
@app.route('/settings')
def settings():
    conn = get_db()
    pending = conn.execute('SELECT * FROM pending_tags ORDER BY submitted_at DESC').fetchall()
    conn.close()
    return render_template('settings.html', pending_tags=pending, **get_lookup_context())


@app.route('/settings/add/<table>', methods=['POST'])
def add_table_item(table):
    if table not in ALLOWED_TABLES:
        return 'Invalid', 400
    name = request.form.get('name', '').strip()
    if name:
        conn = get_db()
        try:
            conn.execute(f'INSERT INTO {table} (name) VALUES (?)', (name,))
            conn.commit()
            flash(f'Added "{name}".', 'success')
        except sqlite3.IntegrityError:
            flash(f'"{name}" already exists.', 'warning')
        finally:
            conn.close()
    return redirect(url_for('settings'))


@app.route('/settings/delete/<table>/<int:item_id>', methods=['POST'])
def delete_table_item(table, item_id):
    if table not in ALLOWED_TABLES:
        return 'Invalid', 400
    conn = get_db()
    conn.execute(f'DELETE FROM {table} WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    flash('Item deleted.', 'info')
    return redirect(url_for('settings'))


@app.route('/settings/pending-tags/approve/<int:tag_id>', methods=['POST'])
def approve_pending_tag(tag_id):
    conn = get_db()
    row = conn.execute('SELECT name FROM pending_tags WHERE id = ?', (tag_id,)).fetchone()
    if row:
        conn.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (row['name'],))
        conn.execute('DELETE FROM pending_tags WHERE id = ?', (tag_id,))
        conn.commit()
        flash(f'Tag "{row["name"]}" approved.', 'success')
    conn.close()
    return redirect(url_for('settings'))


@app.route('/settings/pending-tags/reject/<int:tag_id>', methods=['POST'])
def reject_pending_tag(tag_id):
    conn = get_db()
    row = conn.execute('SELECT name FROM pending_tags WHERE id = ?', (tag_id,)).fetchone()
    if not row:
        conn.close()
        flash('Pending tag not found.', 'danger')
        return redirect(url_for('settings'))

    old_name = row['name']
    new_replacement = request.form.get('new_replacement_tag', '').strip().lower()
    existing_replacement = request.form.get('replacement_tag', '').strip()
    replacement = new_replacement or existing_replacement or None

    if replacement:
        if new_replacement:
            conn.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (replacement,))
        # Copy all associations from old tag to replacement (skip if entry already has it)
        conn.execute(
            'INSERT OR IGNORE INTO log_entry_tags (entry_id, tag_name) '
            'SELECT entry_id, ? FROM log_entry_tags WHERE tag_name = ?',
            (replacement, old_name)
        )

    conn.execute('DELETE FROM log_entry_tags WHERE tag_name = ?', (old_name,))
    conn.execute('DELETE FROM pending_tags WHERE id = ?', (tag_id,))
    conn.commit()
    conn.close()

    if replacement:
        flash(f'Tag "{old_name}" rejected and replaced with "{replacement}" in all entries.', 'warning')
    else:
        flash(f'Tag "{old_name}" rejected and removed from all entries.', 'warning')
    return redirect(url_for('settings'))


# ── Routes: PDF Report ─────────────────────────────────────────────────────────
@app.route('/report')
def generate_report():
    mode = request.args.get('mode', 'basic')
    conn = get_db()
    sql, params = build_search_query(request.args, mode)
    entries = conn.execute(sql, params).fetchall()
    conn.close()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    cell_style = styles['Normal'].clone('cell_style')
    cell_style.fontSize = 7
    cell_style.leading  = 9   # line spacing to match 7pt text
    story = [
        Paragraph('Logbook Report', styles['Title']),
        Paragraph(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}', styles['Normal']),
        Paragraph(f'Results: {len(entries)}', styles['Normal']),
        Spacer(1, 0.5*cm),
    ]

    header = ['#', 'Date/Time', 'User', 'Location', 'Area',
              'Category', 'Severity', 'Rec.', 'Description']
    data = [header] + [
        [
            str(e['id']),
            (e['entry_datetime'] or '')[:16],
            e['username'] or '',
            e['location'] or '',
            e['area'] or '',
            e['category'] or '',
            e['severity'] or '',
            'Yes' if e['recurrent'] else 'No',
            Paragraph(html.escape((e['description'] or '').strip()).replace('\n', '<br/>'), cell_style),
        ]
        for e in entries
    ]

    widths = [0.8*cm, 2.6*cm, 1.8*cm, 2.0*cm, 1.8*cm, 2.0*cm, 1.8*cm, 1.0*cm, 4.2*cm]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1,  0), colors.HexColor('#0078d7')),
        ('TEXTCOLOR',  (0, 0), (-1,  0), colors.white),
        ('FONTNAME',   (0, 0), (-1,  0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 7),
        ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
    ]))
    story.append(t)
    doc.build(story)
    buf.seek(0)

    fname = f'logbook_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
    return send_file(buf, as_attachment=True, download_name=fname,
                     mimetype='application/pdf')


# ── Routes: Backup & Restore ───────────────────────────────────────────────────
@app.route('/backup')
def backup():
    if not os.path.exists(DB_PATH):
        flash('No database found.', 'warning')
        return redirect(url_for('settings'))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(DB_PATH, 'logbook.db')
    buf.seek(0)
    fname = f'logbook_backup_{datetime.now().strftime("%Y%m%d_%H%M")}.zip'
    return send_file(buf, as_attachment=True, download_name=fname,
                     mimetype='application/zip')


@app.route('/backup/auto', methods=['POST'])
def backup_auto():
    """Create a timestamped ZIP backup under /share/logbook for automations."""
    if not os.path.exists(DB_PATH):
        return 'No database found', 204

    backup_dir = '/share/logbook'

    # Verify /share is the real HA share mount, not an empty container directory
    if not os.path.ismount('/share'):
        return 'Share folder not mounted — rebuild or reinstall the add-on to apply map: share:rw', 503

    try:
        os.makedirs(backup_dir, exist_ok=True)

        dest_zip = os.path.join(backup_dir,
                                f'logbook_backup_{datetime.now().strftime("%Y%m%d_%H%M")}.zip')
        with zipfile.ZipFile(dest_zip, 'w', zipfile.ZIP_DEFLATED) as z:
            z.write(DB_PATH, 'logbook.db')

        # Keep only the 30 most recent automated backups
        files = sorted(glob.glob(os.path.join(backup_dir, 'logbook_backup_*.zip')))
        for old_file in files[:-30]:
            try:
                os.remove(old_file)
            except OSError:
                pass

        return f'Backup saved to {dest_zip}', 200

    except Exception as e:
        return f'Backup failed: {e}', 500


@app.route('/restore', methods=['POST'])
def restore():
    f = request.files.get('backup_file')
    if not f or not f.filename.endswith('.zip'):
        flash('Please upload a valid .zip backup file.', 'danger')
        return redirect(url_for('settings'))
    try:
        with zipfile.ZipFile(f, 'r') as z:
            if 'logbook.db' not in z.namelist():
                flash('Invalid backup: logbook.db not found inside zip.', 'danger')
                return redirect(url_for('settings'))
            if os.path.exists(DB_PATH):
                shutil.copy(DB_PATH, DB_PATH + '.pre_restore')
            z.extract('logbook.db', '/data/logbook/')
        flash('Database restored successfully!', 'success')
    except Exception as e:
        flash(f'Restore failed: {e}', 'danger')
    return redirect(url_for('settings'))


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8099, debug=False)
