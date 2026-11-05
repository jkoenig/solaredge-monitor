# Phase 11: OAuth Login & Token Store - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md. This log keeps the alternatives that were considered.

**Date:** 2026-11-05
**Phase:** 11-oauth-login-token-store
**Areas discussed:** Login nötig screen, Getting tokens onto the Pi, Client secret & site ID on the Pi, Login script shape

User asked to continue the discussion in German.

---

## Login nötig screen

| Option | Description | Selected |
|--------|-------------|----------|
| Titel + Hinweis | "Login nötig" + "Mac: login-Skript starten" | ✓ |
| Titel + Grund | "Login nötig" + reason (abgelaufen/fehlt/ungültig) | |
| Nur "Login nötig" | Text only | |

| Option | Description | Selected |
|--------|-------------|----------|
| Sofort | As soon as token is known unusable | ✓ |
| Nach mehreren Versuchen | After 3 failures like generic error | |

| Option | Description | Selected |
|--------|-------------|----------|
| Nur Login-Hinweis | No stale data rotation | ✓ |
| Abwechselnd | Stale screens + login screen in rotation | |

## Getting tokens onto the Pi

| Option | Description | Selected |
|--------|-------------|----------|
| Skript kopiert selbst | scp to se-monitor, 0600, delete local copy | ✓ |
| Lokal speichern | User copies manually | |

| Option | Description | Selected |
|--------|-------------|----------|
| Im App-Ordner | /home/pi/solaredge-monitor/.tokens.json | ✓ |
| Eigener State-Ordner | ~/.local/state/solaredge-monitor/ | |

| Option | Description | Selected |
|--------|-------------|----------|
| Automatisch | Pi checks for new file each loop | ✓ |
| Skript startet Dienst neu | systemctl restart via SSH | |

## Client secret & site ID on the Pi

| Option | Description | Selected |
|--------|-------------|----------|
| .env von Hand | User types into .env | |
| In Token-Datei | Script writes secrets into token file | |
| Other | "im deploy aus 1pass holen" | ✓ |

Follow-up clarification:

| Option | Description | Selected |
|--------|-------------|----------|
| Mac-Schritt schreibt .env | Mac reads op, writes Pi .env via SSH | ✓ |
| op auf dem Pi | Install 1Password CLI on Pi | |
| Neues Mac-Deploy-Skript | Mac script does pull + secrets + restart | |

| Option | Description | Selected |
|--------|-------------|----------|
| Aus Token-Datei | site_id from login, SOLAREDGE_SITE_ID dropped | ✓ |
| .env bleibt Pflicht | | |
| .env optional, Login gewinnt | | |

| Option | Description | Selected |
|--------|-------------|----------|
| In Phase 12 entfernen | API key removed with V1 code | ✓ |
| Jetzt schon optional | | |

## Login script shape

| Option | Description | Selected |
|--------|-------------|----------|
| Ein Befehl | Login + tokens + .env secrets, `--secrets-only` flag | ✓ |
| Zwei getrennte Befehle | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Python, ohne Extras | scripts/solaredge_login.py, stdlib only | ✓ |
| Python mit Repo-venv | | |
| Shell-Skript | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Nur im Log | Daily warning 30 days before 24-month expiry | ✓ |
| Log + Display-Hinweis | | |
| Gar nicht | | |

## Claude's Discretion

Refresh threshold, module layout, loop state representation, script verbosity, lock and file-change detection details, no refresh during sleep.

## Deferred Ideas

None.
