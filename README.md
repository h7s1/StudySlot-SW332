# StudySlot – Sprint 1

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
│   └── admin/          admin-only pages
└── tests/test_app.py   27 automated tests
```

## Database tables

| Table           | Purpose |
|-----------------|---------|
| `users`         | Students and admins (`role` = student / admin), hashed passwords |
| `rooms`         | Classrooms: name, building, floor, capacity, features |
| `time_slots`    | Six 2-hour slots from 08:00 to 20:00 |
| `bookings`      | Student bookings (`status` = active / cancelled). One booking = one seat. Database triggers stop an extra booking when a room's seats (`rooms.capacity`) are all taken for that date and slot |
| `blocked_slots` | Slots closed by the admin for a class or maintenance |

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

## Business rules

- Only university emails (`@pnu.edu.sa`) can register or log in.
- Passwords: at least 8 characters with a letter and a number; stored hashed.
- Students cannot open admin pages (HTTP 403).
- Bookings: only future slots, up to 14 days ahead.
- Seats: one booking takes one seat. Several students can book the same room at the same time until all of its seats (the room's capacity) are booked, then the slot shows as *Full*. A room with 2 seats takes 2 bookings, a room with 6 seats takes 6. A student cannot hold two seats or two rooms at the same time.
- Only the owner of a booking can cancel or change it.
- Blocked slots are shown to students as *Blocked* (*Class* or *Maintenance*) in Find a Free Room and under "Blocked times" on the classroom card in its building page. Blocked slots cannot be booked.
- The admin cannot block a slot that a student has already booked (the booking must be cancelled first).
