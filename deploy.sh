#!/bin/bash
set -e

# ============================================================
# SolarEdge Monitor - Deploy Script
# ============================================================
# This script updates the code from git and restarts the
# systemd service. Run this on the Pi to deploy updates.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Refuse to run as root
if [ "$EUID" -eq 0 ]; then
  echo "ERROR: Do not run this script as root or with sudo."
  echo "Run as the 'pi' user: ./deploy.sh"
  exit 1
fi

echo ""
echo "========================================"
echo "SolarEdge Monitor - Deployment"
echo "========================================"
echo ""

# Step 1: Pull latest code
echo "[1/3] Pulling latest code from git..."
git pull
echo "  ✓ Code updated"
echo ""

# Step 2: Update dependencies
echo "[2/3] Updating Python dependencies..."
venv/bin/pip install -r requirements.txt -q
echo "  ✓ Dependencies updated"
echo ""

# Step 3: Restart service
echo "[3/3] Restarting solaredge-monitor service..."
sudo systemctl restart solaredge-monitor
echo "  ✓ Service restarted"
echo ""

echo "========================================"
echo "Deployment Complete!"
echo "========================================"
echo ""
echo "Service status:"
echo ""
sudo systemctl status solaredge-monitor --no-pager -l
echo ""
