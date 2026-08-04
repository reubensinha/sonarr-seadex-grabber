# Seadex-Sonarr Connector

[![CI](https://github.com/reubensinha/sonarr-seadex-grabber/actions/workflows/ci.yml/badge.svg)](https://github.com/reubensinha/sonarr-seadex-grabber/actions/workflows/ci.yml)
[![GHCR](https://img.shields.io/badge/ghcr.io-sonarr--seadex--grabber-blue?logo=docker)](https://github.com/reubensinha/sonarr-seadex-grabber/pkgs/container/sonarr-seadex-grabber)

A Python application that monitors your Sonarr library and automatically fetches high-quality releases from Seadex.

## Quick Start (Docker)

This app is intended to run as a Docker container against your existing
Sonarr and qBittorrent instances - a published image is built and tagged
automatically on every release (see
[DOCKER.md](DOCKER.md#publishing-a-new-image)), so you don't need to clone
this repo. Save the following as `docker-compose.yml`, fill in the five
`your-*` placeholders below (leave `WEBHOOK_HOST` as-is), and run
`docker-compose up -d` next to it:

```yaml
services:
  sonarr-seadex-grabber:
    image: ghcr.io/reubensinha/sonarr-seadex-grabber:latest
    container_name: sonarr-seadex-grabber
    restart: unless-stopped
    ports:
      - "8765:8765"
    volumes:
      - ./data:/app/data
    environment:
      # Required - your existing Sonarr/qBittorrent instances
      - SONARR_URL=http://your-sonarr-host:8989
      - SONARR_API_KEY=your-sonarr-api-key
      - QB_URL=http://your-qbittorrent-host:8080
      - QB_USER=your-qbittorrent-username
      - QB_PASS=your-qbittorrent-password

      # Required - binds the dashboard/webhook server to all interfaces so
      # it's reachable through the port mapping above. Leaving this unset
      # defaults to localhost-only, which is unreachable from outside the
      # container.
      - WEBHOOK_HOST=0.0.0.0

      # Optional
      - QB_CATEGORY=anime-sonarr    # qBittorrent category for downloads
      - SYNC_INTERVAL=86400         # seconds between scheduled syncs (24h) - also adjustable later from the Settings page
      - STARTUP_SCAN=false          # true: populate the cache on first launch without downloading anything
      - USE_WEBHOOK=false           # true once you've set up the Sonarr webhook below
```

Once it's running, open `http://<host>:8765` for the dashboard (see
[WebUI](#webui) below) - no `config.yaml` edit is required, everything above
is set via environment variables. `./data` is where `known_series.json` and
other cache files persist across container restarts, so keep that volume
mount.

Got the repo checked out instead? `cp .env.docker .env` (fill it in), then
`docker-compose up -d` uses the `docker-compose.yml` already in this repo -
same result. See [DOCKER.md](DOCKER.md) for the full environment variable
reference and the full-stack compose file that also bundles Sonarr and
qBittorrent for you.

## WebUI

Open `http://<host>:8765/` for a dashboard showing monitored series, their
AniList mappings, tracked torrents, and recent activity. It also has a
client-side search box to quickly filter the series list by title. From
there you can:

- Trigger a full sync, or **Resync** a single series (refreshes its
  Sonarr-sourced fields, AniList mapping, and Seadex torrents)
- **Re-search Seadex** for a series - re-queries Seadex for its existing
  AniList entries only, without touching AniList mapping (safe to use after
  cleaning up a mapping, won't reintroduce a bad title-search match)
- Ignore/un-ignore an AniList entry
- **Remove** an AniList entry entirely - unlike Ignore, this also blacklists
  the AniList ID so it can't silently reappear via a future title/TVDB search
- **Prefer** a torrent (marks your pick with no network call - useful for
  private-tracker releases the app can't auto-download) or **Download** it
  (submits to qBittorrent). A pending preferred-but-undownloaded pick pauses
  automatic best-selection for that entry until you explicitly download
  something
- Add a manual AniList mapping via a live search box (type a title, click a
  result to add it) instead of typing a raw AniList ID
- Lazy-load the most recent Sonarr import event for a series (release name,
  date, quality)
- Follow links out to the series' Sonarr page, its AniList page, its SeaDex
  entry, and each torrent's own page

This replaces hand-editing `data/known_series.json`.

## Sonarr Webhook Setup

With `webhook.enabled` (or `USE_WEBHOOK=true`) set, Sonarr can trigger an
immediate sync instead of waiting for the next scheduled run. In Sonarr, go
to **Settings → Connect → Add → Webhook** and configure:

- **URL:** `http://<host>:8765/webhook`
- **Method:** `POST`
- **Triggers:** On Series Add, On Series Delete, On Series Edit

## Running without Docker

```bash
pip install -r requirements.txt
cp .env.example .env       # or cp config.yaml.example config.yaml - see below
# edit .env (or config.yaml) with your Sonarr/qBittorrent details
python main.py
```

Every setting can be set via an environment variable (`.env`, loaded via
python-dotenv) - `config.yaml` is entirely optional, see the comments in
[config.yaml.example](config.yaml.example) for the full list and their
environment variable equivalents. The one exception is
`scoring.tracker_weights` (per-tracker score adjustments), which is
config.yaml-only but already has a sensible built-in default.

This starts the sync loop plus a web server on `webhook.host:webhook.port`
(default `http://localhost:8765`) that serves both the dashboard and the
Sonarr webhook endpoint - it's always running, regardless of whether
`webhook.enabled` is turned on.

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check .
pytest
```

Both run in CI (`.github/workflows/ci.yml`) on every pull request targeting
`main`. See [DOCKER.md](DOCKER.md#publishing-a-new-image) for how merging to
`main` turns into a tagged, published Docker image.

## Planned

- [x] Move config.py to more persistent location.
- [x] Add a WebUI.
