# Cursor Skills

A collection of custom Cursor AI agent skills for automation and integration with external services.

## Overview

This repository contains reusable skills that extend [Cursor](https://cursor.com) agent capabilities. Each skill is a self-contained tool that enables agents to perform specialized tasks, from managing torrents to monitoring infrastructure and market data.

## Skills

### Add Torrent
Manages movie and show torrents with smart auto-detection.

- **Location**: `.cursor/skills/add-torrent/`
- **Features**:
  - Add torrents to your media library (movies or shows)
  - Inspect torrent metadata (title, files) so the agent can pick the type and title
  - Rewrite ToTheGlory page links (`/t/{id}/`) to direct download links
  - Requires: `TORRENT_PATH_SECRET`, `TORRENT_DL_TOKEN` environment variables

### Send Telegram
Simple messaging integration for notifications and alerts.

- **Location**: `.cursor/skills/send-telegram/`
- **Features**:
  - Post messages via Telegram Bot API
  - Send photos with optional captions (`--photo`)
  - Receive alerts and notifications from other skills
  - Requires: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` environment variables

### WMT/VTI Ratio
Real-time financial market data monitoring.

- **Location**: `.cursor/skills/wmt-vti-ratio/`
- **Features**:
  - Fetch live WMT (Walmart) and VTI (Vanguard Total Stock Market ETF) prices
  - Calculate and report WMT/VTI ratio (liquid proxy for former FSKAX comparison)
  - Render a 45-day close-price ratio chart (today = live/spot) and Telegram it first
  - Use live prices during the US regular session, latest close otherwise
  - Automatic Telegram notifications (via Send Telegram)
  - Requires: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `matplotlib`

### Check HTTPS Certificates
Monitor HTTPS certificate expiry and validity.

- **Location**: `.cursor/skills/check-https-certs/`
- **Features**:
  - Verify TLS certificates for multiple domains in parallel
  - Monitor: `shaneqi.dev`, `shaneqi.com`, `ruzhang.dev`, `eastwatch.app`, `eastwatchapp.com`, `qis.family`
  - Check expiry dates and certificate trust status (warn ≤30 days, critical ≤14 days)
  - Report on both apex and www domains, as a table or `--json`

### Moin Wiki
Search and read the private MoinMoin wiki at `wiki.qis.family`.

- **Location**: `.cursor/skills/moin-wiki/`
- **Features**:
  - Full-text search with optional page excerpts or full markup
  - Fetch a page or its metadata by exact name
  - List and filter page titles
  - Read-only (no edits or deletes)
  - Requires: `MOIN_USERNAME`, `MOIN_PASSWORD` (optional `MOIN_URL`)

### iCloud Calendar
Read and write iCloud Calendar over CalDAV.

- **Location**: `.cursor/skills/icloud-calendar/`
- **Features**:
  - List calendars and events
  - Create and delete events
  - Default target calendar: `Qi`; naive times use `America/Chicago`
  - Requires: `ICLOUD_EMAIL` (Apple ID), `ICLOUD_CALDAV` (app-specific password)

## Project Structure

```
.cursor/
├── settings.json        # Cursor settings
└── skills/
    ├── add-torrent/
    ├── send-telegram/
    ├── wmt-vti-ratio/
    ├── check-https-certs/
    ├── moin-wiki/
    └── icloud-calendar/
```

Each skill contains:
- **SKILL.md** — Detailed documentation on usage and implementation
- **scripts/** — Python and shell helpers the agent runs
- **Configuration** — Environment variable requirements

## Getting Started

1. **Clone the repository**:
   ```bash
   git clone https://github.com/ShaneQi/Cursor.git
   cd Cursor
   ```

2. **Set up environment variables**:
   Export the required variables for the skills you plan to use:
   ```bash
   export TELEGRAM_BOT_TOKEN="your_token"
   export TELEGRAM_CHAT_ID="your_chat_id"
   export TORRENT_PATH_SECRET="your_secret"
   export TORRENT_DL_TOKEN="your_token"
   export MOIN_USERNAME="your_wiki_user"
   export MOIN_PASSWORD="your_wiki_password"
   export ICLOUD_EMAIL="your_apple_id@example.com"
   export ICLOUD_CALDAV="your-app-specific-password"
   ```

3. **Install optional dependencies** (only needed for the WMT/VTI chart):
   ```bash
   pip install matplotlib
   ```

4. **Use skills in Cursor**:
   Cursor agents can discover and use these skills automatically when the `.cursor` directory is present in your project.

## Requirements

- **Python 3.9+** — all helpers use only the standard library, except `matplotlib` for the WMT/VTI chart
- **Bash** and **curl** — for `add-torrent.sh`
- Outbound HTTPS access to the services each skill talks to

## Contributing

Feel free to submit pull requests or open issues for new skills, improvements, or bug fixes.

## Author

[Shane Qi](https://github.com/ShaneQi)
