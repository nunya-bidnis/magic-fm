"""
One-off seed script - creates a dummy DJ/admin account for local testing.

Run this ON THE VPS (or wherever database.py/security.py actually live),
in the same directory as main.py:

    python3 create_dummy_dj.py

Then log in at /dj-login.html with:
    username: majik
    password: Assword1

Flagged is_admin=1 so this same account also gets you into /admin.html
(through the SSH tunnel from ADMIN-ACCESS.md). Set is_admin=0 below if you
only want DJ-side access.

Delete this file after running it once - it's a one-time bootstrap tool,
not something that should sit on a production box with a known password
in it.
"""

from database import db, init_db
from security import PasswordManager, StreamKeyManager

USERNAME = "majik"
EMAIL = "majik@mdntmass.live"
PASSWORD = "Assword1"
IS_ADMIN = 1  # set to 0 for a DJ-only test account

init_db()

existing = db.execute_one("SELECT id FROM djs WHERE username = ?", (USERNAME,))
if existing:
    print(f"'{USERNAME}' already exists (dj_id={existing[0]}). Nothing created.")
else:
    password_hash = PasswordManager.hash_password(PASSWORD)

    dj_id = db.execute_update(
        """
        INSERT INTO djs
            (username, email, password_hash, display_name, is_active, is_admin,
             created_by, notes, must_change_password)
        VALUES (?, ?, ?, ?, 1, ?, NULL, ?, 0)
        """,
        (USERNAME, EMAIL, password_hash, "Majik", IS_ADMIN, "dummy test account - seeded locally"),
    )

    stream_key = StreamKeyManager.create_key_for_dj(dj_id)

    print(f"Created dj_id={dj_id}, username={USERNAME}, is_admin={bool(IS_ADMIN)}")
    print(f"Stream key: {stream_key}")
    print(f"Log in at /dj-login.html with {USERNAME} / {PASSWORD}")
