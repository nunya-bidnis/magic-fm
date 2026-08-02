# Magic.fm — Project Brief for Claude Code

## What this is
A 24/7 online radio station platform. DJs are hand-vetted by the owner (no public
signup), log in to get stream keys, and broadcast via RTMP. The site shows now-playing
info and a schedule, with an autoplay library filling dead air.

## Current state (verified 2026-08-01)
The repo at /var/www/magic-fm contains ONLY the front-end plus one backend module:

- index.html, admin.html, dj-login.html, dj-dashboard.html, dj-nowplaying.html
- static/ (css, js, img), uploads/
- admin.py — a working FastAPI APIRouter, but it imports modules that DO NOT EXIST
- ADMIN-ACCESS.md — security design doc (read it before writing nginx config)
- create_dummy_dj.py

**The backend was never built.** These files are missing and must be created:
- main.py (FastAPI app entry point, mounts routers + static files)
- database.py (must expose `db` with `init_tables()`; SQLite at ./magic.db)
- security.py (must expose PasswordManager, AuditLogger, validate_password_strength)
- middleware.py (must expose get_client_ip)
- nowplaying.py (must expose require_dj dependency + nowplaying/metadata routes)
- requirements.txt
- .env.example
- nginx.conf (site config)
- magic-fm.service (systemd unit, uvicorn on 127.0.0.1:8000, user www-data)

Read admin.py first — it defines the contracts (imports, function signatures,
Depends() usage) the missing modules must satisfy. Do not modify admin.py to fit
your code; write the modules to fit admin.py.

## API endpoints the front-end already calls (grep'd from the HTML)
Auth:
- POST /api/auth/login
- POST /api/auth/register  (must be gated by ALLOW_OPEN_REGISTRATION, default OFF)
- GET/POST /api/auth/stream-key
DJ:
- GET /api/dj/me
- GET /api/dj/dashboard
- GET /api/dj/metadata-token
- GET/POST /api/dj/nowplaying
- POST /api/dj/nowplaying/manual
Public:
- GET /api/nowplaying
- GET /api/schedule
Autoplay:
- GET /api/autoplay/next
- GET /api/autoplay/queue
- GET /api/autoplay/status
Admin (loopback-only):
- GET /api/admin/djs
- GET /api/admin/audit-log?limit=N
- GET /api/admin/autoplay/library

Open each HTML file to confirm exact request/response shapes the JS expects
(field names, token storage, headers) before writing handlers.

## Security requirements (non-negotiable, from ADMIN-ACCESS.md + admin.py)
1. No public registration. ALLOW_OPEN_REGISTRATION env var, default false.
2. /admin.html and /api/admin/* must be loopback-only at BOTH layers:
   - nginx: allow 127.0.0.1/::1, deny all (location block BEFORE the general one)
   - app: require_admin() already checks client IP against {127.0.0.1, ::1}
3. get_client_ip() must NOT blindly trust X-Forwarded-For — only honor it from
   the local nginx proxy, else the loopback check is spoofable.
4. Passwords: bcrypt or argon2. JWT secret from env (.env), never hardcoded.
5. Stream keys: random, revocable, stored hashed or at minimum regenerable.
6. AuditLogger writes admin/auth events to the DB (admin.html reads them).

## Stack decisions already made
- FastAPI + uvicorn, Python 3.12 venv at /var/www/magic-fm/venv
- SQLite at ./magic.db (DATABASE_PATH env var)
- nginx reverse proxy on 80/443 → 127.0.0.1:8000; serves /static directly
- systemd service `magic-fm` running as www-data
- Domain: ask the owner what domain to use before writing certbot/nginx
  server_name; may still be IP-only.

## Environment notes
- Ubuntu 24.04 (noble). nginx installed from Ubuntu repos (1.24) — the
  nginx.org repo was removed earlier because it was misconfigured for
  "resolute" and broke apt. Do not re-add it.
- Repo: https://github.com/nunya-bidnis/magic-fm — commit and push work in
  logical chunks so nothing lives only on this VPS again.
- deadsnakes PPA is present; system python3 is 3.12.

## Build order
1. Read admin.py, all HTML files, and ADMIN-ACCESS.md fully.
2. database.py + security.py + middleware.py (foundations admin.py needs)
3. Auth routes + nowplaying.py (require_dj) — get login working end to end
4. main.py wiring all routers + static file serving
5. DJ dashboard + schedule + autoplay endpoints
6. requirements.txt, .env.example, generate real .env (openssl rand -hex 32
   for JWT_SECRET)
7. Init DB, create the first admin account (adapt create_dummy_dj.py)
8. nginx.conf + systemd unit; enable + start; verify with curl
9. Test every endpoint the front-end calls; fix mismatches
10. Commit and push everything to GitHub

## Definition of done
- `systemctl status magic-fm` active; site loads via nginx
- DJ can log in on /dj-login.html and see the dashboard
- /admin.html returns 403 publicly, works through SSH tunnel
  (ssh -L 8080:127.0.0.1:80 user@vps → http://localhost:8080/admin.html)
- All work pushed to the GitHub repo
