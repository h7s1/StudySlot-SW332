"""
Automated tests for Sprint 1 (testing tasks 1.3, 2.4, 3.3, 4.3, 5.3, 6.3, 7.4, 8.4, 9.4)
plus the later changes: buildings page, seats per room and visible blocked periods,
and Sprint 2 (testing tasks 11.4, 18.4, 10.4, 12.3, 13.3, 19.3, 14.4, 15.4, 16.3, 17.3).
Run from the project folder:  python -m pytest -v
"""
import os
import sqlite3
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as studyslot  # noqa: E402

TOMORROW = (date.today() + timedelta(days=1)).isoformat()

# Demo rooms (ids): 1 A-101 (4 seats), 2 A-102 (6), 3 A-205 (10), 4 B-110 (2), 5 B-214 (8), 6 C-012 (20)
B110 = 4


@pytest.fixture
def client(tmp_path):
    studyslot.app.config.update(TESTING=True, DATABASE=str(tmp_path / "test.db"))
    studyslot.init_db()
    with studyslot.app.test_client() as c:
        yield c


def login(client, email, password):
    return client.post("/login", data={"email": email, "password": password})


def login_student(client, n=1):
    return login(client, f"44600000{n}@pnu.edu.sa", "Student@123")


def login_admin(client):
    return login(client, "admin@pnu.edu.sa", "Admin@123")


def new_student(client, n):
    """Create one more student account (the demo data only has two) and log in."""
    email = f"44699000{n}@pnu.edu.sa"
    client.get("/logout")
    client.post("/register", data={"full_name": f"Student {n}", "email": email,
                                   "password": "Pass1234", "confirm_password": "Pass1234"})
    return login(client, email, "Pass1234")


def book(client, room_id=1, day=TOMORROW, slot_id=2):
    return client.post("/book", data={"room_id": room_id, "date": day, "slot_id": slot_id},
                       follow_redirects=True)


def block(client, room_id=1, slot_ids=("2",), reason="maintenance", day=TOMORROW):
    return client.post("/admin/block", data={"room_id": room_id, "date": day, "slot_ids": list(slot_ids),
                                             "reason": reason}, follow_redirects=True)


# --- PBI-1: student access with university email --------------------------
def test_register_with_university_email(client):
    r = client.post("/register", data={"full_name": "Sara", "email": "446999999@pnu.edu.sa",
                                       "password": "Pass1234", "confirm_password": "Pass1234"},
                    follow_redirects=True)
    assert b"Account created" in r.data
    r = login(client, "446999999@pnu.edu.sa", "Pass1234")
    assert r.status_code == 302 and r.headers["Location"].endswith("/rooms")


def test_register_rejects_non_university_email(client):
    r = client.post("/register", data={"full_name": "Sara", "email": "sara@gmail.com",
                                       "password": "Pass1234", "confirm_password": "Pass1234"})
    assert b"university email" in r.data


def test_register_rejects_duplicate_and_weak_password(client):
    r = client.post("/register", data={"full_name": "X", "email": "446000001@pnu.edu.sa",
                                       "password": "Pass1234", "confirm_password": "Pass1234"})
    assert b"already exists" in r.data
    r = client.post("/register", data={"full_name": "X", "email": "446111111@pnu.edu.sa",
                                       "password": "123", "confirm_password": "123"})
    assert b"at least 8 characters" in r.data


def test_login_wrong_password(client):
    r = login(client, "446000001@pnu.edu.sa", "wrong-pass1")
    assert b"Wrong email or password" in r.data


def test_pages_need_login(client):
    r = client.get("/rooms")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    r = client.get("/buildings/building-a")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


# --- PBI-2: admin login and access ----------------------------------------
def test_admin_goes_to_dashboard(client):
    r = login_admin(client)
    assert r.headers["Location"].endswith("/admin")


def test_student_blocked_from_admin_pages(client):
    login_student(client)
    assert client.get("/admin").status_code == 403
    assert client.get("/admin/block").status_code == 403


# --- PBI-3: choose a building, then see its classrooms ----------------------
def test_rooms_page_lists_buildings(client):
    login_student(client)
    r = client.get("/rooms")
    assert b"Choose a building" in r.data
    assert b"Building A" in r.data and b"Building B" in r.data and b"Building C" in r.data
    assert b"3 classrooms" in r.data                      # Building A has 3 rooms
    assert b"/buildings/building-a" in r.data
    assert b"A-101" not in r.data                          # rooms are on the building page


def test_building_page_shows_its_classrooms_with_capacity_and_location(client):
    login_student(client)
    r = client.get("/buildings/building-a")
    assert b"A-101" in r.data and b"A-102" in r.data and b"A-205" in r.data
    assert b"4 seats" in r.data and b"Ground floor" in r.data and b"Whiteboard" in r.data
    assert b"B-110" not in r.data and b"C-012" not in r.data


def test_unknown_building_is_404(client):
    login_student(client)
    assert client.get("/buildings/building-z").status_code == 404


# --- PBI-4 / PBI-5: availability and booking -------------------------------
def test_book_room_and_see_it_in_availability(client):
    login_student(client, 1)
    assert b"Booking confirmed" in book(client, room_id=B110).data
    r = client.get(f"/availability?date={TOMORROW}&slot_id=2")
    assert b"Yours" in r.data                       # my own booking is marked
    client.get("/logout")
    login_student(client, 2)
    r = client.get(f"/availability?date={TOMORROW}&slot_id=2")
    assert b"1 of 2 left" in r.data                 # one seat of B-110 is taken


def test_availability_can_show_one_building(client):
    login_student(client)
    r = client.get(f"/availability?date={TOMORROW}&building=building-b")
    assert b"B-110" in r.data and b"B-214" in r.data and b"A-101" not in r.data
    r = client.get(f"/availability?date={TOMORROW}")
    assert b"A-101" in r.data and b"B-110" in r.data


def test_cannot_book_past_date(client):
    login_student(client)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    assert b"in the past" in book(client, day=yesterday).data


# --- Seats: a room takes as many students as it has seats -------------------
def test_several_students_can_share_a_room_with_free_seats(client):
    login_student(client, 1)
    assert b"Booking confirmed" in book(client, room_id=1).data      # A-101 has 4 seats
    new_student(client, 2)
    assert b"Booking confirmed" in book(client, room_id=1).data
    new_student(client, 3)
    assert b"Booking confirmed" in book(client, room_id=1).data
    new_student(client, 4)                                            # a student who has not booked
    r = client.get(f"/availability?date={TOMORROW}&slot_id=2")
    assert b"1 of 4 left" in r.data                                   # 3 of 4 seats are taken


def test_room_is_full_when_all_seats_are_booked(client):
    login_student(client, 1)
    assert b"Booking confirmed" in book(client, room_id=B110).data   # B-110 has 2 seats
    client.get("/logout")
    login_student(client, 2)
    assert b"Booking confirmed" in book(client, room_id=B110).data
    new_student(client, 3)
    r = book(client, room_id=B110)
    assert b"is full" in r.data and b"Booking confirmed" not in r.data
    r = client.get(f"/availability?date={TOMORROW}&slot_id=2&building=building-b")
    assert b"Full</span>" in r.data and b"Free at 12:00" in r.data   # PBI-17: next free time
    assert b"B-110" not in client.get("/my-bookings").data


def test_cancelling_frees_a_seat(client):
    login_student(client, 1)
    book(client, room_id=B110)                                        # booking id 1
    client.get("/logout")
    login_student(client, 2)
    book(client, room_id=B110)
    new_student(client, 3)
    assert b"is full" in book(client, room_id=B110).data
    client.get("/logout")
    login_student(client, 1)
    assert b"was cancelled" in client.post("/bookings/1/cancel", follow_redirects=True).data
    new_student(client, 3)
    assert b"Booking confirmed" in book(client, room_id=B110).data


def test_student_cannot_take_two_seats_in_the_same_room(client):
    login_student(client)
    assert b"Booking confirmed" in book(client, room_id=1).data
    assert b"already have another booking" in book(client, room_id=1).data


def test_database_itself_stops_the_extra_booking(client):
    """Even if the page checks are skipped, the database refuses booking number capacity + 1."""
    db = sqlite3.connect(studyslot.app.config["DATABASE"])
    db.executemany("INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, 'x', 'student')",
                   [("U3", "446000003@pnu.edu.sa"), ("U4", "446000004@pnu.edu.sa")])
    insert = "INSERT INTO bookings (user_id, room_id, booking_date, slot_id) VALUES (?, ?, ?, 2)"
    db.execute(insert, (2, B110, TOMORROW))
    db.execute(insert, (3, B110, TOMORROW))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(insert, (4, B110, TOMORROW))               # 3rd seat in a 2-seat room
    # moving a booking into a full room is refused too
    db.execute(insert, (4, 5, TOMORROW))                      # B-214 (8 seats) is fine
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE bookings SET room_id = ? WHERE user_id = 4", (B110,))
    # one student cannot hold two rooms at the same time
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(insert, (2, 5, TOMORROW))
    # cancelling is always allowed
    db.execute("UPDATE bookings SET status = 'cancelled' WHERE user_id = 2")
    db.close()


def test_old_database_is_upgraded_without_losing_bookings(client):
    login_student(client, 1)
    book(client, room_id=B110)
    path = studyslot.app.config["DATABASE"]
    db = sqlite3.connect(path)       # make it look like the old version (one booking per room)
    db.executescript(
        "DROP TRIGGER trg_bookings_capacity_insert; DROP TRIGGER trg_bookings_capacity_update;"
        "DROP INDEX ux_bookings_user_date_slot;"
        "CREATE UNIQUE INDEX ux_bookings_room_date_slot ON bookings (room_id, booking_date, slot_id) "
        "WHERE status = 'active';")
    db.close()
    studyslot.ensure_schema()
    db = sqlite3.connect(path)
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master")}
    assert "ux_bookings_room_date_slot" not in names
    assert {"trg_bookings_capacity_insert", "trg_bookings_capacity_update", "ux_bookings_user_date_slot"} <= names
    assert db.execute("SELECT COUNT(*) FROM bookings").fetchone()[0] == 1      # nothing was lost
    db.close()
    client.get("/logout")
    login_student(client, 2)
    assert b"Booking confirmed" in book(client, room_id=B110).data             # shared room works now


# --- PBI-6: upcoming bookings ---------------------------------------------
def test_my_bookings_lists_only_my_bookings(client):
    login_student(client, 1)
    book(client, room_id=1)
    client.get("/logout")
    login_student(client, 2)
    book(client, room_id=3)
    r = client.get("/my-bookings")
    assert b"A-205" in r.data and b"A-101" not in r.data


# --- PBI-7: cancel ---------------------------------------------------------
def test_owner_can_cancel_and_others_cannot(client):
    login_student(client, 1)
    book(client)
    client.get("/logout")
    login_student(client, 2)
    assert client.post("/bookings/1/cancel").status_code == 403
    client.get("/logout")
    login_student(client, 1)
    r = client.post("/bookings/1/cancel", follow_redirects=True)
    assert b"was cancelled" in r.data
    client.get("/logout")
    login_student(client, 2)
    assert b"Booking confirmed" in book(client).data   # the seat is free again


# --- PBI-8: change ---------------------------------------------------------
def test_change_booking_with_seat_check(client):
    login_student(client, 1)
    book(client, room_id=B110, slot_id=3)
    client.get("/logout")
    login_student(client, 2)
    book(client, room_id=B110, slot_id=3)                 # B-110 is now full at slot 3
    new_student(client, 3)
    book(client, room_id=1, slot_id=2)                    # booking id 3
    r = client.post("/bookings/3/change", data={"room_id": B110, "date": TOMORROW, "slot_id": 3},
                    follow_redirects=True)
    assert b"is full" in r.data
    r = client.post("/bookings/3/change", data={"room_id": B110, "date": TOMORROW, "slot_id": 4},
                    follow_redirects=True)
    assert b"Booking changed" in r.data
    assert client.post("/bookings/1/change", data={"room_id": 1, "date": TOMORROW, "slot_id": 5}).status_code == 403


# --- PBI-9: admin blocks slots ---------------------------------------------
def test_blocked_slot_cannot_be_booked(client):
    login_admin(client)
    r = block(client, room_id=1, slot_ids=["2"], reason="maintenance")
    assert b"Blocked A-101" in r.data
    client.get("/logout")
    login_student(client)
    assert b"not available" in book(client, room_id=1, slot_id=2).data
    r = client.get(f"/availability?date={TOMORROW}&slot_id=2")
    assert b"Blocked" in r.data and b"Maintenance" in r.data


def test_admin_sees_the_block_in_the_list(client):
    login_admin(client)
    block(client, room_id=1, slot_ids=["2", "3"], reason="class")
    r = client.get("/admin/block")
    assert b"A-101" in r.data and b"Building A" in r.data
    assert b"10:00 - 12:00" in r.data and b"12:00 - 14:00" in r.data


def test_students_see_the_blocked_period_on_the_classroom_card(client):
    login_admin(client)
    block(client, room_id=1, slot_ids=["2", "3"], reason="class")      # two slots in a row
    client.get("/logout")
    login_student(client)
    r = client.get("/buildings/building-a")
    assert b"Blocked times" in r.data
    assert b"10:00 - 14:00" in r.data and b"Class" in r.data           # joined into one period
    assert b"Blocked times" not in client.get("/buildings/building-b").data
    r = client.get(f"/availability?date={TOMORROW}&building=building-a")
    assert r.data.count(b"Blocked</span>") == 2                         # both slots in the grid


def test_removed_block_disappears_for_students(client):
    login_admin(client)
    block(client, room_id=1, slot_ids=["2"])
    client.post("/admin/block/1/remove", follow_redirects=True)
    client.get("/logout")
    login_student(client)
    assert b"Blocked times" not in client.get("/buildings/building-a").data
    assert b"Booking confirmed" in book(client, room_id=1, slot_id=2).data


def test_admin_is_warned_before_blocking_a_booked_slot(client):
    """PBI-18 (was: the admin cannot block a booked slot). Now the admin sees a warning first."""
    login_student(client)
    book(client, room_id=1, slot_id=2)
    client.get("/logout")
    login_admin(client)
    r = block(client, room_id=1, slot_ids=["2"], reason="class")
    assert b"already booked this time" in r.data and b"446000001@pnu.edu.sa" in r.data
    assert b"Block and cancel 1 booking" in r.data
    assert b"Upcoming blocked slots</h3>" in r.data and b"<span class=\"count\">0</span>" in r.data   # nothing blocked yet


# ===========================================================================
# Sprint 2
# ===========================================================================
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


def db_conn():
    db = sqlite3.connect(studyslot.app.config["DATABASE"])
    db.row_factory = sqlite3.Row
    return db


def past_booking(user_id=2, room_id=1, slot_id=2, day=YESTERDAY):
    """A booking that already happened (the website itself only allows future bookings)."""
    db = db_conn()
    cur = db.execute("INSERT INTO bookings (user_id, room_id, booking_date, slot_id) VALUES (?, ?, ?, ?)",
                     (user_id, room_id, day, slot_id))
    db.commit()
    db.close()
    return cur.lastrowid


# --- PBI-11: admin views all bookings (Task 11.4) ---------------------------
def test_admin_sees_all_bookings_and_can_search(client):
    login_student(client, 1)
    book(client, room_id=1, slot_id=2)
    client.get("/logout")
    login_student(client, 2)
    book(client, room_id=5, slot_id=3)
    client.get("/logout")
    login_admin(client)
    r = client.get("/admin/bookings")
    assert b"446000001@pnu.edu.sa" in r.data and b"446000002@pnu.edu.sa" in r.data
    assert b"2 bookings" in r.data
    r = client.get("/admin/bookings?q=second")                      # search by student name
    assert b"446000002@pnu.edu.sa" in r.data and b"446000001@pnu.edu.sa" not in r.data
    r = client.get("/admin/bookings?room_id=1")                     # search by room
    assert b"446000001@pnu.edu.sa" in r.data and b"446000002@pnu.edu.sa" not in r.data
    r = client.get(f"/admin/bookings?date={YESTERDAY}")              # search by date
    assert b"No bookings match" in r.data


def test_students_cannot_open_the_new_admin_pages(client):
    login_student(client)
    for url in ("/admin/bookings", "/admin/rooms", "/admin/rooms/1/edit", "/admin/settings", "/admin/reports"):
        assert client.get(url).status_code == 403, url
    assert client.post("/admin/rooms/1/remove").status_code == 403
    assert client.post("/admin/settings", data={"daily_limit_hours": 12}).status_code == 403


# --- PBI-18: warning before blocking a booked slot (Task 18.4) --------------
def test_blocking_a_booked_slot_cancels_it_and_tells_the_student(client):
    login_student(client)
    book(client, room_id=1, slot_id=2)
    client.get("/logout")
    login_admin(client)
    r = client.post("/admin/block", data={"room_id": 1, "date": TOMORROW, "slot_ids": ["2"], "reason": "class",
                                          "note": "SW332 lecture", "confirm": "yes"}, follow_redirects=True)
    assert b"Blocked A-101" in r.data and b"1 booking cancelled" in r.data
    db = db_conn()
    b = db.execute("SELECT status, cancel_note FROM bookings WHERE id = 1").fetchone()
    db.close()
    assert b["status"] == "cancelled" and "SW332 lecture" in b["cancel_note"]
    client.get("/logout")
    login_student(client)
    assert b"<span class=\"nav-badge\">" in client.get("/my-bookings").data     # unread notice
    r = client.get("/notifications")
    assert b"Your booking in A-101 was cancelled" in r.data and b"SW332 lecture" in r.data
    assert b"Cancelled by admin" in client.get("/my-bookings?tab=previous").data
    assert b"Blocked" in client.get(f"/availability?date={TOMORROW}&slot_id=2").data


def test_do_not_block_keeps_the_booking(client):
    login_student(client)
    book(client, room_id=1, slot_id=2)
    client.get("/logout")
    login_admin(client)
    block(client, room_id=1, slot_ids=["2"], reason="class")        # only the warning, no confirm
    db = db_conn()
    assert db.execute("SELECT status FROM bookings WHERE id = 1").fetchone()[0] == "active"
    assert db.execute("SELECT COUNT(*) FROM blocked_slots").fetchone()[0] == 0
    db.close()


# --- PBI-10: admin manages classrooms (Task 10.4) ---------------------------
def room_data(**kw):
    data = {"name": "D-101", "building": "Building D", "floor": "Ground floor", "capacity": 5,
            "features": "Whiteboard"}
    data.update(kw)
    return data


def test_admin_adds_a_room_and_students_can_book_it(client):
    login_admin(client)
    r = client.post("/admin/rooms", data=room_data(), follow_redirects=True)
    assert b"Room D-101 was added" in r.data
    assert b"A room called D-101 already exists" in client.post("/admin/rooms", data=room_data()).data
    assert b"Seats must be a number" in client.post("/admin/rooms", data=room_data(name="D-102", capacity=0)).data
    client.get("/logout")
    login_student(client)
    assert b"Building D" in client.get("/rooms").data
    assert b"D-101" in client.get("/buildings/building-d").data
    assert b"Booking confirmed" in book(client, room_id=7).data


def test_admin_edits_a_room_but_not_below_booked_seats(client):
    login_student(client, 1)
    book(client, room_id=1)
    client.get("/logout")
    login_student(client, 2)
    book(client, room_id=1)                                          # 2 students in A-101 at slot 2
    client.get("/logout")
    login_admin(client)
    r = client.post("/admin/rooms/1/edit", data=room_data(name="A-101", building="Building A", capacity=1))
    assert b"needs at least 2 seats" in r.data
    r = client.post("/admin/rooms/1/edit", data=room_data(name="A-101", building="Building A", capacity=12,
                                                         features="Projector"), follow_redirects=True)
    assert b"Room A-101 was updated" in r.data
    client.get("/logout")
    login_student(client, 1)
    r = client.get("/buildings/building-a")
    assert b"12 seats" in r.data and b"Projector" in r.data


def test_room_with_upcoming_bookings_cannot_be_removed(client):
    login_student(client)
    book(client, room_id=1)
    client.get("/logout")
    login_admin(client)
    r = client.post("/admin/rooms/1/remove", follow_redirects=True)
    assert b"cannot be removed" in r.data
    r = client.post("/admin/rooms/2/remove", follow_redirects=True)  # A-102 has no bookings
    assert b"Room A-102 was removed" in r.data
    client.get("/logout")
    login_student(client)
    assert b"A-102" not in client.get("/buildings/building-a").data
    assert b"A-102" not in client.get(f"/availability?date={TOMORROW}").data
    assert b"valid room" in book(client, room_id=2, slot_id=4).data


# --- PBI-12: filter by capacity and building (Task 12.3) --------------------
def test_capacity_filter_alone_and_with_building(client):
    login_student(client)
    r = client.get(f"/availability?date={TOMORROW}&min_seats=10")
    assert b"A-205" in r.data and b"C-012" in r.data                 # 10 and 20 seats
    assert b"A-101" not in r.data and b"B-214" not in r.data
    r = client.get(f"/availability?date={TOMORROW}&min_seats=6&building=building-a")
    assert b"A-102" in r.data and b"A-205" in r.data and b"A-101" not in r.data and b"C-012" not in r.data
    r = client.get(f"/availability?date={TOMORROW}&min_seats=20&building=building-b")
    assert b"No rooms match these filters" in r.data


# --- PBI-13: previous bookings (Task 13.3) ----------------------------------
def test_previous_bookings_with_book_again(client):
    past_booking(user_id=2, room_id=4)                               # B-110 yesterday (used)
    login_student(client)
    book(client, room_id=1, slot_id=3)
    client.post("/bookings/2/cancel")                                # cancelled
    r = client.get("/my-bookings?tab=previous")
    assert b"B-110" in r.data and b"Used" in r.data
    assert b"A-101" in r.data and b"Cancelled" in r.data
    assert b"Book again" in r.data and b"building=building-b#room-4" in r.data
    r = client.get("/my-bookings")
    assert b"B-110" not in r.data and b"No upcoming bookings" in r.data
    client.get("/logout")
    login_student(client, 2)
    assert b"B-110" not in client.get("/my-bookings?tab=previous").data   # only my own history


# --- PBI-19: confirmation emails (Task 19.3) --------------------------------
def test_confirmation_email_for_book_change_and_cancel(client):
    login_student(client)
    r = book(client, room_id=1, slot_id=2)
    assert b"confirmation email was sent to 446000001@pnu.edu.sa" in r.data
    client.post("/bookings/1/change", data={"room_id": 3, "date": TOMORROW, "slot_id": 4})
    client.post("/bookings/1/cancel")
    db = db_conn()
    mails = db.execute("SELECT subject, body FROM notifications WHERE user_id = 2 AND kind = 'email' "
                       "ORDER BY id").fetchall()
    db.close()
    assert [m["subject"].split(":")[0] for m in mails] == ["Booking confirmed", "Booking changed", "Booking cancelled"]
    assert "A-205" in mails[1]["body"] and "Before the change: A-101" in mails[1]["body"]
    r = client.get("/notifications")
    assert b"Email sent to 446000001@pnu.edu.sa" in r.data and r.data.count(b"<article") == 3


# --- PBI-14: daily booking hours limit (Task 14.4) ---------------------------
def test_daily_limit_for_booking_and_change(client):
    login_student(client)
    assert b"Booking confirmed" in book(client, room_id=1, slot_id=1).data
    assert b"Booking confirmed" in book(client, room_id=1, slot_id=2).data      # 4 hours = default limit
    r = book(client, room_id=1, slot_id=3)
    assert b"at most 4 hours per day" in r.data
    day2 = (date.today() + timedelta(days=2)).isoformat()
    book(client, room_id=1, slot_id=3, day=day2)                                  # booking id 3
    r = client.post("/bookings/3/change", data={"room_id": 1, "date": TOMORROW, "slot_id": 3},
                    follow_redirects=True)
    assert b"at most 4 hours per day" in r.data                                   # change is checked too
    client.get("/logout")
    login_admin(client)
    assert b"Please choose one of the limits" in client.post("/admin/settings", data={"daily_limit_hours": 5}).data
    r = client.post("/admin/settings", data={"daily_limit_hours": 6}, follow_redirects=True)
    assert b"up to 6 hours per day" in r.data
    client.get("/logout")
    login_student(client)
    assert b"Booking confirmed" in book(client, room_id=1, slot_id=3).data


# --- PBI-15: review a room (Task 15.4) --------------------------------------
def test_review_a_room_after_using_it(client):
    used = past_booking(user_id=2, room_id=1)
    login_student(client)
    book(client, room_id=1, slot_id=3)                                # a future booking (id 2)
    assert b"only after you have used it" in client.get("/bookings/2/review", follow_redirects=True).data
    assert b"choose a rating" in client.post(f"/bookings/{used}/review", data={"rating": 0}).data
    r = client.post(f"/bookings/{used}/review", data={"rating": 4, "comment": "Quiet and clean"},
                    follow_redirects=True)
    assert b"review of A-101 was saved" in r.data and b"You rated it 4/5" in r.data
    assert b"already reviewed" in client.get(f"/bookings/{used}/review", follow_redirects=True).data
    r = client.get("/buildings/building-a")
    assert b"4.0 / 5" in r.data and b"(1 review)" in r.data and b"Quiet and clean" in r.data
    client.get("/logout")
    login_student(client, 2)
    assert client.get(f"/bookings/{used}/review").status_code == 403   # only the student who used it


# --- PBI-16: report a problem (Task 16.3) -----------------------------------
def test_report_a_problem_and_admin_marks_it_fixed(client):
    login_student(client)
    assert b"Report a problem" in client.get("/buildings/building-a").data
    assert b"at least 10 characters" in client.post("/rooms/1/report", data={
        "category": "Cleanliness", "description": "dirty"}).data
    r = client.post("/rooms/1/report", data={"category": "Equipment (projector, screen, board)",
                                             "description": "The projector does not turn on."},
                    follow_redirects=True)
    assert b"report about A-101 was sent" in r.data
    client.get("/logout")
    login_admin(client)
    assert b"1 open report" in client.get("/admin").data
    r = client.get("/admin/reports")
    assert b"The projector does not turn on." in r.data and b"446000001@pnu.edu.sa" in r.data
    r = client.post("/admin/reports/1/resolve", follow_redirects=True)
    assert b"marked as fixed" in r.data and b"0 open" in r.data
    client.get("/logout")
    login_student(client)
    assert b"Your report about A-101 was fixed" in client.get("/notifications").data


# --- PBI-17: when is a full room free next (Task 17.3) -----------------------
def test_full_room_shows_next_free_time_and_skips_blocked_slots(client):
    login_student(client, 1)
    book(client, room_id=B110, slot_id=2)
    client.get("/logout")
    login_student(client, 2)
    book(client, room_id=B110, slot_id=2)                            # B-110 (2 seats) is full at 10:00
    client.get("/logout")
    login_admin(client)
    block(client, room_id=B110, slot_ids=["3"], reason="maintenance")  # 12:00 is blocked
    client.get("/logout")
    new_student(client, 3)
    r = client.get(f"/availability?date={TOMORROW}&slot_id=2&building=building-b")
    assert b"Free at 14:00" in r.data                                 # 12:00 is skipped (blocked)


def test_room_full_all_day_shows_the_next_day(client):
    day = (date.today() + timedelta(days=3)).isoformat()
    db = db_conn()
    db.executemany("INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, 'x')",
                   [("U3", "446000003@pnu.edu.sa"), ("U4", "446000004@pnu.edu.sa")])
    for user in (3, 4):                                               # fill both seats of B-110 all day
        for slot in range(1, 7):
            db.execute("INSERT INTO bookings (user_id, room_id, booking_date, slot_id) VALUES (?, ?, ?, ?)",
                       (user, B110, day, slot))
    db.commit()
    db.close()
    nxt = (date.today() + timedelta(days=4))
    login_student(client)
    r = client.get(f"/availability?date={day}&slot_id=6&building=building-b")
    assert f"Free {nxt.strftime('%a %d')}, 08:00".encode() in r.data


# --- Upgrade: a Sprint 1 database gets the Sprint 2 tables -------------------
def test_sprint1_database_is_upgraded_for_sprint2(client):
    path = studyslot.app.config["DATABASE"]
    db = sqlite3.connect(path)
    db.executescript("DROP TABLE settings; DROP TABLE notifications; DROP TABLE reviews; DROP TABLE problem_reports;")
    try:   # DROP COLUMN needs SQLite 3.35+ (older Python builds skip this part)
        db.executescript("ALTER TABLE rooms DROP COLUMN is_active; ALTER TABLE bookings DROP COLUMN cancel_note;")
    except sqlite3.OperationalError:
        pass
    db.close()
    studyslot.ensure_schema()
    db = sqlite3.connect(path)
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"settings", "notifications", "reviews", "problem_reports"} <= names
    assert "is_active" in [r[1] for r in db.execute("PRAGMA table_info(rooms)")]
    assert db.execute("SELECT value FROM settings WHERE key = 'daily_limit_hours'").fetchone()[0] == "4"
    db.close()
    login_student(client)
    assert b"Booking confirmed" in book(client).data
