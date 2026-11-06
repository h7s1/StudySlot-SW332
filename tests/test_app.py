"""
Automated tests for Sprint 1 (testing tasks 1.3, 2.4, 3.3, 4.3, 5.3, 6.3, 7.4, 8.4, 9.4)
plus the later changes: buildings page, seats per room and visible blocked periods.
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
    assert b"no seats left" in r.data
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


def test_admin_cannot_block_a_booked_slot(client):
    login_student(client)
    book(client, room_id=1, slot_id=2)
    client.get("/logout")
    login_admin(client)
    r = block(client, room_id=1, slot_ids=["2"], reason="class")
    assert b"already booked it" in r.data
