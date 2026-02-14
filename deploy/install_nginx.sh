#!/bin/bash
# not tested yet!
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NGINX_CONF_DIR="/opt/homebrew/etc/nginx/servers"
NGINX_SSL_DIR="/opt/homebrew/etc/nginx/ssl"
NGINX_HTPASSWD="/opt/homebrew/etc/nginx/.htpasswd"

echo "📦 Project root: $PROJECT_ROOT"

# --------------------------------------------------
# Ensure nginx is installed
# --------------------------------------------------
if ! command -v nginx &> /dev/null; then
    echo "❌ nginx not found. Install with: brew install nginx"
    exit 1
fi

# --------------------------------------------------
# Create directories if missing
# --------------------------------------------------
mkdir -p "$NGINX_CONF_DIR"
mkdir -p "$NGINX_SSL_DIR"

# --------------------------------------------------
# Symlink nginx configs
# --------------------------------------------------
echo "🔗 Linking nginx configs..."

for file in "$PROJECT_ROOT/nginx/"*.conf; do
    name=$(basename "$file")
    target="$NGINX_CONF_DIR/$name"

    if [ -L "$target" ] || [ -f "$target" ]; then
        echo "⚠️  Removing existing $target"
        rm -f "$target"
    fi

    ln -s "$file" "$target"
    echo "✔ Linked $name"
done

# --------------------------------------------------
# Generate self-signed SSL if missing
# --------------------------------------------------
CRT="$NGINX_SSL_DIR/nginx.crt"
KEY="$NGINX_SSL_DIR/nginx.key"

if [ ! -f "$CRT" ] || [ ! -f "$KEY" ]; then
    echo "🔐 Generating self-signed SSL certificate..."
    openssl req -x509 -nodes -days 365 \
        -newkey rsa:2048 \
        -keyout "$KEY" \
        -out "$CRT" \
        -subj "/C=US/ST=State/L=City/O=Dev/OU=Dev/CN=localhost"
    echo "✔ SSL certificate generated"
else
    echo "✔ SSL certificate already exists"
fi

# --------------------------------------------------
# Create .htpasswd if missing
# --------------------------------------------------
if [ ! -f "$NGINX_HTPASSWD" ]; then
    echo "🔑 Creating .htpasswd file"
    echo "Enter username for nginx basic auth:"
    read USERNAME
    htpasswd -c "$NGINX_HTPASSWD" "$USERNAME"
else
    echo "✔ .htpasswd already exists"
fi

# --------------------------------------------------
# Test nginx config
# --------------------------------------------------
echo "🧪 Testing nginx configuration..."
nginx -t

# --------------------------------------------------
# Restart nginx
# --------------------------------------------------
echo "🔄 Restarting nginx..."
brew services restart nginx

echo "✅ NGINX DEPLOY COMPLETE"
echo "Access your site at: https://localhost:8443"

