#!/bin/bash
set -e

# ============================================================
# SolarEdge Monitor - Deploy Script
# ============================================================
# This script updates the code from git, installs a changed
# systemd unit file and restarts the service. Run this on the
# Pi to deploy updates.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Refuse to run as root
if [ "$EUID" -eq 0 ]; then
  echo "ERROR: Do not run this script as root or with sudo."
  echo "Run as the 'pi' user: ./deploy.sh"
  exit 1
fi

# All steps live in main() and the last line of the file calls it.
# Bash reads scripts incrementally, and "git pull" may replace this
# very file while it runs; with everything parsed up front that is safe.
main() {
  echo ""
  echo "========================================"
  echo "SolarEdge Monitor - Deployment"
  echo "========================================"
  echo ""

  # Step 1: Pull latest code
  echo "[1/4] Pulling latest code from git..."
  git pull
  echo "  ✓ Code updated"
  echo ""

  # Step 2: Update dependencies
  echo "[2/4] Updating Python dependencies..."
  venv/bin/pip install -r requirements.txt -q
  echo "  ✓ Dependencies updated"
  echo ""

  # Step 3: Install the systemd unit if it changed
  echo "[3/4] Checking systemd unit..."
  UNIT_NAME="solaredge-monitor.service"
  UNIT_SRC="$SCRIPT_DIR/$UNIT_NAME"
  # SOLAREDGE_UNIT_DST is an override for tests only.
  UNIT_DST="${SOLAREDGE_UNIT_DST:-/etc/systemd/system/$UNIT_NAME}"
  if ! cmp -s "$UNIT_SRC" "$UNIT_DST"; then
    echo "  Unit file changed, installing..."
    sudo install -m 644 -o root -g root "$UNIT_SRC" "$UNIT_DST"
    sudo systemctl daemon-reload
    sudo systemctl enable solaredge-monitor
    echo "  ✓ Unit file installed"
  else
    echo "  Unit file unchanged"
  fi
  echo ""

  # Step 4: Restart service
  echo "[4/4] Restarting solaredge-monitor service..."
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
}

main "$@"; exit $?
