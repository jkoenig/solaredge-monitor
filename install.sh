#!/bin/bash
set -e
set -u

# ============================================================
# SolarEdge Monitor - Initial Raspberry Pi Setup
# ============================================================
# This script automates the full Pi setup: SPI, venv, deps,
# .env, and systemd service installation.
# Run this once on a fresh Pi Zero WH as the 'pi' user.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Refuse to run as root
if [ "$EUID" -eq 0 ]; then
  echo "ERROR: Do not run this script as root or with sudo."
  echo "Run as the 'pi' user: ./install.sh"
  exit 1
fi

REBOOT_REQUIRED=false
NEEDS_ENV_CONFIG=false

echo ""
echo "========================================"
echo "SolarEdge Monitor - Initial Setup"
echo "========================================"
echo ""

# [1/6] Check and enable SPI
echo "[1/6] Checking SPI interface..."
if ls /dev/spidev* &>/dev/null; then
  echo "  ✓ SPI already enabled"
else
  echo "  Enabling SPI interface..."
  sudo raspi-config nonint do_spi 0
  REBOOT_REQUIRED=true
  echo "  ✓ SPI enabled (reboot required)"
fi

# [2/6] Add user to spi and gpio groups
echo "[2/6] Checking user groups..."
if groups "$USER" | grep -q "spi"; then
  echo "  ✓ User already in 'spi' group"
else
  echo "  Adding user to 'spi' group..."
  sudo usermod -a -G spi "$USER"
  echo "  ✓ Added to 'spi' group (reboot required)"
  REBOOT_REQUIRED=true
fi

if groups "$USER" | grep -q "gpio"; then
  echo "  ✓ User already in 'gpio' group"
else
  echo "  Adding user to 'gpio' group..."
  sudo usermod -a -G gpio "$USER"
  echo "  ✓ Added to 'gpio' group (reboot required)"
  REBOOT_REQUIRED=true
fi

# [3/6] Create virtual environment
echo "[3/6] Setting up Python virtual environment..."
if [ -d "venv" ]; then
  echo "  ✓ Virtual environment already exists"
else
  echo "  Creating virtual environment..."
  python3 -m venv venv
  echo "  ✓ Virtual environment created"
fi

# [4/6] Install Python dependencies
echo "[4/6] Installing Python dependencies..."
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q
venv/bin/pip install -r requirements-pi.txt -q
echo "  ✓ Dependencies installed"

# [5/6] Create .env file
echo "[5/6] Configuring environment variables..."
if [ -f ".env" ]; then
  echo "  ✓ .env file already exists (preserving)"
else
  if [ -f ".env.example" ]; then
    cp .env.example .env
    NEEDS_ENV_CONFIG=true
    echo "  ✓ Created .env from .env.example"
  else
    echo "  ⚠ WARNING: .env.example not found"
    NEEDS_ENV_CONFIG=true
  fi
fi

# [6/6] Install systemd service
echo "[6/6] Installing systemd service..."
sudo cp solaredge-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable solaredge-monitor
echo "  ✓ Service installed and enabled"

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""

# Print next steps based on what's needed
if [ "$REBOOT_REQUIRED" = true ]; then
  echo "NEXT STEPS:"
  echo ""
  if [ "$NEEDS_ENV_CONFIG" = true ]; then
    echo "1. Edit .env file with your SolarEdge credentials:"
    echo "   nano .env"
    echo ""
    echo "2. Reboot to apply SPI and group changes:"
    echo "   sudo reboot"
    echo ""
    echo "3. After reboot, the service will start automatically."
  else
    echo "1. Reboot to apply SPI and group changes:"
    echo "   sudo reboot"
    echo ""
    echo "2. After reboot, the service will start automatically."
  fi
else
  if [ "$NEEDS_ENV_CONFIG" = true ]; then
    echo "NEXT STEPS:"
    echo ""
    echo "1. Edit .env file with your SolarEdge credentials:"
    echo "   nano .env"
    echo ""
    echo "2. Start the service:"
    echo "   sudo systemctl start solaredge-monitor"
    echo ""
    echo "3. Check status:"
    echo "   sudo systemctl status solaredge-monitor"
  else
    echo "The service is ready to start:"
    echo ""
    echo "  sudo systemctl start solaredge-monitor"
    echo ""
    echo "Check status:"
    echo "  sudo systemctl status solaredge-monitor"
  fi
fi

echo ""
