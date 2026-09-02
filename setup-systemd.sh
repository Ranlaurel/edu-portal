#!/bin/bash
set -e

echo "Setting up systemd service for edu-portal..."

# Configuration
SERVICE_NAME="edu-portal"
WORK_DIR="/var/www/edu-portal"
PORT=8002
USER="www-data"

# Create systemd unit file
echo "Creating systemd unit file..."
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=Edu Portal FastAPI Application
After=network.target

[Service]
Type=simple
User=${USER}
Group=${USER}
WorkingDirectory=${WORK_DIR}
Environment="PATH=${WORK_DIR}/.venv/bin"
ExecStart=${WORK_DIR}/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${PORT}
Restart=always
RestartSec=3
StandardOutput=append:${WORK_DIR}/app.log
StandardError=append:${WORK_DIR}/app.log

[Install]
WantedBy=multi-user.target
EOF

# Set correct permissions
echo "Setting file permissions..."
sudo chown -R ${USER}:${USER} ${WORK_DIR}/.venv
sudo chmod +x ${WORK_DIR}/.venv/bin/uvicorn

# Reload systemd and enable service
echo "Reloading systemd..."
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}

# Wait and check status
sleep 2
if systemctl is-active --quiet ${SERVICE_NAME}; then
  echo "✓ Service ${SERVICE_NAME} is running on port ${PORT}"
  systemctl status ${SERVICE_NAME} --no-pager -n 5
else
  echo "✗ Service failed to start"
  systemctl status ${SERVICE_NAME} --no-pager -n 20
  exit 1
fi

# Update Caddyfile if needed
echo ""
echo "Checking Caddy configuration..."
if ! grep -q "edu.rvnza.ru" /etc/caddy/Caddyfile 2>/dev/null; then
  echo "Adding edu.rvnza.ru to Caddyfile..."
  sudo tee -a /etc/caddy/Caddyfile > /dev/null <<'CADDY_EOF'

edu.rvnza.ru {
    reverse_proxy 127.0.0.1:8002
    encode gzip
    
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        X-XSS-Protection "1; mode=block"
        Referrer-Policy "strict-origin-when-cross-origin"
        -Server
    }
}
CADDY_EOF
  
  echo "Reloading Caddy..."
  sudo systemctl reload caddy || sudo systemctl restart caddy
  echo "✓ Caddy configured for edu.rvnza.ru"
else
  echo "edu.rvnza.ru already configured in Caddyfile"
  # Check if port matches
  if ! grep -A 1 "edu.rvnza.ru" /etc/caddy/Caddyfile | grep -q "127.0.0.1:${PORT}"; then
    echo "⚠ WARNING: Caddyfile may point to wrong port. Current service uses port ${PORT}"
  fi
fi

echo ""
echo "Setup completed!"
echo "Service is listening on 127.0.0.1:${PORT}"
echo "External access: https://edu.rvnza.ru"
