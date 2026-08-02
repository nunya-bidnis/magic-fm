# Magic.fm - 24/7 Online Radio Station

A secure, lightweight online radio streaming platform for DJs to broadcast 24/7 with a public homepage featuring live stream player, schedule, and Discord-integrated chat.

## Features

- **DJ Authentication System** - Secure login with stream key generation
- **RTMP Stream Input** - DJs stream via standard RTMP protocol
- **DASH Stream Output** - Modern, adaptive bitrate streaming to listeners
- **Live Player** - Embedded dash.js player on homepage
- **Schedule Display** - Show upcoming DJ streams and slots
- **Discord Chat Integration** - Live chat via webhook integration with Discord
- **Security-First** - Built to resist common attacks (XSS, CSRF, SQL injection, brute force)
- **Minimal Footprint** - Python/FastAPI + SQLite for low resource usage

## Project Structure

```
magic-fm/
├── main.py                 # FastAPI application entry point
├── app/
│   ├── database.py         # SQLite models and initialization
│   ├── models.py           # Pydantic data models
│   ├── security.py         # Authentication, hashing, JWT
│   ├── middleware.py       # CORS, rate limiting, CSP headers
│   ├── routes/             # API endpoints
│   │   ├── auth.py         # DJ login and registration
│   │   ├── streaming.py    # Stream validation and status
│   │   ├── schedule.py     # Schedule management
│   │   └── discord.py      # Discord webhook handling
│   └── utils.py            # Helper functions
├── frontend/               # HTML/CSS/JS for public site
│   ├── index.html          # Homepage with player
│   ├── dj-login.html       # DJ login page
│   ├── dj-dashboard.html   # DJ portal
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── player.js       # dash.js player initialization
│       ├── chat.js         # Discord chat embed
│       └── auth.js         # Authentication handling
├── config/                 # Deployment configs
│   ├── nginx.conf          # Reverse proxy setup
│   └── magic-fm.service    # Systemd service file
├── docs/
│   └── SECURITY.md         # Security hardening guide
├── requirements.txt        # Python dependencies
└── .env.example            # Environment configuration template
```

## Quick Start

### Prerequisites
- Python 3.9+
- SQLite3
- Nginx (for reverse proxy)
- RTMP server (nginx-rtmp module)
- Domain name pointed to your VPS

### Installation

1. **Clone and setup:**
```bash
git clone <repo> magic-fm
cd magic-fm
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your settings (domain, Discord webhook, etc.)
```

3. **Initialize database:**
```bash
python -c "from app.database import init_db; init_db()"
```

4. **Run FastAPI:**
```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

5. **Setup Nginx reverse proxy** (see `config/nginx.conf`)

6. **Configure RTMP server** for DJ stream input

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new DJ
- `POST /api/auth/login` - DJ login
- `POST /api/auth/logout` - DJ logout
- `POST /api/auth/regenerate-key` - Generate new stream key

### Streaming
- `POST /api/stream/validate` - Validate stream key (RTMP server calls this)
- `GET /api/stream/status` - Get current stream status
- `GET /api/stream/dash` - Serve DASH manifest

### Schedule
- `GET /api/schedule` - Get upcoming schedule
- `POST /api/schedule` - Add show (authenticated DJ)
- `DELETE /api/schedule/<id>` - Remove show

### Discord
- `POST /api/discord/webhook` - Receive chat messages from Discord

## Security Highlights

- **Input Validation** - Pydantic validates all request data
- **SQL Injection Protection** - Parameterized SQLite queries
- **XSS Protection** - HTML escaping, no dynamic eval()
- **CSRF Tokens** - All form submissions verified
- **Rate Limiting** - Brute force protection on login
- **HTTPOnly Cookies** - Session tokens immune to XSS
- **CSP Headers** - Content Security Policy prevents inline scripts
- **HTTPS Only** - Enforce TLS in production
- **Secure Passwords** - bcrypt hashing, salted

See `docs/SECURITY.md` for detailed hardening guide.

## Streaming Setup

### RTMP Input (DJ Broadcasting)
DJs use OBS/Streamlabs with:
- Server: `rtmp://magic.fm/live`
- Stream Key: `<generated-key>`

### DASH Output (Public Playback)
Homepage player requests:
- `https://magic.fm/api/stream/dash/manifest.mpd`

## Deployment

See `config/nginx.conf` and `config/magic-fm.service` for production setup on your VPS.

### Steps:
1. Copy service file to `/etc/systemd/system/`
2. Update Nginx with reverse proxy config
3. Obtain SSL cert (Let's Encrypt)
4. Start service: `systemctl start magic-fm`

## Environment Variables

```
DOMAIN=magic.fm
DISCORD_WEBHOOK_URL=https://discordapp.com/api/webhooks/...
JWT_SECRET=<generate-strong-random-string>
DATABASE_URL=sqlite:///./magic.db
RTMP_SERVER_IP=127.0.0.1
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
```

## Development

Run tests:
```bash
pytest tests/
```

Format code:
```bash
black app/
```

## License

MIT

## Support

For issues or questions, see `docs/SECURITY.md` before deployment.
