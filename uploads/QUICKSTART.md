# Magic.fm Quick Start Guide

## What You Got

A complete, production-ready online radio station platform with:

✅ **Backend** (Python/FastAPI)
- Secure DJ authentication + password hashing
- Stream key generation & validation
- Schedule management API
- Discord chat webhook integration
- Database (SQLite)

✅ **Frontend** (HTML/CSS/JavaScript)
- Modern, responsive homepage
- DASH player with dash.js
- Live chat widget (Discord integrated)
- DJ login & dashboard
- Show schedule display

✅ **Security** (Enterprise-grade)
- SQL injection prevention (parameterized queries)
- XSS protection (HTML escaping + CSP headers)
- CSRF token protection
- Rate limiting (brute force resistant)
- bcrypt password hashing
- JWT authentication
- HTTPS/TLS enforced
- Audit logging

✅ **Deployment** (Ready for VPS)
- Nginx reverse proxy config
- Systemd service file
- Let's Encrypt SSL setup
- Log rotation
- Backup strategy

---

## File Structure

```
magic-fm/
├── main.py                  # FastAPI application
├── database.py              # SQLite with parameterized queries
├── security.py              # Authentication, hashing, JWT, stream keys
├── middleware.py            # Rate limiting, CSP, CORS
├── models.py                # Pydantic validation models
├── requirements.txt         # Python dependencies
├── .env.example              # Environment configuration template
├── .gitignore               # Git ignore rules
├── frontend/
│   ├── index.html           # Homepage with player
│   ├── dj-login.html        # DJ login/register
│   ├── dj-dashboard.html    # DJ portal
│   ├── css/
│   │   └── style.css        # Responsive styling
│   └── js/
│       ├── player.js        # DASH player + schedule
│       └── chat.js          # Discord chat widget
├── config/
│   ├── nginx.conf           # Reverse proxy + security headers
│   └── magic-fm.service     # Systemd service
├── docs/
│   ├── SECURITY.md          # Security hardening guide
│   └── DEPLOYMENT.md        # Step-by-step deployment
├── README.md                # Overview
└── QUICKSTART.md            # This file
```

---

## Local Development (5 minutes)

### 1. Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env
cp .env.example .env
# Edit .env if needed
```

### 2. Initialize Database

```bash
python3 -c "from database import db; db.init_tables()"
```

### 3. Run Server

```bash
python3 -m uvicorn main:app --reload
```

Server runs on `http://localhost:8000`

### 4. Test It

- Homepage: http://localhost:8000/
- DJ Login: http://localhost:8000/dj-login.html
- Health: http://localhost:8000/health

### 5. Create a Test DJ Account

1. Go to http://localhost:8000/dj-login.html
2. Click "Register here"
3. Create account (username, email, password)
4. You'll be logged in to dashboard
5. Generate stream key
6. Create a show

---

## Deployment to VPS (30 minutes)

### Quick Version

```bash
# 1. SSH to VPS
ssh root@your-vps-ip

# 2. Run deployment script (see DEPLOYMENT.md for detailed steps)
cd /var/www
git clone <your-repo> magic-fm
cd magic-fm

# 3. Install dependencies
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 4. Setup .env
cp .env.example .env
nano .env  # Add your settings

# 5. Initialize database
venv/bin/python3 -c "from database import db; db.init_tables()"

# 6. Setup Nginx
sudo cp nginx.conf /etc/nginx/sites-available/magic-fm
sudo ln -s /etc/nginx/sites-available/magic-fm /etc/nginx/sites-enabled/
sudo systemctl restart nginx

# 7. Setup SSL
sudo certbot certonly --nginx -d your-domain.com

# 8. Setup systemd service
sudo cp magic-fm.service /etc/systemd/system/
sudo systemctl enable magic-fm
sudo systemctl start magic-fm
```

**Full detailed guide**: See `DEPLOYMENT.md`

---

## Configuration

### Environment Variables (.env)

```
DOMAIN=magic.fm                           # Your domain
JWT_SECRET=your-secret-key                # Generate: openssl rand -hex 32
DISCORD_WEBHOOK_URL=https://discord...    # Discord webhook for chat
DATABASE_PATH=./magic.db                  # Database location
RATE_LIMIT_REQUESTS=100                   # API rate limit
RATE_LIMIT_WINDOW=60                      # Rate limit time window (seconds)
```

### User Roles

Currently, there's one role: **DJ**

- Register at `/dj-login.html`
- Get stream key for broadcasting
- Create show schedule
- View stream status

**Future expansion ideas:**
- Admin role (moderate chat, manage users)
- Listener accounts (favorites, preferences)
- Moderator role

---

## API Endpoints

### Public

```
GET  /                              # Homepage
GET  /health                        # Health check
GET  /api/schedule                  # Get upcoming schedule
GET  /api/stream/status             # Current stream status
GET  /api/chat/messages             # Get chat messages
POST /api/discord/webhook           # Discord message webhook
```

### Authentication

```
POST /api/auth/register             # Create DJ account
POST /api/auth/login                # DJ login
POST /api/auth/logout               # DJ logout
GET  /api/csrf-token                # Get CSRF token
```

### DJ-Only (requires Bearer token)

```
POST /api/auth/stream-key           # Generate stream key
GET  /api/auth/stream-keys          # List stream keys
GET  /api/dj/dashboard              # DJ dashboard data
POST /api/schedule                  # Create show
GET  /api/schedule                  # Get all shows
```

### Streaming

```
POST /api/stream/validate           # Validate RTMP key (from RTMP server)
GET  /api/stream/dash/manifest.mpd  # DASH manifest
```

---

## OBS/Streamlabs Setup

Once you have a stream key:

### OBS
1. Settings → Stream
2. Service: Custom...
3. Server: `rtmp://your-domain.com/live`
4. Stream Key: (paste from dashboard)
5. Start streaming!

### Streamlabs
1. Settings → Stream
2. Platform: Custom RTMP
3. Ingest Server: `rtmp://your-domain.com/live`
4. Stream Key: (paste from dashboard)
5. Go live!

---

## Security Checklist

Before deploying to production:

- [ ] Read `SECURITY.md` completely
- [ ] Generate strong JWT secret
- [ ] Setup HTTPS/SSL certificate
- [ ] Configure firewall rules
- [ ] Set file permissions correctly
- [ ] Enable rate limiting
- [ ] Review CSP headers
- [ ] Test CSRF protection
- [ ] Setup logging/monitoring
- [ ] Setup backups
- [ ] Enable audit logging
- [ ] Test incident response

---

## Troubleshooting

### Port already in use

```bash
# Find process using port 8000
lsof -i :8000
kill -9 <PID>
```

### Database locked

```bash
# Remove and reinitialize
rm magic.db
python3 -c "from database import db; db.init_tables()"
```

### Import errors

```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Verify dependencies
pip list
```

### CORS errors

Check `CORS_ORIGINS` in `.env` includes your domain.

### Nginx won't start

```bash
# Test config
sudo nginx -t

# Check logs
sudo tail -f /var/log/nginx/error.log
```

---

## Monitoring & Maintenance

### Daily

- Check logs: `sudo tail -f /var/log/nginx/magic-fm.access.log`
- Monitor CPU/memory: `top` or `htop`
- Verify backups ran

### Weekly

- Review audit log in database
- Check for failed login attempts
- Update dependencies if needed

### Monthly

- Security updates: `sudo apt update && sudo apt upgrade`
- Test backups can be restored
- Review performance metrics

---

## Next Steps

### Immediate

1. Test locally
2. Deploy to VPS
3. Configure Discord webhook
4. Test streaming with OBS
5. Add DJs

### Short-term

- Customize branding (logo, colors)
- Add DJ profiles
- Setup monitoring/alerts
- Configure CDN for player

### Long-term

- Add listener accounts
- Implement chat moderation
- Add recurring shows
- Analytics dashboard
- Mobile app

---

## Support & Issues

### Logs

```bash
# Application errors
sudo journalctl -u magic-fm -f

# Web server errors
sudo tail -f /var/log/nginx/magic-fm.error.log

# Database issues
# Check magic.db file permissions and size
ls -lh magic.db
```

### Documentation

- **Architecture**: README.md
- **Security**: docs/SECURITY.md
- **Deployment**: docs/DEPLOYMENT.md
- **API**: See main.py for all endpoints

### Common Issues

**Issue**: Can't login  
**Solution**: Check password requirements (8+ chars, 1 uppercase, 1 digit)

**Issue**: Stream key not working  
**Solution**: Verify key is active in DJ dashboard; regenerate if needed

**Issue**: Chat not showing  
**Solution**: Verify Discord webhook URL in .env; check webhook is active

---

## Performance Tips

### Database Optimization

```bash
# Vacuum database
sqlite3 magic.db "VACUUM;"

# Analyze for query optimization
sqlite3 magic.db "ANALYZE;"
```

### Nginx Caching

Static files are cached:
- CSS/JS: 1 day
- Images: 1 day
- HTML: No cache

### Enable Compression

Gzip is enabled in nginx config (reduces bandwidth ~70%)

---

## Version & License

- **Version**: 1.0
- **License**: MIT (do what you want, credit appreciated)
- **Last Updated**: January 2024

---

## You're Ready! 🚀

You now have a complete, secure, production-ready online radio station.

1. **Start local**: `python3 -m uvicorn main:app --reload`
2. **Deploy to VPS**: Follow DEPLOYMENT.md
3. **Secure it**: Review SECURITY.md
4. **Go live**: Point domain → test → invite DJs

Good luck, and happy streaming! 📻

For questions or issues, check the logs and documentation first.
