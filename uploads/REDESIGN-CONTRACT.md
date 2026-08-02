# Magic.fm - Redesign Contract

Hand this to whatever you use to restyle the site.

**The short version:** restyle anything you like, but keep the element IDs and don't
add external fonts or scripts. Break either rule and the page goes quiet — no errors,
just a site that looks great and does nothing.

---

## Rule 1 — Keep the IDs

All behaviour is wired by `getElementById`. Change the markup, the layout, the
classes, the colours, the copy — all fine. Delete or rename an ID and that feature
stops working silently.

### index.html (homepage)

| ID | What breaks without it |
|---|---|
| `np-idle` | Ticker idle state |
| `np-content` | Ticker container |
| `np-track` | Track title |
| `np-artist` | Artist name |
| `np-dj` | Current DJ name |
| `np-art` | Album art (`<img>`) |
| `video-player` | **The player itself** (`<video>`) |
| `stream-status` | Live/offline badge |
| `now-playing` | Player status line |
| `stream-details` | Bitrate/viewer line |
| `play-btn` | Play/pause |
| `mute-btn` | Mute |
| `volume` | Volume (`<input type="range">`) |
| `schedule-list` | Upcoming shows |
| `current-show-name` / `current-show-time` / `current-show-desc` | Now-playing show card |
| `next-show-name` / `next-show-time` | Up-next card |
| `chat-messages` | Discord chat |
| `request-section` | Request box wrapper — **needs `style="display:none"` initially** |
| `req-search` | Request search box |
| `req-name` | Requester nickname |
| `search-results` | Search results container |
| `public-queue` | Queue list |
| `request-msg` / `request-err` | Request feedback |

### dj-login.html

`login-form`, `username`, `password`, `error-message`, `success-message`

The register form is intentionally hidden — accounts are admin-created. Don't
restore a public sign-up UI.

### dj-dashboard.html

`dj-name`, `logout-btn`, `profile-username`, `profile-email`, `profile-created`,
`stream-status-text`, `stream-status-viewers`, `stream-keys-list`,
`generate-key-btn`, `metadata-token-display`, `copy-metadata-btn`,
`rotate-metadata-btn`, `shows-list`, `create-show-btn`, `create-show-modal`,
`close-modal-btn`, `create-show-form`, `show-name`, `show-desc`, `show-start`,
`show-end`, `show-recurring`, `show-error`

### admin.html

`access-denied`, `admin-content`, `create-dj-form`, `new-username`, `new-email`,
`new-password`, `new-display`, `new-notes`, `create-error`, `create-success`,
`new-credentials`, `cred-details`, `dj-list`, `add-track-form`, `track-title`,
`track-artist`, `track-source`, `track-url`, `track-license`, `track-error`,
`stat-total`, `stat-licensed`, `stat-unlicensed`, `stat-queue`, `advance-btn`,
`refresh-library-btn`, `library-list`, `queue-list`, `audit-list`, `logout-btn`

### dj-nowplaying.html

`manual-form`, `track`, `artist`, `clear-btn`, `current-display`,
`error-message`, `success-message`, `logout-btn`

---

## Rule 2 — Four class names carry behaviour

JS toggles these. Style them however you want, but keep the names:

| Class | Meaning |
|---|---|
| `show` | Reveals error/success messages. Base state must be hidden. |
| `online` / `offline` | Stream status badge state |
| `np-flash` | Brief highlight on track change |
| `js-request-btn` | Request buttons — **do not rename**, listeners bind to it |

Pattern for messages — keep this shape:

```css
.error-message, .success-message { display: none; }
.error-message.show, .success-message.show { display: block; }
```

---

## Rule 3 — The CSP will block most design shortcuts

The server sends a strict Content-Security-Policy. **This is the one that wastes
the most time**, because blocked resources fail quietly in a way that looks like a
CSS bug.

Currently allowed:

```
script-src  'self' https://cdn.dashjs.org
style-src   'self' 'unsafe-inline'
font-src    'self'
img-src     'self' data: https:
frame-src   'self' https://discordapp.com
```

**What this means in practice:**

| Want to use | Works? |
|---|---|
| Google Fonts / Adobe Fonts | **No** — `font-src 'self'` |
| Self-hosted `.woff2` | Yes |
| Tailwind / Bootstrap via CDN | **No** — `script-src` and `style-src` |
| Tailwind compiled to a local CSS file | Yes |
| Inline `<style>` blocks | Yes |
| Inline `style="..."` attributes | Yes |
| `<script>` in the page | Yes |
| Any other CDN JavaScript | **No** |
| Remote images over https | Yes |
| SVG, gradients, CSS animations | Yes |

**Web fonts:** download the files, drop them in `frontend/fonts/`, and `@font-face`
them locally. Don't relax `font-src` to allow Google — that reopens a
data-exfiltration path the CSP is there to close.

**If something must be added to the CSP,** it lives in two places and both need
updating or production and local will disagree:
- `middleware.py` → `SecurityHeadersMiddleware`
- `nginx.conf` → the `add_header Content-Security-Policy` line

---

## Rule 4 — Don't introduce innerHTML with live data

Track titles, artist names, chat messages and requester nicknames are all
attacker-controlled. Anyone can submit a request under any name.

Current code renders them with `textContent` or escapes them first. If a redesign
swaps in a template that drops raw values into `innerHTML`, that's a stored XSS on
your public homepage.

Safe:
```js
el.textContent = data.track;
```

Not safe:
```js
el.innerHTML = data.track;
```

---

## What's genuinely free to change

- All colours, spacing, typography, layout, borders, shadows
- Every CSS class except the four above
- Element types — a `<div>` can become a `<section>`, keep the ID
- Element nesting and order
- All copy and labels
- Adding new elements, sections, icons, illustrations
- `style.css` wholesale — nothing depends on its internals

---

## Design notes, take or leave

- **Ticker is the emotional centre.** It's the thing that says a human is on the
  other end. Worth more visual weight than it currently has.
- **Requester names on the queue** are the "intimacy" you described — someone
  seeing their name on the station's homepage. Currently rendered as small grey
  text. That's underselling it.
- **Idle state matters.** A 24/7 station is often between DJs. "No track
  information available" is a dead end; a good idle state keeps people around.
- **Dark theme is the right instinct** for a radio station and worth keeping.

---

## After the redesign

```bash
# 1. Confirm nothing lost its ID
grep -o 'id="[^"]*"' index.html | sort -u

# 2. Serve locally and watch the browser console
python3 -m uvicorn main:app --reload

# 3. Check for CSP violations - they appear in the console as
#    "Refused to load ... because it violates the Content Security Policy"
```

If a feature goes quiet after restyling, it's almost always a renamed ID or a CSP
block. Console will tell you which.
