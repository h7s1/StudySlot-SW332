"""
StudySlot - classroom booking website (SW332, Group 4, Section O53)
Sprint 1 scope: PBI-1 .. PBI-9
Sprint 2 scope: PBI-10 .. PBI-19 (admin tools, filters, history, emails, reviews, reports)

Run:   python app.py           (creates studyslot.db on first run)
Reset: python app.py --reset   (deletes all data and re-creates demo data)
"""
import os
import re
import smtplib
import sqlite3
import sys
from email.message import EmailMessage
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("STUDYSLOT_SECRET_KEY", "change-this-secret-key"),
    DATABASE=os.environ.get("STUDYSLOT_DB", os.path.join(BASE_DIR, "studyslot.db")),
    UNIVERSITY_DOMAIN=os.environ.get("STUDYSLOT_DOMAIN", "pnu.edu.sa"),
    MAX_DAYS_AHEAD=14,   # students can book up to 14 days ahead
)

# pbkdf2 works on every Python build (the macOS system Python has no scrypt)
PASSWORD_METHOD = "pbkdf2:sha256"

SLOT_SQL = "SELECT id, start_time, end_time, start_time || ' - ' || end_time AS label FROM time_slots"

# Simple line icons (SVG) used in the pages
ICONS = {
    "logo": '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M3 9h18M8 2v4M16 2v4"/><path d="M9 15l2 2 4-4"/>',
    "users": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    "pin": '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "door": '<path d="M13 4h3a2 2 0 0 1 2 2v14M2 20h3M13 20h9"/><path d="M10 12v.01"/><path d="M13 4.56v16.16a.5.5 0 0 1-.63.48L5 19V5.94a1 1 0 0 1 .76-.97l6-1.5A1 1 0 0 1 13 4.56z"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
    "ban": '<circle cx="12" cy="12" r="10"/><path d="M4.93 4.93l14.14 14.14"/>',
    "logout": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/>',
    "check": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="M22 4L12 14.01l-3-3"/>',
    "alert": '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>',
    "x": '<circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/>',
    "arrow-right": '<path d="M5 12h14M12 5l7 7-7 7"/>',
    "arrow-left": '<path d="M19 12H5M12 19l-7-7 7-7"/>',
    "lock": '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "mail": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 6l-10 7L2 6"/>',
    "user": '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
    "star": '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>',
    "bell": '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
    "flag": '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><path d="M4 22v-7"/>',
    "sliders": '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
    "history": '<path d="M3 3v5h5"/><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8"/><path d="M12 7v5l4 2"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "trash": '<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>',
    "building": '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4M8 6h.01M12 6h.01M16 6h.01M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01"/>',
}


def icon(name, cls=""):
    return Markup(f'<svg class="icon {cls}" viewBox="0 0 24 24" aria-hidden="true">{ICONS.get(name, "")}</svg>')


def initials(name):
    parts = (name or "?").split()
    return "".join(p[0] for p in parts[:2]).upper()


def tint(building):
    """Colour per building: A = green, B = brown, C = amber, then the colours repeat (D = green ...)."""
    letter = (building or "a").strip()[-1:].lower()
    if letter.isalpha() and letter.isascii():
        return "tint-" + "abc"[(ord(letter) - ord("a")) % 3]
    return "tint-a"


def slugify(text):
    """'Building A' -> 'building-a' (used in the address of a building page)."""
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def building_code(name):
    """'Building A' -> 'A' (the big letter on a building card)."""
    parts = (name or "?").split()
    return parts[-1][:3].upper() if parts else "?"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


DEMO_SLOTS = [
    (1, "08:00", "10:00"), (2, "10:00", "12:00"), (3, "12:00", "14:00"),
    (4, "14:00", "16:00"), (5, "16:00", "18:00"), (6, "18:00", "20:00"),
]

DEMO_ROOMS = [
    ("A-101", "Building A", "Ground floor", 4, "Whiteboard"),
    ("A-102", "Building A", "Ground floor", 6, "Whiteboard, Screen"),
    ("A-205", "Building A", "Second floor", 10, "Projector, Whiteboard"),
    ("B-110", "Building B", "First floor", 2, "Quiet room"),
    ("B-214", "Building B", "Second floor", 8, "Projector"),
    ("C-012", "Building C", "Ground floor", 20, "Projector, Smart board"),
]

DEMO_USERS = [
    ("System Admin", "admin@pnu.edu.sa", "Admin@123", "admin"),
    ("Demo Student", "446000001@pnu.edu.sa", "Student@123", "student"),
    ("Second Student", "446000002@pnu.edu.sa", "Student@123", "student"),
]


def init_db(seed=True, history=False):
    """Create all tables (drops old ones) and optionally add demo data.

    history=True also adds a few past bookings with reviews and one problem report, so the
    Sprint 2 pages (Previous bookings, ratings, Reports) have something to show in a demo.
    """
    db = sqlite3.connect(app.config["DATABASE"])
    with open(os.path.join(BASE_DIR, "schema.sql"), encoding="utf-8") as f:
        db.executescript(f.read())
    db.executemany("INSERT INTO time_slots (id, start_time, end_time) VALUES (?, ?, ?)", DEMO_SLOTS)
    if seed:
        db.executemany(
            "INSERT INTO rooms (name, building, floor, capacity, features) VALUES (?, ?, ?, ?, ?)",
            DEMO_ROOMS)
        db.executemany(
            "INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            [(n, e, generate_password_hash(p, method=PASSWORD_METHOD), r) for n, e, p, r in DEMO_USERS])
    if seed and history:
        for user_id, room_id, days_ago, slot_id, rating, comment in DEMO_HISTORY:
            day = (date.today() - timedelta(days=days_ago)).isoformat()
            cur = db.execute("INSERT INTO bookings (user_id, room_id, booking_date, slot_id) VALUES (?, ?, ?, ?)",
                             (user_id, room_id, day, slot_id))
            if rating:
                db.execute("INSERT INTO reviews (user_id, room_id, booking_id, rating, comment) VALUES (?, ?, ?, ?, ?)",
                           (user_id, room_id, cur.lastrowid, rating, comment))
        db.execute("INSERT INTO problem_reports (user_id, room_id, category, description) VALUES (3, 6, ?, ?)",
                   ("Air conditioning or lights", "Two lights at the back of the room do not work."))
    db.commit()
    db.close()


# (user id, room id, days ago, slot id, rating, comment) - past bookings for the demo
DEMO_HISTORY = [
    (2, 1, 2, 2, 5, "Quiet room, great for group study."),
    (2, 5, 4, 3, 4, "The projector works well."),
    (3, 1, 3, 4, 4, None),
    (2, 3, 6, 1, None, None),
]


def ensure_schema():
    """Upgrade an older studyslot.db to the current booking rules (seats per room).

    Runs the "BOOKING RULES" part of schema.sql. It is safe to run every time:
    nothing is deleted, bookings and accounts stay as they are.
    """
    with open(os.path.join(BASE_DIR, "schema.sql"), encoding="utf-8") as f:
        text = f.read()
    rules = text[text.index("-- BOOKING RULES"):]
    db = sqlite3.connect(app.config["DATABASE"])
    # Sprint 2 columns (SQLite has no "ADD COLUMN IF NOT EXISTS", so check first)
    for table, column, ddl in (("rooms", "is_active", "INTEGER NOT NULL DEFAULT 1"),
                               ("bookings", "cancel_note", "TEXT")):
        if column not in [r[1] for r in db.execute(f"PRAGMA table_info({table})")]:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    try:
        db.executescript(rules)
    except sqlite3.IntegrityError:
        # Only possible if an old database holds two active bookings of one student at the
        # same time. The app still checks this rule itself, so we keep going.
        db.executescript(rules.replace("CREATE UNIQUE INDEX IF NOT EXISTS ux_bookings_user_date_slot",
                                       "CREATE INDEX IF NOT EXISTS ix_bookings_user_date_slot"))
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def parse_date(value):
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def slot_has_started(day, slot):
    """True if the slot on that day is already in the past (or running now)."""
    now = datetime.now()
    if day < now.date():
        return True
    if day > now.date():
        return False
    return now.strftime("%H:%M") >= slot["start_time"]


def is_university_email(email):
    domain = re.escape(app.config["UNIVERSITY_DOMAIN"])
    return re.fullmatch(r"[a-z0-9._%+-]+@" + domain, email) is not None


def password_problem(password):
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain at least one letter and one number."
    return None


def get_slots():
    return get_db().execute(SLOT_SQL + " ORDER BY start_time").fetchall()


def get_rooms(min_seats=None):
    """Active classrooms (PBI-10: removed rooms are hidden), optionally only rooms with at least
    min_seats seats (PBI-12)."""
    return get_db().execute(
        "SELECT * FROM rooms WHERE is_active = 1 AND capacity >= ? ORDER BY building, name",
        (min_seats or 0,)).fetchall()


def get_buildings():
    """Rooms grouped by building, for the buildings page and the building filter."""
    groups = {}
    for room in get_rooms():
        b = groups.setdefault(room["building"], {
            "name": room["building"], "slug": slugify(room["building"]),
            "code": building_code(room["building"]), "rooms": [], "seats": 0, "floors": []})
        b["rooms"].append(room)
        b["seats"] += room["capacity"]
        if room["floor"] not in b["floors"]:
            b["floors"].append(room["floor"])
    return list(groups.values())


def max_booking_date():
    return date.today() + timedelta(days=app.config["MAX_DAYS_AHEAD"])


def blocked_periods(room_ids):
    """Upcoming blocked periods per room, for students (PBI-9).

    Returns {room_id: [{"date", "start", "end", "reason"}, ...]}. Neighbouring slots with the
    same reason on the same day are joined, so 10:00-12:00 and 12:00-14:00 show as 10:00 - 14:00.
    Only the days students can book (today up to MAX_DAYS_AHEAD) are listed.
    """
    result = {rid: [] for rid in room_ids}
    if not room_ids:
        return result
    now = datetime.now()
    marks = ",".join("?" * len(room_ids))
    rows = get_db().execute(
        "SELECT bs.room_id, bs.block_date, bs.reason, t.start_time, t.end_time "
        "FROM blocked_slots bs JOIN time_slots t ON t.id = bs.slot_id "
        f"WHERE bs.room_id IN ({marks}) AND bs.block_date BETWEEN ? AND ? "
        "ORDER BY bs.room_id, bs.block_date, t.start_time",
        (*room_ids, now.date().isoformat(), max_booking_date().isoformat())).fetchall()
    for r in rows:
        day = parse_date(r["block_date"])
        if day == now.date() and r["end_time"] <= now.strftime("%H:%M"):
            continue   # this blocked slot is already over
        periods = result[r["room_id"]]
        last = periods[-1] if periods else None
        if last and last["date"] == day and last["reason"] == r["reason"] and last["end"] == r["start_time"]:
            last["end"] = r["end_time"]
        else:
            periods.append({"date": day, "start": r["start_time"], "end": r["end_time"],
                            "reason": r["reason"]})
    return result


def slot_hours(slot):
    """Length of a time slot in hours ('10:00' - '12:00' -> 2)."""
    h1, m1 = map(int, slot["start_time"].split(":"))
    h2, m2 = map(int, slot["end_time"].split(":"))
    return (h2 * 60 + m2 - h1 * 60 - m1) / 60


# --- PBI-14: settings --------------------------------------------------------
def get_setting(key, default=None):
    row = get_db().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def daily_limit_hours():
    try:
        return int(get_setting("daily_limit_hours", "4"))
    except ValueError:
        return 4


# --- PBI-18 / PBI-19: notices and confirmation emails -------------------------
def notify(user_id, subject, body, kind="notice"):
    """Save a message for the student. It shows on their Notifications page."""
    get_db().execute("INSERT INTO notifications (user_id, kind, subject, body, created_at) VALUES (?, ?, ?, ?, ?)",
                     (user_id, kind, subject, body, datetime.now().strftime("%Y-%m-%d %H:%M")))


def send_email(user, subject, body):
    """PBI-19: confirmation email.

    A copy is always saved (Notifications page). The real email is sent only when an SMTP
    server is set in the environment (STUDYSLOT_SMTP_HOST, _PORT, _USER, _PASSWORD, _FROM).
    Without it (or if sending fails) the email is printed in the terminal; the booking itself
    is never stopped by an email problem.
    """
    notify(user["id"], subject, body, kind="email")
    host = os.environ.get("STUDYSLOT_SMTP_HOST")
    if not host or app.config.get("TESTING"):
        print(f"[email] To: {user['email']} | {subject}\n{body}\n")
        return False
    msg = EmailMessage()
    msg["From"] = os.environ.get("STUDYSLOT_SMTP_FROM", os.environ.get("STUDYSLOT_SMTP_USER", "studyslot@localhost"))
    msg["To"] = user["email"]
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, int(os.environ.get("STUDYSLOT_SMTP_PORT", "587")), timeout=10) as smtp:
            smtp.starttls()
            if os.environ.get("STUDYSLOT_SMTP_USER"):
                smtp.login(os.environ["STUDYSLOT_SMTP_USER"], os.environ.get("STUDYSLOT_SMTP_PASSWORD", ""))
            smtp.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        print(f"[email] Could not send to {user['email']}: {exc}")
        return False


def booking_email_text(user, action, room, day, slot_label, extra=""):
    lines = [f"Hello {user['full_name'].split()[0]},", "",
             f"Your StudySlot booking was {action}.", "",
             f"Room:     {room['name']} ({room['building']}, {room['floor']})",
             f"Date:     {day.strftime('%A %d %B %Y')}",
             f"Time:     {slot_label}"]
    if extra:
        lines += ["", extra]
    lines += ["", "You can see all your bookings in My Bookings.", "", "StudySlot"]
    return "\n".join(lines)


# --- PBI-17: when is a full room free next? -----------------------------------
def next_free_time(room, day, after_start):
    """First slot after `after_start` on `day` (or a later bookable day) where the room has a free
    seat and is not blocked. Returns {"date", "start"} or None (nothing free in the booking window)."""
    db = get_db()
    slots = get_slots()
    current = day
    while current <= max_booking_date():
        booked = {r["slot_id"]: r["n"] for r in db.execute(
            "SELECT slot_id, COUNT(*) AS n FROM bookings WHERE room_id = ? AND booking_date = ? "
            "AND status = 'active' GROUP BY slot_id", (room["id"], current.isoformat()))}
        blocked = {r["slot_id"] for r in db.execute(
            "SELECT slot_id FROM blocked_slots WHERE room_id = ? AND block_date = ?",
            (room["id"], current.isoformat()))}
        for s in slots:
            if current == day and s["start_time"] <= after_start:
                continue
            if s["id"] in blocked or slot_has_started(current, s):
                continue
            if booked.get(s["id"], 0) < room["capacity"]:
                return {"date": current, "start": s["start_time"], "slot_id": s["id"]}
        current += timedelta(days=1)
    return None


# --- PBI-15: ratings ----------------------------------------------------------
def room_ratings(room_ids):
    """{room_id: {"avg": 4.5, "count": 2, "latest": [comments]}} for the room cards."""
    result = {}
    if not room_ids:
        return result
    marks = ",".join("?" * len(room_ids))
    db = get_db()
    for r in db.execute(f"SELECT room_id, AVG(rating) AS avg, COUNT(*) AS n FROM reviews "
                        f"WHERE room_id IN ({marks}) GROUP BY room_id", room_ids):
        result[r["room_id"]] = {"avg": round(r["avg"], 1), "count": r["n"], "latest": []}
    for r in db.execute(f"SELECT room_id, rating, comment FROM reviews WHERE room_id IN ({marks}) "
                        f"AND comment IS NOT NULL AND comment <> '' ORDER BY created_at DESC, id DESC", room_ids):
        latest = result[r["room_id"]]["latest"]
        if len(latest) < 2:
            latest.append(r["comment"])
    return result


def validate_booking(user_id, room_id, date_str, slot_id, exclude_booking_id=None):
    """Check every booking rule. Returns (error_message, None) or (None, details)."""
    db = get_db()
    day = parse_date(date_str)
    if day is None:
        return "Please choose a valid date.", None
    room = db.execute("SELECT * FROM rooms WHERE id = ? AND is_active = 1", (room_id,)).fetchone()
    if room is None:
        return "Please choose a valid room.", None
    slot = db.execute(SLOT_SQL + " WHERE id = ?", (slot_id,)).fetchone()
    if slot is None:
        return "Please choose a valid time slot.", None
    if slot_has_started(day, slot):
        return "This time slot is in the past. Please choose a future time.", None
    if day > max_booking_date():
        return f"You can only book up to {app.config['MAX_DAYS_AHEAD']} days ahead.", None

    blocked = db.execute(
        "SELECT reason FROM blocked_slots WHERE room_id = ? AND block_date = ? AND slot_id = ?",
        (room_id, day.isoformat(), slot_id)).fetchone()
    if blocked:
        return (f"Room {room['name']} is not available at this time "
                f"(blocked for {blocked['reason']})."), None

    exclude = exclude_booking_id or 0
    # Seats: every active booking takes one seat. The room is full when all seats are taken.
    taken = db.execute(
        "SELECT COUNT(*) FROM bookings WHERE room_id = ? AND booking_date = ? AND slot_id = ? "
        "AND status = 'active' AND id <> ?",
        (room_id, day.isoformat(), slot_id, exclude)).fetchone()[0]
    if taken >= room["capacity"]:
        return (f"Room {room['name']} is full on {day.isoformat()} at {slot['label']} "
                f"(all {room['capacity']} seats are booked). Please choose another room or time."), None

    own = db.execute(
        "SELECT 1 FROM bookings WHERE user_id = ? AND booking_date = ? AND slot_id = ? "
        "AND status = 'active' AND id <> ?",
        (user_id, day.isoformat(), slot_id, exclude)).fetchone()
    if own:
        return "You already have another booking at this date and time.", None

    # PBI-14: a student can book at most "daily_limit_hours" hours on one day
    limit = daily_limit_hours()
    used = sum(slot_hours(r) for r in db.execute(
        "SELECT s.start_time, s.end_time FROM bookings b JOIN time_slots s ON s.id = b.slot_id "
        "WHERE b.user_id = ? AND b.booking_date = ? AND b.status = 'active' AND b.id <> ?",
        (user_id, day.isoformat(), exclude)))
    if limit and used + slot_hours(slot) > limit:
        return (f"You can book at most {limit} hours per day. You already have {used:g} hours "
                f"booked on {day.isoformat()}."), None

    return None, {"room": room, "slot": slot, "day": day,
                  "seats_left": room["capacity"] - taken}


def get_own_booking(booking_id):
    """Load a booking with room and slot; only the owner may access it (Task 7.2, 8.2)."""
    booking = get_db().execute(
        "SELECT b.*, r.name AS room_name, r.building, r.floor, "
        "s.start_time, s.end_time, s.start_time || ' - ' || s.end_time AS slot_label "
        "FROM bookings b JOIN rooms r ON r.id = b.room_id JOIN time_slots s ON s.id = b.slot_id "
        "WHERE b.id = ?", (booking_id,)).fetchone()
    if booking is None:
        abort(404)
    if booking["user_id"] != g.user["id"]:
        abort(403)
    return booking


# ---------------------------------------------------------------------------
# Login state and permission checks
# ---------------------------------------------------------------------------
@app.before_request
def load_logged_in_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if g.user is None:
            session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def student_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if g.user["role"] != "student":
            flash("This page is for students. Admins use the dashboard.", "info")
            return redirect(url_for("admin_dashboard"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    """Task 2.3 / 9.2: block students from admin pages."""
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if g.user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    return {
        "today": date.today().isoformat(),
        "max_date": max_booking_date().isoformat(),
        "university_domain": app.config["UNIVERSITY_DOMAIN"],
        "icon": icon,
        "initials": initials,
        "tint": tint,
        "parse_date": parse_date,
        "unread_count": unread_count(),
    }


def unread_count():
    if g.get("user") is None or g.user["role"] != "student":
        return 0
    return get_db().execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
                            (g.user["id"],)).fetchone()[0]


@app.errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403,
                           message="You do not have permission to open this page."), 403


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, message="Page not found."), 404


# ---------------------------------------------------------------------------
# PBI-1 / PBI-2: register and log in with university email
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if g.user is None:
        return redirect(url_for("login"))
    if g.user["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("rooms"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("index"))
    form = {"full_name": "", "email": ""}
    if request.method == "POST":
        form["full_name"] = request.form.get("full_name", "").strip()
        form["email"] = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        error = None
        if not form["full_name"] or not form["email"] or not password:
            error = "Please fill in all fields."
        elif not is_university_email(form["email"]):
            error = f"Please use your university email (@{app.config['UNIVERSITY_DOMAIN']})."
        elif password_problem(password):
            error = password_problem(password)
        elif password != confirm:
            error = "Passwords do not match."
        else:
            db = get_db()
            if db.execute("SELECT 1 FROM users WHERE email = ?", (form["email"],)).fetchone():
                error = "An account with this email already exists. Please log in."
            else:
                # New accounts are always students; admin accounts are created by the system.
                db.execute(
                    "INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, ?, 'student')",
                    (form["full_name"], form["email"], generate_password_hash(password, method=PASSWORD_METHOD)))
                db.commit()
                flash("Account created. You can log in now.", "success")
                return redirect(url_for("login"))
        flash(error, "error")
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))
    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Please enter your email and password.", "error")
        elif not is_university_email(email):
            flash(f"Please use your university email (@{app.config['UNIVERSITY_DOMAIN']}).", "error")
        else:
            user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if user is None or not check_password_hash(user["password_hash"], password):
                flash("Wrong email or password.", "error")
            else:
                session.clear()
                session["user_id"] = user["id"]
                # Task 2.3: admin goes to the admin landing page, student to the rooms
                if user["role"] == "admin":
                    return redirect(url_for("admin_dashboard"))
                return redirect(url_for("rooms"))
    return render_template("login.html", email=email)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have logged out.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# PBI-3: list of classrooms - first choose a building, then see its classrooms
# ---------------------------------------------------------------------------
@app.route("/rooms")
@student_required
def rooms():
    buildings = get_buildings()
    room_count = sum(len(b["rooms"]) for b in buildings)
    return render_template("rooms.html", buildings=buildings, room_count=room_count)


@app.route("/buildings/<slug>")
@student_required
def building_rooms(slug):
    buildings = get_buildings()
    building = next((b for b in buildings if b["slug"] == slug), None)
    if building is None:
        abort(404)
    room_ids = [r["id"] for r in building["rooms"]]
    blocks = blocked_periods(room_ids)
    ratings = room_ratings(room_ids)   # PBI-15
    return render_template("building.html", building=building, buildings=buildings, blocks=blocks,
                           ratings=ratings)


# ---------------------------------------------------------------------------
# PBI-4: check free rooms by date and time
# ---------------------------------------------------------------------------
@app.route("/availability")
@student_required
def availability():
    db = get_db()
    all_slots = get_slots()
    buildings = get_buildings()
    date_str = request.args.get("date") or date.today().isoformat()
    slot_id = request.args.get("slot_id", type=int)
    building_slug = request.args.get("building", "").strip()
    min_seats = request.args.get("min_seats", type=int) or 0     # PBI-12: capacity filter
    day = parse_date(date_str)

    # Optional filters: one building (an unknown building shows all rooms) and/or a minimum
    # number of seats. Both can be used together with the date and time.
    building = next((b for b in buildings if b["slug"] == building_slug), None)
    building_slug = building["slug"] if building else ""
    shown_rooms = [r for r in (building["rooms"] if building else get_rooms()) if r["capacity"] >= min_seats]

    error, grid, slots = None, [], all_slots
    if slot_id:
        slots = [s for s in all_slots if s["id"] == slot_id]
    if day is None:
        error = "Please choose a valid date."
    elif day < date.today():
        error = "This date is in the past. Please choose today or a later date."
    elif day > max_booking_date():
        error = f"You can only book up to {app.config['MAX_DAYS_AHEAD']} days ahead."
    else:
        # how many seats are booked per room and slot on this day
        booked = {(r["room_id"], r["slot_id"]): r["n"] for r in db.execute(
            "SELECT room_id, slot_id, COUNT(*) AS n FROM bookings "
            "WHERE booking_date = ? AND status = 'active' GROUP BY room_id, slot_id",
            (day.isoformat(),))}
        mine = {(r["room_id"], r["slot_id"]) for r in db.execute(
            "SELECT room_id, slot_id FROM bookings "
            "WHERE booking_date = ? AND status = 'active' AND user_id = ?",
            (day.isoformat(), g.user["id"]))}
        blocked = {(r["room_id"], r["slot_id"]): r["reason"] for r in db.execute(
            "SELECT room_id, slot_id, reason FROM blocked_slots WHERE block_date = ?",
            (day.isoformat(),))}
        for room in shown_rooms:
            cells = []
            for s in slots:
                key = (room["id"], s["id"])
                taken = booked.get(key, 0)
                if key in blocked:   # Task 9.3: blocked slots cannot be booked
                    cells.append({"slot": s, "status": "blocked", "reason": blocked[key]})
                elif key in mine:
                    cells.append({"slot": s, "status": "mine"})
                elif taken >= room["capacity"]:
                    # PBI-17: tell the student when this room has a free seat again
                    cells.append({"slot": s, "status": "full",
                                  "next_free": next_free_time(room, day, s["start_time"])})
                elif slot_has_started(day, s):
                    cells.append({"slot": s, "status": "past"})
                else:
                    cells.append({"slot": s, "status": "free", "seats_left": room["capacity"] - taken})
            grid.append({"room": room, "cells": cells})

    free_count = sum(1 for row in grid for c in row["cells"] if c["status"] == "free")
    prev_day = next_day = None
    if day is not None:
        if date.today() < day <= max_booking_date():
            prev_day = (day - timedelta(days=1)).isoformat()
        if date.today() <= day < max_booking_date():
            next_day = (day + timedelta(days=1)).isoformat()
    return render_template("availability.html", date_str=date_str, slot_id=slot_id, day=day,
                           all_slots=all_slots, slots=slots, grid=grid, error=error,
                           free_count=free_count, prev_day=prev_day, next_day=next_day,
                           buildings=buildings, building=building, building_slug=building_slug,
                           min_seats=min_seats, seat_options=SEAT_OPTIONS)


SEAT_OPTIONS = [2, 4, 6, 8, 10, 20]


# ---------------------------------------------------------------------------
# PBI-5: book a free room (confirmation screen + no double booking)
# ---------------------------------------------------------------------------
@app.route("/book", methods=["GET", "POST"])
@student_required
def book():
    room_id = request.values.get("room_id", type=int)
    slot_id = request.values.get("slot_id", type=int)
    date_str = request.values.get("date", "")

    error, details = validate_booking(g.user["id"], room_id, date_str, slot_id)
    if error:
        flash(error, "error")
        return redirect(url_for("availability", date=date_str or None))

    if request.method == "POST":
        db = get_db()
        try:
            db.execute(
                "INSERT INTO bookings (user_id, room_id, booking_date, slot_id) VALUES (?, ?, ?, ?)",
                (g.user["id"], room_id, details["day"].isoformat(), slot_id))
            db.commit()
        except sqlite3.IntegrityError:
            # The database seat limit stops the extra booking if two people confirm at the same moment
            db.rollback()
            error, _ = validate_booking(g.user["id"], room_id, date_str, slot_id)
            flash(error or "Sorry, the last seat was just booked by someone else.", "error")
            return redirect(url_for("availability", date=date_str))
        send_email(g.user, f"Booking confirmed: {details['room']['name']} on {details['day'].isoformat()}",
                   booking_email_text(g.user, "confirmed", details["room"], details["day"], details["slot"]["label"]))
        db.commit()
        flash(f"Booking confirmed: {details['room']['name']} on {details['day'].isoformat()}, "
              f"{details['slot']['label']}. A confirmation email was sent to {g.user['email']}.", "success")
        return redirect(url_for("my_bookings"))

    return render_template("book_confirm.html", **details)   # details include seats_left


# ---------------------------------------------------------------------------
# PBI-6: view upcoming bookings
# ---------------------------------------------------------------------------
def has_ended(booking):
    now = datetime.now()
    return (booking["booking_date"] < now.date().isoformat()
            or (booking["booking_date"] == now.date().isoformat() and booking["end_time"] <= now.strftime("%H:%M")))


@app.route("/my-bookings")
@student_required
def my_bookings():
    tab = "previous" if request.args.get("tab") == "previous" else "upcoming"
    rows = get_db().execute(
        "SELECT b.id, b.booking_date, b.status, b.cancel_note, b.room_id, r.name AS room_name, r.building, "
        "r.floor, r.capacity, r.is_active, s.start_time, s.end_time, "
        "s.start_time || ' - ' || s.end_time AS slot_label, rv.rating AS my_rating "
        "FROM bookings b JOIN rooms r ON r.id = b.room_id JOIN time_slots s ON s.id = b.slot_id "
        "LEFT JOIN reviews rv ON rv.booking_id = b.id "
        "WHERE b.user_id = ? ORDER BY b.booking_date, s.start_time", (g.user["id"],)).fetchall()
    upcoming = [b for b in rows if b["status"] == "active" and not has_ended(b)]
    # PBI-13: previous = finished or cancelled bookings, newest first
    previous = [b for b in reversed(rows) if b["status"] != "active" or has_ended(b)]
    return render_template("my_bookings.html", tab=tab, bookings=upcoming, previous=previous[:50],
                           upcoming_count=len(upcoming), previous_count=len(previous), slugify=slugify)


# ---------------------------------------------------------------------------
# PBI-15: review a room after using it
# ---------------------------------------------------------------------------
@app.route("/bookings/<int:booking_id>/review", methods=["GET", "POST"])
@student_required
def review_booking(booking_id):
    booking = get_own_booking(booking_id)            # only the owner (Task 15.2)
    if booking["status"] != "active" or not has_ended(booking):
        flash("You can review a room only after you have used it.", "error")
        return redirect(url_for("my_bookings", tab="previous"))
    db = get_db()
    if db.execute("SELECT 1 FROM reviews WHERE booking_id = ?", (booking_id,)).fetchone():
        flash("You already reviewed this booking.", "info")
        return redirect(url_for("my_bookings", tab="previous"))
    form = {"rating": 0, "comment": ""}
    if request.method == "POST":
        form = {"rating": request.form.get("rating", type=int) or 0,
                "comment": request.form.get("comment", "").strip()}
        if form["rating"] not in range(1, 6):
            flash("Please choose a rating from 1 to 5 stars.", "error")
        elif len(form["comment"]) > 300:
            flash("Please keep the comment under 300 characters.", "error")
        else:
            db.execute("INSERT INTO reviews (user_id, room_id, booking_id, rating, comment) VALUES (?, ?, ?, ?, ?)",
                       (g.user["id"], booking["room_id"], booking_id, form["rating"], form["comment"] or None))
            db.commit()
            flash(f"Thank you! Your review of {booking['room_name']} was saved.", "success")
            return redirect(url_for("my_bookings", tab="previous"))
    return render_template("review.html", booking=booking, form=form)


# ---------------------------------------------------------------------------
# PBI-16: report a problem in a room
# ---------------------------------------------------------------------------
PROBLEM_CATEGORIES = ["Equipment (projector, screen, board)", "Cleanliness", "Furniture",
                      "Air conditioning or lights", "Other"]


@app.route("/rooms/<int:room_id>/report", methods=["GET", "POST"])
@student_required
def report_problem(room_id):
    db = get_db()
    room = db.execute("SELECT * FROM rooms WHERE id = ? AND is_active = 1", (room_id,)).fetchone()
    if room is None:
        abort(404)
    form = {"category": "", "description": ""}
    if request.method == "POST":
        form = {"category": request.form.get("category", ""),
                "description": request.form.get("description", "").strip()}
        if form["category"] not in PROBLEM_CATEGORIES:
            flash("Please choose the type of problem.", "error")
        elif len(form["description"]) < 10:
            flash("Please describe the problem (at least 10 characters).", "error")
        elif len(form["description"]) > 500:
            flash("Please keep the description under 500 characters.", "error")
        else:
            db.execute("INSERT INTO problem_reports (user_id, room_id, category, description) VALUES (?, ?, ?, ?)",
                       (g.user["id"], room_id, form["category"], form["description"]))
            db.commit()
            flash(f"Thank you! Your report about {room['name']} was sent to the admin.", "success")
            return redirect(url_for("building_rooms", slug=slugify(room["building"])))
    return render_template("report_problem.html", room=room, form=form, categories=PROBLEM_CATEGORIES,
                           slug=slugify(room["building"]))


# ---------------------------------------------------------------------------
# PBI-18 / PBI-19: the student's notices and email copies
# ---------------------------------------------------------------------------
@app.route("/notifications")
@student_required
def notifications():
    db = get_db()
    items = db.execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 50",
                       (g.user["id"],)).fetchall()
    unread_ids = {n["id"] for n in items if not n["is_read"]}
    db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (g.user["id"],))
    db.commit()
    return render_template("notifications.html", items=items, unread_ids=unread_ids)


# ---------------------------------------------------------------------------
# PBI-7: cancel a booking (owner only)
# ---------------------------------------------------------------------------
@app.route("/bookings/<int:booking_id>/cancel", methods=["GET", "POST"])
@student_required
def cancel_booking(booking_id):
    booking = get_own_booking(booking_id)
    if booking["status"] != "active":
        flash("This booking is already cancelled.", "info")
        return redirect(url_for("my_bookings"))
    if slot_has_started(parse_date(booking["booking_date"]), booking):
        flash("You cannot cancel a booking that has already started or ended.", "error")
        return redirect(url_for("my_bookings"))

    if request.method == "POST":
        db = get_db()
        db.execute("UPDATE bookings SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                   (booking_id,))
        send_email(g.user, f"Booking cancelled: {booking['room_name']} on {booking['booking_date']}",
                   booking_email_text(g.user, "cancelled", {"name": booking["room_name"], "building": booking["building"],
                                      "floor": booking["floor"]}, parse_date(booking["booking_date"]),
                                      booking["slot_label"]))
        db.commit()
        flash(f"Your booking for {booking['room_name']} was cancelled. Your seat is free for other students now. "
              "A confirmation email was sent.", "success")
        return redirect(url_for("my_bookings"))
    return render_template("cancel_confirm.html", booking=booking)


# ---------------------------------------------------------------------------
# PBI-8: change a booking (owner only + double booking check)
# ---------------------------------------------------------------------------
@app.route("/bookings/<int:booking_id>/change", methods=["GET", "POST"])
@student_required
def change_booking(booking_id):
    booking = get_own_booking(booking_id)
    if booking["status"] != "active":
        flash("You cannot change a cancelled booking.", "error")
        return redirect(url_for("my_bookings"))
    if slot_has_started(parse_date(booking["booking_date"]), booking):
        flash("You cannot change a booking that has already started or ended.", "error")
        return redirect(url_for("my_bookings"))

    form = {"room_id": booking["room_id"], "date": booking["booking_date"], "slot_id": booking["slot_id"]}
    if request.method == "POST":
        form = {
            "room_id": request.form.get("room_id", type=int),
            "date": request.form.get("date", ""),
            "slot_id": request.form.get("slot_id", type=int),
        }
        if (form["room_id"] == booking["room_id"] and form["date"] == booking["booking_date"]
                and form["slot_id"] == booking["slot_id"]):
            flash("You did not change anything.", "info")
        else:
            error, details = validate_booking(g.user["id"], form["room_id"], form["date"],
                                              form["slot_id"], exclude_booking_id=booking_id)
            if error:
                flash(error, "error")
            else:
                db = get_db()
                try:
                    db.execute(
                        "UPDATE bookings SET room_id = ?, booking_date = ?, slot_id = ?, "
                        "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (form["room_id"], details["day"].isoformat(), form["slot_id"], booking_id))
                    db.commit()
                except sqlite3.IntegrityError:
                    db.rollback()
                    error, _ = validate_booking(g.user["id"], form["room_id"], form["date"],
                                                form["slot_id"], exclude_booking_id=booking_id)
                    flash(error or "Sorry, the last seat was just booked by someone else.", "error")
                else:
                    send_email(g.user, f"Booking changed: {details['room']['name']} on {details['day'].isoformat()}",
                               booking_email_text(
                                   g.user, "changed", details["room"], details["day"], details["slot"]["label"],
                                   extra=f"Before the change: {booking['room_name']}, {booking['booking_date']}, "
                                         f"{booking['slot_label']}."))
                    db.commit()
                    flash(f"Booking changed to {details['room']['name']} on {details['day'].isoformat()}, "
                          f"{details['slot']['label']}. A confirmation email was sent.", "success")
                    return redirect(url_for("my_bookings"))
    return render_template("change_booking.html", booking=booking, form=form,
                           rooms=get_rooms(), slots=get_slots())


# ---------------------------------------------------------------------------
# PBI-2: admin landing page
# ---------------------------------------------------------------------------
@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    today = date.today().isoformat()
    stats = {
        "rooms": db.execute("SELECT COUNT(*) FROM rooms WHERE is_active = 1").fetchone()[0],
        "students": db.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0],
        "upcoming_bookings": db.execute(
            "SELECT COUNT(*) FROM bookings WHERE status = 'active' AND booking_date >= ?", (today,)).fetchone()[0],
        "upcoming_blocks": db.execute(
            "SELECT COUNT(*) FROM blocked_slots WHERE block_date >= ?", (today,)).fetchone()[0],
        "open_reports": db.execute(
            "SELECT COUNT(*) FROM problem_reports WHERE status = 'open'").fetchone()[0],
        "daily_limit": daily_limit_hours(),
    }
    blocks = db.execute(
        "SELECT bs.block_date, bs.reason, r.name AS room_name, "
        "t.start_time || ' - ' || t.end_time AS slot_label "
        "FROM blocked_slots bs JOIN rooms r ON r.id = bs.room_id JOIN time_slots t ON t.id = bs.slot_id "
        "WHERE bs.block_date >= ? ORDER BY bs.block_date, t.start_time, r.name LIMIT 5", (today,)).fetchall()
    return render_template("admin/dashboard.html", stats=stats, blocks=blocks)


# ---------------------------------------------------------------------------
# PBI-9: admin blocks time slots for classes or maintenance (admin only)
# ---------------------------------------------------------------------------
@app.route("/admin/block", methods=["GET", "POST"])
@admin_required
def admin_block():
    db = get_db()
    form = {"room_id": None, "date": "", "slot_ids": [], "reason": "class", "note": ""}

    if request.method == "POST":
        form = {
            "room_id": request.form.get("room_id", type=int),
            "date": request.form.get("date", ""),
            "slot_ids": [int(s) for s in request.form.getlist("slot_ids") if s.isdigit()],
            "reason": request.form.get("reason", ""),
            "note": request.form.get("note", "").strip(),
        }
        day = parse_date(form["date"])
        room = db.execute("SELECT * FROM rooms WHERE id = ? AND is_active = 1", (form["room_id"],)).fetchone()
        error = None
        if room is None:
            error = "Please choose a room."
        elif day is None:
            error = "Please choose a valid date."
        elif day < date.today():
            error = "You cannot block a date in the past."
        elif not form["slot_ids"]:
            error = "Please choose at least one time slot."
        elif form["reason"] not in ("class", "maintenance"):
            error = "Please choose a reason (class or maintenance)."

        affected = []
        if not error:
            # PBI-18: bookings that are already in the chosen slots
            marks = ",".join("?" * len(form["slot_ids"]))
            affected = db.execute(
                "SELECT b.id, b.user_id, u.full_name, u.email, s.start_time, "
                "s.start_time || ' - ' || s.end_time AS slot_label "
                "FROM bookings b JOIN users u ON u.id = b.user_id JOIN time_slots s ON s.id = b.slot_id "
                f"WHERE b.room_id = ? AND b.booking_date = ? AND b.status = 'active' AND b.slot_id IN ({marks}) "
                "ORDER BY s.start_time, u.full_name",
                (room["id"], day.isoformat(), *form["slot_ids"])).fetchall()
            affected = [b for b in affected if not slot_has_started(day, b)]   # past ones stay as they are

        if error:
            flash(error, "error")
        elif affected and request.form.get("confirm") != "yes":
            # Task 18.2: warn first and list the bookings that will be cancelled
            return render_template("admin/block.html", form=form, rooms=get_rooms(), slots=get_slots(),
                                   blocks=upcoming_blocks(), affected=affected, room=room, day=day)
        else:
            added, skipped = [], []
            # Task 18.3: cancel the affected bookings and tell each student
            reason_text = form["reason"] + (f" - {form['note']}" if form["note"] else "")
            for b in affected:
                db.execute("UPDATE bookings SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP, "
                           "cancel_note = ? WHERE id = ?", (f"Cancelled by the admin ({reason_text})", b["id"]))
                student = {"id": b["user_id"], "email": b["email"], "full_name": b["full_name"]}
                text = booking_email_text(
                    student, "cancelled by the admin", room, day, b["slot_label"],
                    extra=f"Reason: the room is needed for {reason_text}. Sorry for the change. "
                          "Please book another room in Find a Free Room.")
                notify(b["user_id"], f"Your booking in {room['name']} was cancelled",
                       f"Your booking in {room['name']} on {day.strftime('%a %d %b')}, {b['slot_label']} was cancelled "
                       f"because the room is needed for {reason_text}. Please book another room in Find a Free Room.")
                send_email(student, f"Booking cancelled by the admin: {room['name']} on {day.isoformat()}", text)
            for slot_id in form["slot_ids"]:
                slot = db.execute(SLOT_SQL + " WHERE id = ?", (slot_id,)).fetchone()
                if slot is None:
                    continue
                if slot_has_started(day, slot):
                    skipped.append(f"{slot['label']} (already in the past)")
                    continue
                if db.execute("SELECT 1 FROM blocked_slots WHERE room_id = ? AND block_date = ? AND slot_id = ?",
                              (room["id"], day.isoformat(), slot_id)).fetchone():
                    skipped.append(f"{slot['label']} (already blocked)")
                    continue
                db.execute(
                    "INSERT INTO blocked_slots (room_id, block_date, slot_id, reason, note, created_by) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (room["id"], day.isoformat(), slot_id, form["reason"], form["note"] or None, g.user["id"]))
                added.append(slot["label"])
            db.commit()
            if added:
                flash(f"Blocked {room['name']} on {day.isoformat()}: {', '.join(added)}. "
                      "Students now see this time as Blocked and cannot book it.", "success")
            if affected:
                flash(f"{len(affected)} booking{'' if len(affected) == 1 else 's'} cancelled. "
                      "Each student got a notice and an email.", "info")
            if skipped:
                flash("Not blocked: " + "; ".join(skipped), "error")
            if added and not skipped:
                return redirect(url_for("admin_block"))

    return render_template("admin/block.html", form=form, rooms=get_rooms(),
                           slots=get_slots(), blocks=upcoming_blocks(), affected=[])


def upcoming_blocks():
    return get_db().execute(
        "SELECT bs.id, bs.block_date, bs.reason, bs.note, r.name AS room_name, r.building, "
        "t.start_time || ' - ' || t.end_time AS slot_label "
        "FROM blocked_slots bs JOIN rooms r ON r.id = bs.room_id JOIN time_slots t ON t.id = bs.slot_id "
        "WHERE bs.block_date >= ? ORDER BY bs.block_date, t.start_time, r.name",
        (date.today().isoformat(),)).fetchall()


@app.route("/admin/block/<int:block_id>/remove", methods=["POST"])
@admin_required
def admin_unblock(block_id):
    db = get_db()
    db.execute("DELETE FROM blocked_slots WHERE id = ?", (block_id,))
    db.commit()
    flash("The time slot is open for booking again.", "success")
    return redirect(url_for("admin_block"))


# ---------------------------------------------------------------------------
# PBI-11: admin views all bookings (search by date, room and student)
# ---------------------------------------------------------------------------
@app.route("/admin/bookings")
@admin_required
def admin_bookings():
    db = get_db()
    f = {"date": request.args.get("date", "").strip(), "room_id": request.args.get("room_id", type=int),
         "q": request.args.get("q", "").strip(), "show": request.args.get("show", "upcoming")}
    where, params = [], []
    day = parse_date(f["date"]) if f["date"] else None
    if f["date"] and day is None:
        flash("Please choose a valid date.", "error")
    if day:
        where.append("b.booking_date = ?"); params.append(day.isoformat())
    elif f["show"] != "all":
        where.append("b.booking_date >= ?"); params.append(date.today().isoformat())
    if f["show"] != "all":
        where.append("b.status = 'active'")
    if f["room_id"]:
        where.append("b.room_id = ?"); params.append(f["room_id"])
    if f["q"]:
        where.append("(LOWER(u.full_name) LIKE ? OR LOWER(u.email) LIKE ?)")
        params += [f"%{f['q'].lower()}%"] * 2
    rows = db.execute(
        "SELECT b.id, b.booking_date, b.status, b.cancel_note, r.name AS room_name, r.building, "
        "u.full_name, u.email, s.start_time || ' - ' || s.end_time AS slot_label "
        "FROM bookings b JOIN rooms r ON r.id = b.room_id JOIN users u ON u.id = b.user_id "
        "JOIN time_slots s ON s.id = b.slot_id "
        + ("WHERE " + " AND ".join(where) if where else "") +
        " ORDER BY b.booking_date, s.start_time, r.name LIMIT 300", params).fetchall()
    all_rooms = db.execute("SELECT id, name FROM rooms ORDER BY building, name").fetchall()
    return render_template("admin/bookings.html", rows=rows, f=f, rooms=all_rooms)


# ---------------------------------------------------------------------------
# PBI-10: admin manages classrooms (add, edit, remove)
# ---------------------------------------------------------------------------
def room_form_problem(form, room_id=None):
    if not form["name"] or not form["building"] or not form["floor"]:
        return "Please fill in the room name, building and floor."
    if not re.fullmatch(r"[A-Za-z0-9 ._-]{2,20}", form["name"]):
        return "The room name can use letters, numbers, spaces, dots and dashes (2 to 20 characters)."
    if form["capacity"] is None or not 1 <= form["capacity"] <= 200:
        return "Seats must be a number from 1 to 200."
    other = get_db().execute("SELECT id FROM rooms WHERE LOWER(name) = LOWER(?) AND id <> ?",
                             (form["name"], room_id or 0)).fetchone()
    if other:
        return f"A room called {form['name']} already exists."
    return None


def read_room_form():
    return {"name": request.form.get("name", "").strip(), "building": request.form.get("building", "").strip(),
            "floor": request.form.get("floor", "").strip(), "capacity": request.form.get("capacity", type=int),
            "features": request.form.get("features", "").strip()}


@app.route("/admin/rooms", methods=["GET", "POST"])
@admin_required
def admin_rooms():
    db = get_db()
    form = {"name": "", "building": "", "floor": "", "capacity": None, "features": ""}
    if request.method == "POST":
        form = read_room_form()
        error = room_form_problem(form)
        if error:
            flash(error, "error")
        else:
            db.execute("INSERT INTO rooms (name, building, floor, capacity, features) VALUES (?, ?, ?, ?, ?)",
                       (form["name"], form["building"], form["floor"], form["capacity"], form["features"] or None))
            db.commit()
            flash(f"Room {form['name']} was added. Students can book it now.", "success")
            return redirect(url_for("admin_rooms"))
    rooms_list = db.execute(
        "SELECT r.*, (SELECT COUNT(*) FROM bookings b WHERE b.room_id = r.id AND b.status = 'active' "
        "AND b.booking_date >= ?) AS upcoming FROM rooms r WHERE r.is_active = 1 ORDER BY r.building, r.name",
        (date.today().isoformat(),)).fetchall()
    buildings = sorted({r["building"] for r in rooms_list})
    return render_template("admin/rooms.html", rooms=rooms_list, form=form, buildings=buildings)


@app.route("/admin/rooms/<int:room_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_room_edit(room_id):
    db = get_db()
    room = db.execute("SELECT * FROM rooms WHERE id = ? AND is_active = 1", (room_id,)).fetchone()
    if room is None:
        abort(404)
    form = dict(room)
    if request.method == "POST":
        form = read_room_form()
        error = room_form_problem(form, room_id)
        if not error:
            # Seats cannot go below the number of students already booked in one slot
            most = db.execute("SELECT COUNT(*) AS n FROM bookings WHERE room_id = ? AND status = 'active' "
                              "AND booking_date >= ? GROUP BY booking_date, slot_id ORDER BY n DESC LIMIT 1",
                              (room_id, date.today().isoformat())).fetchone()
            if most and form["capacity"] < most["n"]:
                error = (f"{most['n']} students already booked one time slot in this room, "
                         f"so it needs at least {most['n']} seats.")
        if error:
            flash(error, "error")
        else:
            db.execute("UPDATE rooms SET name = ?, building = ?, floor = ?, capacity = ?, features = ? WHERE id = ?",
                       (form["name"], form["building"], form["floor"], form["capacity"], form["features"] or None,
                        room_id))
            db.commit()
            flash(f"Room {form['name']} was updated.", "success")
            return redirect(url_for("admin_rooms"))
    return render_template("admin/room_edit.html", room=room, form=form)


@app.route("/admin/rooms/<int:room_id>/remove", methods=["POST"])
@admin_required
def admin_room_remove(room_id):
    db = get_db()
    room = db.execute("SELECT * FROM rooms WHERE id = ? AND is_active = 1", (room_id,)).fetchone()
    if room is None:
        abort(404)
    upcoming = db.execute("SELECT COUNT(*) FROM bookings WHERE room_id = ? AND status = 'active' "
                          "AND booking_date >= ?", (room_id, date.today().isoformat())).fetchone()[0]
    if upcoming:
        flash(f"Room {room['name']} has {upcoming} upcoming booking{'' if upcoming == 1 else 's'}, so it cannot "
              "be removed. Block its time slots first (the bookings will be cancelled with a notice).", "error")
        return redirect(url_for("admin_rooms"))
    # The room is hidden, not deleted, so old bookings and reviews keep their room name.
    db.execute("UPDATE rooms SET is_active = 0 WHERE id = ?", (room_id,))
    db.execute("DELETE FROM blocked_slots WHERE room_id = ? AND block_date >= ?", (room_id, date.today().isoformat()))
    db.commit()
    flash(f"Room {room['name']} was removed. Students no longer see it.", "success")
    return redirect(url_for("admin_rooms"))


# ---------------------------------------------------------------------------
# PBI-14: admin sets the daily booking hours limit
# ---------------------------------------------------------------------------
LIMIT_OPTIONS = [2, 4, 6, 8, 12]


@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    if request.method == "POST":
        limit = request.form.get("daily_limit_hours", type=int)
        if limit not in LIMIT_OPTIONS:
            flash("Please choose one of the limits in the list.", "error")
        else:
            db = get_db()
            db.execute("INSERT INTO settings (key, value) VALUES ('daily_limit_hours', ?) "
                       "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (str(limit),))
            db.commit()
            flash(f"Saved. Students can now book up to {limit} hours per day.", "success")
            return redirect(url_for("admin_settings"))
    return render_template("admin/settings.html", limit=daily_limit_hours(), options=LIMIT_OPTIONS)


# ---------------------------------------------------------------------------
# PBI-16: admin sees reported problems and marks them as fixed
# ---------------------------------------------------------------------------
@app.route("/admin/reports")
@admin_required
def admin_reports():
    rows = get_db().execute(
        "SELECT p.*, r.name AS room_name, r.building, u.full_name, u.email FROM problem_reports p "
        "JOIN rooms r ON r.id = p.room_id JOIN users u ON u.id = p.user_id "
        "ORDER BY p.status = 'resolved', p.created_at DESC, p.id DESC").fetchall()
    return render_template("admin/reports.html", rows=rows)


@app.route("/admin/reports/<int:report_id>/resolve", methods=["POST"])
@admin_required
def admin_report_resolve(report_id):
    db = get_db()
    report = db.execute("SELECT p.*, r.name AS room_name FROM problem_reports p JOIN rooms r ON r.id = p.room_id "
                        "WHERE p.id = ?", (report_id,)).fetchone()
    if report is None:
        abort(404)
    if report["status"] == "open":
        db.execute("UPDATE problem_reports SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
                   (report_id,))
        notify(report["user_id"], f"Your report about {report['room_name']} was fixed",
               f"Thank you for reporting: \"{report['description']}\". The admin marked it as fixed.")
        db.commit()
        flash(f"Report about {report['room_name']} marked as fixed. The student was told.", "success")
    return redirect(url_for("admin_reports"))


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if "--reset" in sys.argv or not os.path.exists(app.config["DATABASE"]):
        init_db(history=True)
        print("Database created with demo data:", app.config["DATABASE"])
    else:
        ensure_schema()   # upgrades a database made by an older version, keeps all data
    app.run(debug=True, port=5001)   # 5001 because macOS uses port 5000 for AirPlay
