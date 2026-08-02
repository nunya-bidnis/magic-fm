# Magic.fm Deployment Guide

Step-by-step guide to deploy Magic.fm to your VPS.

## Prerequisites

- VPS running Ubuntu 22.04 LTS (recommended)
- Root/sudo access
- Domain name pointing to VPS IP
- Python 3.9+ installed
- Nginx installed
- Basic SSH knowledge

## Step 1: Initial Server Setup

### 1.1 Update system packages

```bash
sudo apt update
sudo apt upgrade -y
sudo apt autoremove -y
```

### 1.2 Install dependencies

```bash
sudo apt install -y python3-pip python3-venv nginx git curl wget
```

### 1.3 Configure firewall

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw enable
```

### 1.4 Create application user

```bash
sudo useradd -r -s /bin/bash -d /var/www/magic-fm www-data
```

## Step 2: Clone and Setup Magic.fm

### 2.1 Clone repository

```bash
cd /var/www
sudo git clone https://github.com/yourusername/magic-fm.git magic-fm
sudo chown -R www-data:www-data /var/www/magic-fm
```

### 2.2 Create Python virtual environment

```bash
cd /var/www/magic-fm
sudo -u www-data python3 -m venv venv
sudo -u www-data venv/bin/pip install --upgrade pip
sudo -u www-data venv/bin/pip install -r requirements.txt
```

### 2.3 Setup environment configuration

```bash
sudo cp .env.example .env
sudo nano .env  # Edit with your settings
```

**Key environment variables to set:**
```
DOMAIN=your-domain.com
JWT_SECRET=<generate-with: openssl rand -hex 32>
DISCORD_WEBHOOK_URL=<your Discord webhook>
DATABASE_PATH=./magic.db
```

### 2.4 Initialize database

```bash
cd /var/www/magic-fm
sudo -u www-data venv/bin/python3 -c "from database import db; db.init_tables()"
```

Verify database created:
```bash
ls -la magic.db
```

## Step 3: Setup Nginx Reverse Proxy

### 3.1 Copy Nginx configuration

```bash
sudo cp /var/www/magic-fm/nginx.conf /etc/nginx/sites-available/magic-fm
sudo ln -s /etc/nginx/sites-available/magic-fm /etc/nginx/sites-enabled/
```

### 3.2 Update domain in Nginx config

```bash
sudo sed -i 's/magic.fm/your-domain.com/g' /etc/nginx/sites-available/magic-fm
```

### 3.3 Test Nginx configuration

```bash
sudo nginx -t
```

Should output:
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration will be successful
```

### 3.4 Enable Nginx

```bash
sudo systemctl enable nginx
sudo systemctl restart nginx
```

## Step 4: Setup SSL Certificate (Let's Encrypt)

### 4.1 Install Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 4.2 Create certificate

```bash
sudo certbot certonly --nginx -d your-domain.com -d www.your-domain.com
```

### 4.3 Setup auto-renewal

```bash
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

Verify renewal:
```bash
sudo certbot renew --dry-run
```

### 4.4 Update Nginx config with certificate paths

```bash
sudo nano /etc/nginx/sites-available/magic-fm
```

Update certificate paths:
```
ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
```

Reload Nginx:
```bash
sudo systemctl reload nginx
```

## Step 5: Setup Systemd Service

### 5.1 Copy service file

```bash
sudo cp /var/www/magic-fm/magic-fm.service /etc/systemd/system/
```

### 5.2 Enable and start service

```bash
sudo systemctl daemon-reload
sudo systemctl enable magic-fm
sudo systemctl start magic-fm
```

### 5.3 Verify service is running

```bash
sudo systemctl status magic-fm
```

Should show: `● magic-fm.service - Magic.fm - 24/7 Online Radio Station`

### 5.4 Check application logs

```bash
sudo journalctl -u magic-fm -f
```

## Step 6: Setup RTMP Streaming Server (Optional)

If using local RTMP server:

### 6.1 Build nginx-rtmp

```bash
sudo apt install -y build-essential libpcre3 libpcre3-dev zlib1g zlib1g-dev libssl-dev libgd-dev libgeoip-dev wget

cd /tmp
wget http://nginx.org/download/nginx-1.25.0.tar.gz
wget https://github.com/arut/nginx-rtmp-module/archive/master.zip

tar xzf nginx-1.25.0.tar.gz
unzip master.zip

cd nginx-1.25.0
./configure --add-module=../nginx-rtmp-module-master \
    --with-http_ssl_module --with-http_v2_module
make
sudo make install
```

### 6.2 Configure RTMP in nginx.conf

Add to `/usr/local/nginx/conf/nginx.conf`:

```nginx
rtmp {
    server {
        listen 1935;
        chunk_size 4096;

        application live {
            live on;
            record off;
            
            on_publish http://127.0.0.1:8000/api/stream/validate;
            on_publish_done http://127.0.0.1:8000/api/stream/end;
        }
    }
}
```

### 6.3 Reload RTMP nginx

```bash
sudo /usr/local/nginx/sbin/nginx -s reload
```

## Step 7: Setup Monitoring & Logging

### 7.1 Check application is responding

```bash
curl -I https://your-domain.com/health
```

Should return: `HTTP/1.1 200 OK`

### 7.2 Setup log rotation

```bash
sudo cat > /etc/logrotate.d/magic-fm << EOF
/var/log/nginx/magic-fm.access.log
/var/log/nginx/magic-fm.error.log
{
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 640 www-data www-data
    sharedscripts
    postrotate
        if [ -f /var/run/nginx.pid ]; then
            kill -USR1 `cat /var/run/nginx.pid`
        fi
    endscript
}
EOF
```

### 7.3 Monitor logs in real-time

```bash
# Application logs
sudo journalctl -u magic-fm -f

# Web server access
sudo tail -f /var/log/nginx/magic-fm.access.log

# Web server errors
sudo tail -f /var/log/nginx/magic-fm.error.log
```

## Step 8: Backup Strategy

### 8.1 Setup daily backups

```bash
sudo mkdir -p /var/backups/magic-fm
sudo chown www-data:www-data /var/backups/magic-fm

# Create backup script
sudo cat > /usr/local/bin/backup-magic-fm << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/magic-fm"
DB_PATH="/var/www/magic-fm/magic.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Backup database
cp $DB_PATH $BACKUP_DIR/magic.db.$TIMESTAMP
gzip $BACKUP_DIR/magic.db.$TIMESTAMP

# Keep only last 7 days
find $BACKUP_DIR -name "*.gz" -mtime +7 -delete

echo "Backup completed: $TIMESTAMP"
EOF

sudo chmod +x /usr/local/bin/backup-magic-fm
```

### 8.2 Schedule daily backups

```bash
# Add to crontab
sudo crontab -e

# Add this line:
0 2 * * * /usr/local/bin/backup-magic-fm >> /var/log/magic-fm-backup.log 2>&1
```

## Step 9: Verification & Testing

### 9.1 Test homepage access

```bash
curl https://your-domain.com/
```

### 9.2 Test API endpoints

```bash
# Health check
curl https://your-domain.com/health

# Get schedule
curl https://your-domain.com/api/schedule
```

### 9.3 Test DJ registration

```bash
curl -X POST https://your-domain.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testdj",
    "email": "test@example.com",
    "password": "TestPassword123",
    "display_name": "Test DJ"
  }'
```

### 9.4 Test DJ login

```bash
curl -X POST https://your-domain.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testdj",
    "password": "TestPassword123"
  }'
```

Should return access token.

## Step 10: Configure Discord Webhook (Optional)

### 10.1 Create Discord webhook

1. Go to your Discord server settings
2. Navigate to Integrations → Webhooks
3. Click "New Webhook"
4. Set name to "Magic.fm Chat"
5. Copy the webhook URL

### 10.2 Update .env

```bash
sudo nano /var/www/magic-fm/.env
```

Set:
```
DISCORD_WEBHOOK_URL=https://discordapp.com/api/webhooks/YOUR_ID/YOUR_TOKEN
```

Restart service:
```bash
sudo systemctl restart magic-fm
```

## Troubleshooting

### Service won't start

```bash
# Check logs
sudo journalctl -u magic-fm -n 50

# Check Python syntax
cd /var/www/magic-fm
venv/bin/python3 -m py_compile main.py
```

### Nginx error

```bash
# Test config
sudo nginx -t

# View error logs
sudo tail -f /var/log/nginx/magic-fm.error.log
```

### Database locked

```bash
# Delete old database and reinitialize
sudo rm /var/www/magic-fm/magic.db
cd /var/www/magic-fm
sudo -u www-data venv/bin/python3 -c "from database import db; db.init_tables()"
sudo systemctl restart magic-fm
```

### High CPU/Memory usage

Check for stuck processes:
```bash
ps aux | grep python
ps aux | grep nginx
```

Restart if needed:
```bash
sudo systemctl restart magic-fm
sudo systemctl restart nginx
```

## Post-Deployment Checklist

- [ ] HTTPS working (check https://magic.fm)
- [ ] Homepage loads
- [ ] DJ login/register works
- [ ] Stream keys generate
- [ ] Schedule displays
- [ ] Chat widget functional
- [ ] Logs rotating properly
- [ ] Backups running
- [ ] Firewall configured
- [ ] SSL auto-renewal scheduled
- [ ] Monitoring in place

## Next Steps

1. **Configure RTMP streaming** - Setup OBS to point to your server
2. **Test streaming** - Start a stream and verify it appears on homepage
3. **Invite DJs** - Share /dj-login.html with your broadcasters
4. **Monitor performance** - Watch logs and system metrics
5. **Plan maintenance** - Schedule updates and backups

## Support

- Check logs: `sudo journalctl -u magic-fm -f`
- Review security: See SECURITY.md
- Update dependencies: `pip install --upgrade -r requirements.txt`

---

**Deployment completed!** 🎉

Your Magic.fm instance is now running at `https://your-domain.com`
