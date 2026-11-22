-- StudySlot database schema (SQLite)
-- Sprint 1: PBI-1 .. PBI-9 (booking rules updated: seats per room)
-- Sprint 2: PBI-10 .. PBI-19 (tables at the end, also added to older databases on start)

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS problem_reports;
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS settings;
DROP TABLE IF EXISTS blocked_slots;
DROP TABLE IF EXISTS bookings;
DROP TABLE IF EXISTS time_slots;
DROP TABLE IF EXISTS rooms;
DROP TABLE IF EXISTS users;

-- PBI-1 / PBI-2: students and admins (Task 1.2, Task 2.2)
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'student'
                          CHECK (role IN ('student', 'admin')),
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- PBI-3: classrooms with capacity and location (Task 3.2)
CREATE TABLE rooms (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT    NOT NULL UNIQUE,
    building  TEXT    NOT NULL,
    floor     TEXT    NOT NULL,
    capacity  INTEGER NOT NULL CHECK (capacity > 0),
    features  TEXT,
    is_active INTEGER NOT NULL DEFAULT 1    -- PBI-10: 0 = removed by the admin (history is kept)
);

-- Fixed booking periods used by availability, booking and blocking
CREATE TABLE time_slots (
    id         INTEGER PRIMARY KEY,
    start_time TEXT NOT NULL,   -- 'HH:MM'
    end_time   TEXT NOT NULL    -- 'HH:MM'
);

-- PBI-4 .. PBI-8: bookings (Task 4.2, 5.2, 7.3, 8.3)
CREATE TABLE bookings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    room_id      INTEGER NOT NULL REFERENCES rooms(id),
    booking_date TEXT    NOT NULL,              -- 'YYYY-MM-DD'
    slot_id      INTEGER NOT NULL REFERENCES time_slots(id),
    status       TEXT    NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active', 'cancelled')),
    created_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TEXT,
    cancel_note  TEXT                           -- PBI-18: why the admin cancelled it
);

CREATE INDEX ix_bookings_user ON bookings (user_id, booking_date);

-- PBI-9: time slots blocked by the admin (Task 9.3)
CREATE TABLE blocked_slots (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id    INTEGER NOT NULL REFERENCES rooms(id),
    block_date TEXT    NOT NULL,
    slot_id    INTEGER NOT NULL REFERENCES time_slots(id),
    reason     TEXT    NOT NULL CHECK (reason IN ('class', 'maintenance')),
    note       TEXT,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (room_id, block_date, slot_id)
);

-- BOOKING RULES (safe to run again). Everything below this line is also run on
-- startup, so a database made by an older version is upgraded without losing data.

-- Older versions allowed only ONE booking per room, date and slot. Now a room
-- can be booked by several students until all of its seats are taken.
DROP INDEX IF EXISTS ux_bookings_room_date_slot;

-- One student cannot hold two rooms at the same date and time slot
CREATE UNIQUE INDEX IF NOT EXISTS ux_bookings_user_date_slot
    ON bookings (user_id, booking_date, slot_id)
    WHERE status = 'active';

-- Seats: one booking = one seat. A room accepts at most as many active bookings
-- (per date and time slot) as its capacity. These triggers stop the extra booking
-- even if two students press "Confirm" at the same moment.
CREATE TRIGGER IF NOT EXISTS trg_bookings_capacity_insert
BEFORE INSERT ON bookings
WHEN NEW.status = 'active'
 AND (SELECT COUNT(*) FROM bookings
       WHERE room_id = NEW.room_id AND booking_date = NEW.booking_date
         AND slot_id = NEW.slot_id AND status = 'active')
     >= (SELECT capacity FROM rooms WHERE id = NEW.room_id)
BEGIN
    SELECT RAISE(ABORT, 'room is full');
END;

CREATE TRIGGER IF NOT EXISTS trg_bookings_capacity_update
BEFORE UPDATE OF room_id, booking_date, slot_id, status ON bookings
WHEN NEW.status = 'active'
 AND (SELECT COUNT(*) FROM bookings
       WHERE room_id = NEW.room_id AND booking_date = NEW.booking_date
         AND slot_id = NEW.slot_id AND status = 'active' AND id <> NEW.id)
     >= (SELECT capacity FROM rooms WHERE id = NEW.room_id)
BEGIN
    SELECT RAISE(ABORT, 'room is full');
END;

-- ===========================================================================
-- Sprint 2 tables (CREATE ... IF NOT EXISTS, so older databases get them too)
-- ===========================================================================

-- PBI-14: settings the admin can change (daily booking hours limit)
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_limit_hours', '4');

-- PBI-18 / PBI-19: notices and confirmation emails sent to students
CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    kind       TEXT    NOT NULL CHECK (kind IN ('email', 'notice')),
    subject    TEXT    NOT NULL,
    body       TEXT    NOT NULL,
    is_read    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_notifications_user ON notifications (user_id, is_read);

-- PBI-15: room reviews (one review per finished booking)
CREATE TABLE IF NOT EXISTS reviews (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    room_id    INTEGER NOT NULL REFERENCES rooms(id),
    booking_id INTEGER NOT NULL UNIQUE REFERENCES bookings(id),
    rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment    TEXT,
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- PBI-16: problems reported by students (broken projector, dirty room ...)
CREATE TABLE IF NOT EXISTS problem_reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    room_id     INTEGER NOT NULL REFERENCES rooms(id),
    category    TEXT    NOT NULL,
    description TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT
);
