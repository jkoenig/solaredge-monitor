# SolarEdge Off-Grid Monitor

A Raspberry Pi-powered e-ink display that shows your SolarEdge solar energy data at a glance — production, consumption, grid feed-in, and purchased energy.

The display cycles through 4 screens, each showing a daily energy metric with a proportional bar and breakdown. Updates every 5 minutes. Sleeps at night.

## Screens

| Produktion | Verbrauch |
|:---:|:---:|
| ![Produktion](docs/screen-produktion.png) | ![Verbrauch](docs/screen-verbrauch.png) |
| **Einspeisung** | **Bezug** |
| ![Einspeisung](docs/screen-einspeisung.png) | ![Bezug](docs/screen-bezug.png) |

## Hardware

| Part | Model |
|------|-------|
| Computer | Raspberry Pi Zero WH v1.1 (1 GHz, 512 MB RAM, WLAN, BT) 
| Display | DEBO EPA 2.1 — 2.13" e-paper, black/white (Waveshare compatible)
| Power supply | Official RPi PSU, 5.1V / 2.5A, micro-USB 
| Storage | SanDisk Ultra microSDXC 64GB 

Total: ~CHF 49

## Prerequisites

- Python 3.9+
- A [SolarEdge monitoring account](https://monitoring.solaredge.com) with API access
- SolarEdge API key ([how to get one](https://knowledge-center.solaredge.com/sites/kc/files/se_monitoring_api.pdf))
- Your SolarEdge site ID

## Setup

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/solaredge-offgrid-monitor.git
cd solaredge-offgrid-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
SOLAREDGE_API_KEY=your_api_key_here
SOLAREDGE_SITE_ID=your_site_id_here
```

Optional settings (defaults shown):

```env
SOLAREDGE_POLL_INTERVAL=5    # Minutes between API polls
SOLAREDGE_SLEEP_START=0      # Hour to pause (0 = midnight)
SOLAREDGE_SLEEP_END=6        # Hour to resume (6 = 6 AM)
SOLAREDGE_DEBUG=false        # true = PNG output instead of e-ink
```

### 3. Test (without hardware)

```bash
SOLAREDGE_DEBUG=true python3 main.py
```

Debug mode saves screen renders as PNG files in the `debug/` folder instead of driving the e-ink display.

## Raspberry Pi Setup

### Enable SPI

```bash
sudo raspi-config
# Interface Options → SPI → Enable
sudo reboot
```

### Install system dependencies

```bash
sudo apt-get update
sudo apt-get install python3-pip python3-venv python3-dev
```

### Deploy

```bash
git clone https://github.com/YOUR_USERNAME/solaredge-offgrid-monitor.git
cd solaredge-offgrid-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API credentials
```

### Run as a service (systemd)

Create `/etc/systemd/system/solaredge-monitor.service`:

```ini
[Unit]
Description=SolarEdge Off-Grid Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/solaredge-offgrid-monitor
ExecStart=/home/pi/solaredge-offgrid-monitor/venv/bin/python3 main.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable solaredge-monitor
sudo systemctl start solaredge-monitor
```

## Project Structure

```
.
├── main.py              # Entry point
├── config.py            # Environment-based configuration
├── solaredge_api.py     # SolarEdge API client with retry logic
├── models.py            # Data models (PowerFlow, EnergyDetails, SiteOverview)
├── display.py           # Display abstraction (e-ink / PNG fallback)
├── screens/             # Screen renderers (one per display screen)
│   ├── production.py    # Produktion — daily production + breakdown
│   ├── consumption.py   # Verbrauch — daily consumption + sources
│   ├── feed_in.py       # Einspeisung — grid feed-in
│   └── purchased.py     # Bezug — grid purchase
├── rendering/           # Drawing primitives (fonts, icons, bars)
├── fonts/               # Arial, ArialBlack (bundled for Pi)
├── lib/waveshare_epd/   # Waveshare e-ink driver (epd2in13_V3)
├── .env.example         # Configuration template
└── requirements.txt     # Python dependencies
```

## How It Works

1. Fetches energy data from the SolarEdge monitoring API every 5 minutes
2. Renders 4 screens at 4x resolution (1000x488) using PIL
3. Downsamples to 250x122 with LANCZOS resampling for crisp text on e-ink
4. Cycles through screens on the e-ink display
5. Sleeps between midnight and 6 AM (no solar production)

## License

MIT
