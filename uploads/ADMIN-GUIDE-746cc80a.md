# Magic.fm - Admin & Login System

How accounts work, and how you run the station.

---

## What Changed, And Why

The first build had **open self-registration**. Anyone who found `/dj-login.html`
could click "Register here," create an account, and receive a working stream key
with no approval from you.

That is the opposite of your model. You interview people. You vet them. The
software was handing out broadcast access to anyone who filled in a form.

Public registration is now **disabled by default**. Accounts exist only because you
created them.

---

## Your Admin Panel

**`/admin.html`** — the menu you asked about. Not linked from public navigation.

From there you can:

- **Add a DJ** — set their username, password, display name, and private notes
- **See the roster** — status, last login, active key count, your notes
- **Suspend** — kills login, stream keys, and metadata tokens in one action
- **Reactivate** — restores access and issues a *fresh* key
- **Reset password** — set a new one and force them to change it
- **Revoke keys** — panic button if a key leaks
- **Manage autoplay** — library, queue, moderation
- **Read the audit log** — who did what, when, from where

Non-admins hitting `/admin.html` get an access-denied screen. That screen is
cosmetic; the real boundary is server-side on every endpoint.

---

## First-Time Setup

Run these in order on the VPS:

```bash
# 1. Base tables (skip if the database already exists)
python3 -c "from database import db; db.init_tables()"

# 2. Now-playing support
python3 migrate_nowplaying.py

# 3. Admin roles + autoplay
python3 migrate_admin_autoplay.py

# 4. Create your admin account
python3 create_admin.py
```

`create_admin.py` prompts for username, email and password. It uses a hidden
password prompt so the value never lands in your shell history.

Both migrations are safe to run more than once.

Then log in at `/dj-login.html` and go to `/admin.html`.

---

## Adding a DJ

1. Interview and vet them
2. Open `/admin.html` → **Add a DJ**
3. Enter username, email, an initial password, and your notes
4. Click **Create Account**
5. The panel shows their username, password, and stream key — **copy these now**
6. Send them the credentials
7. On first login they are prompted to set their own password

**Why they change the password:** if they kept the one you chose, you would
permanently know every DJ's password. That is bad for them and worse for you — it
makes you the single point of compromise for the whole roster.

### Private Notes

Interview notes, musical style, how you know them, anything. Tested and verified:
**the DJ cannot read these.** Not through their profile, not through their
dashboard. Admin only.

---

## Suspending Someone

One click. It cascades:

| What | Effect |
|---|---|
| Login | Refused immediately |
| Stream keys | Revoked — broadcast cut at next publish |
| Metadata token | Revoked — ticker stops updating |
| Now-playing entry | Deleted from the homepage |

If someone has to go mid-set, this is the button.

**Reactivating issues a new stream key and leaves the old ones dead.** If you
suspended them because a key leaked, silently re-enabling that key would reopen
the hole.

**You cannot suspend yourself**, and you cannot suspend the last active admin.
Both are blocked server-side so you can't lock yourself out of your own station.

---

## Security Notes

Three findings from testing this build, all now fixed:

**1. Open registration** — described above. Closed.

**2. Suspended accounts could still log in.** The login endpoint checked the
password but never checked `is_active`. Someone you had just banned could still
sign in. Their stream key was dead so they couldn't broadcast, but they could see
their dashboard. Now blocked with a 403.

The check runs *after* password verification on purpose. Rejecting on `is_active`
first would let someone distinguish "suspended account" from "wrong password,"
turning the login form into an account-status oracle.

**3. Header parsing bug** — five endpoints read the `Authorization` header as a
query parameter, so the entire DJ dashboard returned 401. Fixed, with a test
asserting query-string auth is *rejected* (tokens in URLs get written to nginx
access logs in plaintext).

### Admin Rights Are Read Live

Admin status is read from the database on every request, not baked into the login
token. If it were in the token, removing someone's admin rights wouldn't take
effect until their token expired — up to 24 hours of continued admin access after
you thought you'd revoked it. Reading live means revocation is instant.

### Three Separate Credentials

| Credential | Purpose | If leaked |
|---|---|---|
| **Password** | Dashboard login | Account access — reset it |
| **Stream key** | RTMP broadcast | Someone broadcasts as that DJ |
| **Metadata token** | Track info updates | Someone writes bad song titles |

Each is revocable on its own. This is why the metadata token exists — so the
stream key never has to be pasted into a third-party agent config.

---

## Autoplay

Runs when **no DJ is live and nothing is scheduled**. A live DJ always wins.

### Music Sources

| Source | Tier | Notes |
|---|---|---|
| `jamendo` | Safe | CC catalogue, free open API — your best bet |
| `fma` | Safe | Free Music Archive, CC-licensed |
| `ccmixter` | Safe | CC remix catalogue |
| `local` | Safe | Files you own |
| `direct` | Safe | Artist gave permission — keep the email |
| `youtube` | **Grey** | Fallback only, not licensed for broadcast |

The selector prefers licensed sources and only touches YouTube when nothing else
matches. The admin panel shows a live licensed-vs-unlicensed count so you can see
your exposure at a glance.

**On SoundCloud:** I suggested it earlier. Their public API has been effectively
closed to new application registrations for years — don't plan around getting a
key. Jamendo is the practical open alternative.

**Fill in the license note.** Every track has one. If you ever get a DMCA notice,
"we believed it was licensed" is a far stronger position with a written per-track
record than without one. It takes five seconds per track.

### Listener Requests

The request box appears on the homepage only when autoplay is active — showing it
during a live set would imply listeners can influence what the DJ plays.

Guards, all tested:

- 5 requests per IP per hour
- Queue capped at 100 pending
- Same track can't be double-queued
- Nicknames are 32 chars, printable only, escaped on render
- Requester IPs are logged for you but **never exposed publicly**
- You can remove any request from the admin panel

---

## Your Test Run

The sequence you described, in order:

**1. Queue a song, have someone else queue one, hear them**

```bash
# add a few tracks first
# /admin.html -> Autoplay Library -> Add Track
```

Then on the homepage, the request box appears (no DJ live). Search, click Request.
Have a friend do the same from their own connection. Both appear in the queue with
names attached, in order. Hit **Play Next Track** in the admin panel to advance.

Requests play before library fallback — verified by test.

**2. Generate a stream key and log in**

```bash
# /admin.html -> Add a DJ
# copy the username, password and stream key
# log out, log back in as that DJ
# you will be asked to set a new password
```

The stream key is on their dashboard, alongside the metadata token, with a warning
not to confuse the two.

---

## Configuration

Add to `.env`:

```
# Keep this off. Accounts are created by admins after vetting.
ALLOW_OPEN_REGISTRATION=false
```

The endpoint stays in the codebase so a future public-signup mode doesn't need a
code change, but it refuses everything unless this is explicitly `true`.

---

## Endpoint Reference

**Admin only** (403 for everyone else, verified by test):

```
POST   /api/admin/djs                          create account
GET    /api/admin/djs                          list roster
POST   /api/admin/djs/{id}/suspend             suspend
POST   /api/admin/djs/{id}/reactivate          reactivate + new key
POST   /api/admin/djs/{id}/reset-password      reset password
POST   /api/admin/djs/{id}/revoke-keys         revoke keys
PUT    /api/admin/djs/{id}/notes               update notes
GET    /api/admin/audit-log                    activity log
POST   /api/admin/autoplay/library             add track
GET    /api/admin/autoplay/library             list library
DELETE /api/admin/autoplay/library/{id}        delete track
POST   /api/admin/autoplay/library/{id}/toggle enable/disable
DELETE /api/admin/autoplay/queue/{id}          remove request
POST   /api/autoplay/next                      advance playback
```

**Authenticated DJ:**

```
GET    /api/dj/me                              own profile (no admin notes)
POST   /api/dj/change-password                 change own password
```

**Public:**

```
GET    /api/autoplay/search                    search library
POST   /api/autoplay/request                   request a track
GET    /api/autoplay/queue                     view queue
GET    /api/autoplay/status                    autoplay state
```

---

## Test Coverage

Automated tests for this build:

- 33 admin and auth tests
- 34 autoplay and request tests
- 32 now-playing tests
- 13 endpoint integration tests

Covering: registration closure, privilege boundaries, notes isolation, suspension
cascade, password lifecycle, admin self-protection, source licensing preference,
SQL injection attempts in search, XSS payloads in nicknames, rate limits, and IP
non-disclosure.

---

## Still Open

- [ ] Verify DJ software now-playing paths (see DJ-SOFTWARE-STANDARDS.md)
- [ ] Decide on stream key reuse policy for the DJ agreement
- [ ] Seed the autoplay library with enough tracks to cover a quiet night
- [ ] Wire `/api/autoplay/next` to actual audio playback — currently it selects
      the track and reports it; the playback layer is not built yet
