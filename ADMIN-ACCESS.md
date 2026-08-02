# Locking /admin.html behind your SSH access

Goal: nobody can even load `/admin.html` (or its API routes) unless they can
already SSH into the VPS. The existing DJ login/admin-flag check stays in
place underneath this — this adds a network-layer gate in front of it, it
doesn't replace it.

## 1. nginx change

In `nginx.conf`, add a location block that only allows the loopback address,
placed *before* your general `location /` block:

```nginx
location ~ ^/(admin\.html|api/admin/) {
    allow 127.0.0.1;
    allow ::1;
    deny all;

    # keep whatever you already proxy everything else to
    proxy_pass http://127.0.0.1:8000;   # <- your uvicorn/main:app upstream
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

Reload nginx (`nginx -s reload`). From the public internet, hitting
`https://yourdomain/admin.html` now gets a plain 403 — nginx drops it before
it ever reaches your app.

## 2. How you reach it

From your own machine, open a tunnel using the same key you already SSH into
the VPS with:

```bash
ssh -L 8080:127.0.0.1:80 -N youruser@your-vps-ip
```

(swap `80` for whatever port nginx listens on if not 80/443; use `-L
8080:127.0.0.1:443` and `https://localhost:8080` if you tunnel to the TLS
port instead).

Leave that running, then in a browser go to:

```
http://localhost:8080/admin.html
```

nginx sees the request as coming from `127.0.0.1` (the tunnel's local end),
so it passes. Close the SSH connection and the page becomes unreachable
again, from anywhere.

## 3. App-level backstop (already wired in)

`admin.py` in this project is now a ready-to-deploy replacement for yours:
`require_admin()` checks `get_client_ip(request)` against
`{"127.0.0.1", "::1"}` before it even checks `is_admin`, so every route on
`admin_router` is loopback-only regardless of nginx. Copy it over your
server's `admin.py` (it's otherwise identical to what you sent). nginx blocks
it first; this blocks it again if nginx is ever bypassed.

## 4. What still happens after that

Nothing on the page itself changes. `admin.html`'s existing `checkAdmin()`
still runs, still requires a valid DJ login token, still checks `is_admin`
server-side. You now need both: an SSH tunnel to reach the page at all, and
a valid admin login to see any content once it loads. No new frontend auth
UI needed — the tunnel is the "log in with your VPS key" step you asked for.

## Not included here

`main.py` / the app's auth routes weren't part of what I have — this only
touches nginx, which is enough for the gate you asked for. If you also want
the API JSON routes under `/api/admin/` reachable *only* through the tunnel
(recommended, and included in the block above via the regex), make sure
nothing else references those paths from a page that isn't itself
tunnel-gated.
