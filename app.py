"""
StudySlot - classroom booking website (SW332, Group 4, Section O53)
Sprint 1 scope: PBI-1 .. PBI-9
(buildings page, visible blocked periods and seats per room were added later)

Run:   python app.py           (creates studyslot.db on first run)
Reset: python app.py --reset   (deletes all data and re-creates demo data)
"""
import os
import re
import sqlite3
import sys
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


def init_db(seed=True):
    """Create all tables (drops old ones) and optionally add demo data."""
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
    db.commit()
    db.close()


def ensure_schema():
    """Upgrade an older studyslot.db to the current booking rules (seats per room).

    Runs the "BOOKING RULES" part of schema.sql. It is safe to run every time:
    nothing is deleted, bookings and accounts stay as they are.
    """
    with open(os.path.join(BASE_DIR, "schema.sql"), encoding="utf-8") as f:
        text = f.read()
    rules = text[text.index("-- BOOKING RULES"):]
    db = sqlite3.connect(app.config["DATABASE"])
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


def get_rooms():
    return get_db().execute("SELECT * FROM rooms ORDER BY building, name").fetchall()


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


def validate_booking(user_id, room_id, date_str, slot_id, exclude_booking_id=None):
    """Check every booking rule. Returns (error_message, None) or (None, details)."""
    db = get_db()
    day = parse_date(date_str)
    if day is None:
        return "Please choose a valid date.", None
    room = db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
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
    }


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
    blocks = blocked_periods([r["id"] for r in building["rooms"]])
    return render_template("building.html", building=building, buildings=buildings, blocks=blocks)


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
    day = parse_date(date_str)

    # Optional filter: only the rooms of one building (an unknown building shows all rooms)
    building = next((b for b in buildings if b["slug"] == building_slug), None)
    building_slug = building["slug"] if building else ""
    shown_rooms = building["rooms"] if building else get_rooms()

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
                    cells.append({"slot": s, "status": "full"})
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
                           buildings=buildings, building=building, building_slug=building_slug)


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
        flash(f"Booking confirmed: {details['room']['name']} on {details['day'].isoformat()}, "
              f"{details['slot']['label']}.", "success")
        return redirect(url_for("my_bookings"))

    return render_template("book_confirm.html", **details)   # details include seats_left


# ---------------------------------------------------------------------------
# PBI-6: view upcoming bookings
# ---------------------------------------------------------------------------
@app.route("/my-bookings")
@student_required
def my_bookings():
    rows = get_db().execute(
        "SELECT b.id, b.booking_date, r.name AS room_name, r.building, r.floor, r.capacity, "
        "s.start_time, s.end_time, s.start_time || ' - ' || s.end_time AS slot_label "
        "FROM bookings b JOIN rooms r ON r.id = b.room_id JOIN time_slots s ON s.id = b.slot_id "
        "WHERE b.user_id = ? AND b.status = 'active' AND b.booking_date >= ? "
        "ORDER BY b.booking_date, s.start_time",
        (g.user["id"], date.today().isoformat())).fetchall()
    now = datetime.now()
    upcoming = [b for b in rows
                if b["booking_date"] > now.date().isoformat() or b["end_time"] > now.strftime("%H:%M")]
    return render_template("my_bookings.html", bookings=upcoming)


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
        db.commit()
        flash(f"Your booking for {booking['room_name']} was cancelled. Your seat is free for other students now.",
              "success")
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
                    flash(f"Booking changed to {details['room']['name']} on {details['day'].isoformat()}, "
                          f"{details['slot']['label']}.", "success")
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
        "rooms": db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0],
        "students": db.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0],
        "upcoming_bookings": db.execute(
            "SELECT COUNT(*) FROM bookings WHERE status = 'active' AND booking_date >= ?", (today,)).fetchone()[0],
        "upcoming_blocks": db.execute(
            "SELECT COUNT(*) FROM blocked_slots WHERE block_date >= ?", (today,)).fetchone()[0],
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
        room = db.execute("SELECT * FROM rooms WHERE id = ?", (form["room_id"],)).fetchone()
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

        if error:
            flash(error, "error")
        else:
            added, skipped = [], []
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
                if db.execute("SELECT 1 FROM bookings WHERE room_id = ? AND booking_date = ? AND slot_id = ? "
                              "AND status = 'active'", (room["id"], day.isoformat(), slot_id)).fetchone():
                    skipped.append(f"{slot['label']} (a student already booked it)")
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
            if skipped:
                flash("Not blocked: " + "; ".join(skipped), "error")
            if added and not skipped:
                return redirect(url_for("admin_block"))

    blocks = db.execute(
        "SELECT bs.id, bs.block_date, bs.reason, bs.note, r.name AS room_name, r.building, "
        "t.start_time || ' - ' || t.end_time AS slot_label "
        "FROM blocked_slots bs JOIN rooms r ON r.id = bs.room_id JOIN time_slots t ON t.id = bs.slot_id "
        "WHERE bs.block_date >= ? ORDER BY bs.block_date, t.start_time, r.name",
        (date.today().isoformat(),)).fetchall()
    return render_template("admin/block.html", form=form, rooms=get_rooms(),
                           slots=get_slots(), blocks=blocks)


@app.route("/admin/block/<int:block_id>/remove", methods=["POST"])
@admin_required
def admin_unblock(block_id):
    db = get_db()
    db.execute("DELETE FROM blocked_slots WHERE id = ?", (block_id,))
    db.commit()
    flash("The time slot is open for booking again.", "success")
    return redirect(url_for("admin_block"))


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if "--reset" in sys.argv or not os.path.exists(app.config["DATABASE"]):
        init_db()
        print("Database created with demo data:", app.config["DATABASE"])
    else:
        ensure_schema()   # upgrades a database made by an older version, keeps all data
    app.run(debug=True, port=5001)   # 5001 because macOS uses port 5000 for AirPlay
