#!/bin/bash
set -e

echo "Setting up Caddy configuration for edu.rvnza.ru..."

# Check if already configured
if grep -q "edu.rvnza.ru" /etc/caddy/Caddyfile 2>/dev/null; then
  echo "edu.rvnza.ru already configured in Caddyfile"
  exit 0
fi

echo "Adding edu.rvnza.ru to Caddyfile..."

sudo tee -a /etc/caddy/Caddyfile > /dev/null <<'EOF'

edu.rvnza.ru {
    reverse_proxy localhost:8000
    encode gzip
    
    log {
        output file /var/log/caddy/edu-portal.log
        level INFO
    }
    
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        X-XSS-Protection "1; mode=block"
        Referrer-Policy "strict-origin-when-cross-origin"
        -Server
    }
}
EOF

echo "Caddyfile updated successfully"
