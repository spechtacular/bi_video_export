# NGINX Configuration

This directory contains version-controlled nginx configuration files
for the BI Video Export portal and related services.

---

## 📁 Structure

nginx/
├── blueiris.conf
├── django.conf
├── zt_dashboard.conf
└── ssl/


These files are symlinked into:

opt/homebrew/etc/nginx/servers/


---

## 🚀 Installation

Run the deploy script:

./deploy/install_nginx.sh


This will:

- Symlink config files into nginx
- Generate a self-signed SSL certificate (if missing)
- Create `.htpasswd` (if missing)
- Restart nginx

---

## 🔐 SSL Certificates

Self-signed certificates are generated into:



/opt/homebrew/etc/nginx/ssl/

For production, replace with real certificates (e.g. Let's Encrypt).

---

## 🔑 Basic Auth

Credentials are stored in:

/opt/homebrew/etc/nginx/.htpasswd


To add a user:
htpasswd /opt/homebrew/etc/nginx/.htpasswd username


---

## 🧪 Testing Config

Before restarting nginx manually:



nginx -t
---

## 🔄 Restarting nginx

brew services restart nginx


Or run in foreground:

/opt/homebrew/opt/nginx/bin/nginx -g 'daemon off;'


---

## 🏗 Architecture
- nginx serves static files (videos, images, documents)
- nginx reverse proxies:
  - ZeroTier dashboard
  - Django application
- SSL terminates at nginx
- Basic auth protects portal access

---

## ⚠️ Do Not Commit

Never commit:

- Real SSL certificates
- Private keys
- `.htpasswd`
- Production IP addresses
- Secrets
Ensure `.gitignore` includes:

nginx/ssl/.key
nginx/ssl/.crt
nginx/.htpasswd


---

## 💡 Philosophy

Infrastructure as Code.
All nginx configuration is version controlled
so the full stack can be rebuilt reproducibly.

---

## Long Path Taken

This stack evolved through:

- Blue Iris API integration
- Export queue debugging
- Reverse proxy tuning
- ZeroTier network observability
- Django integration
- macOS + Homebrew optimization

The result is a unified development and operations portal.

---

