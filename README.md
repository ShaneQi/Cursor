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
  - Auto-detect content type (movie vs. show) and title from torrent metadata
  - Support for ToTheGlory page link rewrites
  - Requires: `TORRENT_PATH_SECRET`, `TORRENT_DL_TOKEN` environment variables

### Send Telegram
Simple messaging integration for notifications and alerts.

- **Location**: `.cursor/skills/send-telegram/`
- **Features**:
  - Post messages via Telegram Bot API
  - Receive alerts and notifications from other skills
  - Requires: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` environment variables

### WMT/VTI Ratio
Real-time financial market data monitoring.

- **Location**: `.cursor/skills/wmt-vti-ratio/`
- **Features**:
  - Fetch live WMT (Walmart) and VTI (Vanguard Total Stock Market ETF) prices
  - Calculate and report WMT/VTI ratio (liquid proxy for former FSKAX comparison)
  - Support for both regular trading hours and after-hours data
  - Automatic Telegram notifications
  - Requires: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` environment variables

### Check TLS Certificates
Monitor HTTPS certificate expiry and validity.

- **Location**: `.cursor/skills/check-tls-certs/`
- **Features**:
  - Verify TLS certificates for multiple domains
  - Monitor: `shaneqi.*`, `ruzhang.dev`, `eastwatch.*`, `qis.family`
  - Check expiry dates and certificate trust status
  - Report on both apex and www domains

### Fill Card Statements
Automate financial record management.

- **Location**: `.cursor/skills/fill-card-statements/`
- **Features**:
  - Populate card statement information
  - See `SKILL.md` in the skill directory for detailed usage and implementation

## Project Structure

```
.cursor/
├── skills/
│   ├── add-torrent/
│   ├── send-telegram/
│   ├── wmt-vti-ratio/
│   ├── check-tls-certs/
│   └── fill-card-statements/
```

Each skill contains:
- **SKILL.md** — Detailed documentation on usage and implementation
- **Helper scripts** — Python and shell scripts for execution
- **Configuration** — Environment variable requirements

## Getting Started

1. **Clone the repository**:
   ```bash
   git clone https://github.com/ShaneQi/Cursor.git
   cd Cursor
   ```

2. **Set up environment variables**:
   Create a `.env` file or export the required variables for the skills you plan to use:
   ```bash
   export TELEGRAM_BOT_TOKEN="your_token"
   export TELEGRAM_CHAT_ID="your_chat_id"
   export TORRENT_PATH_SECRET="your_secret"
   export TORRENT_DL_TOKEN="your_token"
   ```

3. **Use skills in Cursor**:
   Cursor agents can discover and use these skills automatically when the `.cursor` directory is present in your project.

## Requirements

- **Python** (92.4% of codebase)
- **Shell** (7.6% of codebase)

## Contributing

Feel free to submit pull requests or open issues for new skills, improvements, or bug fixes.

## License

This project is open source. See LICENSE file for details.

## Author

[Shane Qi](https://github.com/ShaneQi)
