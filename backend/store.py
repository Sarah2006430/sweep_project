"""SQLite ticket log. Statuses: Open, Assigned, Cleaned (Archived = from an earlier run or playback loop)."""
import sqlite3, threading, time

_db, _lock = None, threading.Lock()


def init(path):
    global _db
    _db = sqlite3.connect(path, check_same_thread=False)
    _db.row_factory = sqlite3.Row
    _db.execute("""create table if not exists tickets(
        id text primary key, zone text, type text, priority text, status text, staff text,
        created real, assigned real, cleaned real, note text)""")
    _db.commit()


def add(zone, typ, priority):
    with _lock:
        tid = f"T-{_db.execute('select count(*) from tickets').fetchone()[0] + 1:03d}"
        _db.execute("insert into tickets values(?,?,?,?,?,?,?,?,?,?)",
                    (tid, zone, typ, priority, "Open", None, time.time(), None, None, None))
        _db.commit()
        return tid


def get(tid):
    with _lock:
        r = _db.execute("select * from tickets where id=?", (tid,)).fetchone()
        return dict(r) if r else None


def update(tid, **kw):
    with _lock:
        _db.execute(f"update tickets set {','.join(k + '=?' for k in kw)} where id=?", (*kw.values(), tid))
        _db.commit()


def recent(archived=False, limit=200):
    with _lock:
        q = "select * from tickets " + ("" if archived else "where status!='Archived' ") + "order by created desc limit ?"
        return [dict(r) for r in _db.execute(q, (limit,))]


def archived(limit=200):
    with _lock:
        return [dict(r) for r in _db.execute("select * from tickets where status='Archived' order by created desc limit ?", (limit,))]


def archive_all():
    """Start a fresh run: everything from earlier runs moves to Archived and leaves the dashboard."""
    with _lock:
        _db.execute("update tickets set status='Archived' where status!='Archived'")
        _db.commit()
