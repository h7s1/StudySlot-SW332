# StudySlot – Sprint 1 + Sprint 2 (complete)

Classroom booking website for SW332 (Group 4, Section O53).
Built with **Python + Flask** and a **SQLite** database (one file, no server to install).

## How to run

Requires **Python 3.10 or newer** (https://www.python.org/downloads/ – on Windows tick *"Add python.exe to PATH"* during install).

Open a terminal **inside the `studyslot` folder**, then:

```bash
# 1) (optional but recommended) create a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux

# 2) install the libraries
pip install -r requirements.txt

# 3) start the website (creates studyslot.db with demo data the first time)
python app.py
```

Open **http://127.0.0.1:5001** in the browser. Stop the server with `Ctrl + C`.

Reset the database to the demo data at any time: `python app.py --reset`
(the demo data includes a few past bookings with reviews and one problem report, so every page has something to show)
(An older `studyslot.db` is upgraded automatically on start, nothing is deleted.)

Run the automated tests: `python -m pytest -v`

## Demo accounts

| Role    | Email                  | Password    |
|---------|------------------------|-------------|
| Admin   | admin@pnu.edu.sa       | Admin@123   |
| Student | 446000001@pnu.edu.sa   | Student@123 |
| Student | 446000002@pnu.edu.sa   | Student@123 |

New students can sign up from the login page with any `@pnu.edu.sa` email.
To use a different university domain, change `UNIVERSITY_DOMAIN` at the top of `app.py`.

## Project structure

```
studyslot/
├── app.py              all routes and business rules
├── schema.sql          database tables
├── requirements.txt
├── static/style.css
├── templates/          HTML pages (Jinja2)
│   ├── rooms.html      choose a building
│   ├── building.html   the classrooms of one building
│   ├── my_bookings.html upcoming and previous bookings
│   ├── review.html, report_problem.html, notifications.html
│   └── admin/          admin-only pages (dashboard, bookings, rooms, block, reports, settings)
└── tests/test_app.py   43 automated tests (Sprint 1 + Sprint 2)
```

## Database tables

| Table           | Purpose |
|-----------------|---------|
| `users`         | Students and admins (`role` = student / admin), hashed passwords |
| `rooms`         | Classrooms: name, building, floor, capacity, features |
| `time_slots`    | Six 2-hour slots from 08:00 to 20:00 |
| `bookings`      | Student bookings (`status` = active / cancelled). One booking = one seat. Database triggers stop an extra booking when a room's seats (`rooms.capacity`) are all taken for that date and slot |
| `blocked_slots` | Slots closed by the admin for a class or maintenance |
| `settings`      | Admin settings (daily booking hours limit) – Sprint 2 |
| `notifications` | Copies of confirmation emails and notices for each student – Sprint 2 |
| `reviews`       | Star rating and comment for a room, one per finished booking – Sprint 2 |
| `problem_reports` | Problems reported by students, open or fixed – Sprint 2 |

You can open `studyslot.db` with **DB Browser for SQLite** (https://sqlitebrowser.org) to show the data.

## Sprint 1 backlog → code

| PBI | User story | Where |
|-----|------------|-------|
| PBI-1 | Student accesses the system with university email | `/register`, `/login` |
| PBI-2 | Admin logs in with university email | `/login` → `/admin`, `admin_required` |
| PBI-3 | See the list of classrooms | `/rooms` (choose a building) then `/buildings/<building>` (its classrooms) |
| PBI-4 | Check free rooms by date and time | `/availability` (can be limited to one building) |
| PBI-5 | Book a free room | `/book` (confirmation screen + double booking check) |
| PBI-6 | View upcoming bookings | `/my-bookings` |
| PBI-7 | Student cancels a booking | `/bookings/<id>/cancel` (owner only) |
| PBI-8 | Student changes a booking | `/bookings/<id>/change` (owner only + double booking check) |
| PBI-9 | Admin blocks time slots | `/admin/block` (admin only) |

## Sprint 2 backlog → code

| PBI | User story | Where |
|-----|------------|-------|
| PBI-11 | Admin views all bookings | `/admin/bookings` (search by date, room, student) |
| PBI-18 | Admin is warned before blocking a booked slot | `/admin/block` (warning, then cancel with notice + email) |
| PBI-10 | Admin manages classrooms | `/admin/rooms`, `/admin/rooms/<id>/edit`, `/admin/rooms/<id>/remove` |
| PBI-12 | Filter rooms by capacity and building | `/availability?min_seats=…&building=…` |
| PBI-13 | View previous bookings | `/my-bookings?tab=previous` (with *Book again*) |
| PBI-19 | Confirmation email | `send_email()` after book, change, cancel; copies in `/notifications` |
| PBI-14 | Daily booking hours limit | `/admin/settings`; checked in `validate_booking()` |
| PBI-15 | Review a room | `/bookings/<id>/review`; rating on the classroom card |
| PBI-16 | Report a problem | `/rooms/<id>/report`; admin `/admin/reports` |
| PBI-17 | See when a full room is free next | Full cells in `/availability` show the next free time |

## Sending real emails (optional)

Without settings, each email is saved on the student's **Notifications** page and printed in the terminal.
To send real emails, set these before `python app.py` (example for Gmail with an App Password):

```bash
export STUDYSLOT_SMTP_HOST=smtp.gmail.com
export STUDYSLOT_SMTP_PORT=587
export STUDYSLOT_SMTP_USER=your.account@gmail.com
export STUDYSLOT_SMTP_PASSWORD="your app password"
```
(On Windows use `set` instead of `export`.) A booking is never stopped by an email problem.

## Business rules

- Only university emails (`@pnu.edu.sa`) can register or log in.
- Passwords: at least 8 characters with a letter and a number; stored hashed.
- Students cannot open admin pages (HTTP 403).
- Bookings: only future slots, up to 14 days ahead.
- Seats: one booking takes one seat. Several students can book the same room at the same time until all of its seats (the room's capacity) are booked, then the slot shows as *Full*. A room with 2 seats takes 2 bookings, a room with 6 seats takes 6. A student cannot hold two seats or two rooms at the same time.
- Only the owner of a booking can cancel or change it.
- Blocked slots are shown to students as *Blocked* (*Class* or *Maintenance*) in Find a Free Room and under "Blocked times" on the classroom card in its building page. Blocked slots cannot be booked.
- If the admin blocks a slot that students already booked, a warning lists those bookings first. If the admin goes ahead, the bookings are cancelled and each student gets a notice and an email.
- A student can book at most the daily limit (default 4 hours = 2 slots) on one day; the admin can change it.
- Every booking, change and cancel sends a confirmation email.
- A room can be reviewed (1–5 stars) only by the student who used it, once per booking.
- A room with upcoming bookings cannot be removed; a removed room is hidden from students but kept in the history.
- A full slot shows when the room has a free seat again (blocked slots are skipped).
