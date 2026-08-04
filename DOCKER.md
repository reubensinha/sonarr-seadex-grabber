# Docker Deployment Guide

## Quick Start

1. **Copy the environment template:**
   ```bash
   cp .env.docker .env
   ```

2. **Edit the `.env` file with your actual values:**
   - Set your Sonarr API key
   - Set your qBittorrent username and password
   - Adjust paths as needed

3. **Deploy with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

## Deployment Options

### Option 1: Standalone (if you have existing Sonarr/qBittorrent)
Use `docker-compose.yml` for just the Sonarr Seadex Grabber:
```bash
docker-compose up -d
```

### Option 2: Full Stack (includes Sonarr and qBittorrent)
Use `docker-compose.full.yml` for a complete setup:
```bash
docker-compose -f docker-compose.full.yml up -d
```

### Scheduled-only mode (no webhook)

There's no separate compose file for this - it's the default. Leave
`USE_WEBHOOK=false` (or omit it) in either option above and the container
only runs on `SYNC_INTERVAL`'s schedule. The dashboard is still reachable
either way; the flag only controls whether incoming Sonarr webhook events
also trigger a sync.

## Configuration

### Environment Variables
The application supports the following environment variables:

**Required:**
- `SONARR_URL` - Your Sonarr instance URL
- `SONARR_API_KEY` - Your Sonarr API key
- `QB_URL` - Your qBittorrent Web UI URL
- `QB_USER` - qBittorrent username
- `QB_PASS` - qBittorrent password
- `WEBHOOK_HOST` - Must be `0.0.0.0` for the dashboard to be reachable from
  outside the container. The app's own default is `localhost` (meant for a
  bare-metal run on the same machine you're browsing from) - that's
  container-unreachable, so `docker-compose.yml` hardcodes `0.0.0.0` for you
  already. Only relevant if you're running the image directly (`docker run`)
  without that compose file.

**Optional:**
- `QB_CATEGORY` - qBittorrent category for downloads (default: anime-sonarr)
- `SONARR_SERIES_TYPE` - Type of series to monitor (e.g., "anime", "standard")
- `SONARR_TAGS` - Comma-separated list of tags to filter series (e.g., "anime,imported")
- `WEBHOOK_PORT` - Webhook server port (default: 8765)
- `USE_WEBHOOK` - Enable webhook server (default: false)
- `STARTUP_SCAN` - Perform scan on startup (default: false)
- `SYNC_INTERVAL` - Sync interval in seconds (default: 86400)

### `config.yaml` is optional

Every setting checks its environment variable first (`core/config.py`), and
the app runs fine even if `config.yaml` doesn't exist at all - it just logs a
warning and falls back to environment variables/defaults. So filling in
`.env` and running `docker-compose up` works out of the box; you never need
to touch `config.yaml` for the app to work. The only exception is
`scoring.tracker_weights` (per-tracker score adjustments), which is
config.yaml-only with no environment variable equivalent - but it already
has a sensible built-in default, so it's purely optional fine-tuning.

### Custom Configuration
If you do want to override `scoring.tracker_weights` (or just prefer YAML),
copy `config.yaml.example` to `config.yaml` and mount it:
```yaml
volumes:
  - ./config.yaml:/app/config.yaml:ro
```

## Accessing the Application

- **Dashboard / WebUI:** http://localhost:8765
- **Sonarr webhook URL:** http://localhost:8765/webhook
- **Health Check:** http://localhost:8765/health
- **Sonarr (if using full stack):** http://localhost:8989
- **qBittorrent (if using full stack):** http://localhost:8080

The dashboard and health check are always reachable on this port, regardless
of `USE_WEBHOOK` - that variable only controls whether incoming Sonarr
webhook events trigger a sync.

## Data Persistence

The application stores cache data in `/app/data` inside the container. This is mapped to a Docker volume for persistence.

## Logs

View application logs:
```bash
docker-compose logs -f sonarr-seadex-grabber
```

## Updates

To update to the latest version:
```bash
docker-compose pull
docker-compose up -d
```

## Troubleshooting

1. **Check container status:**
   ```bash
   docker-compose ps
   ```

2. **View logs:**
   ```bash
   docker-compose logs sonarr-seadex-grabber
   ```

3. **Restart services:**
   ```bash
   docker-compose restart
   ```

4. **Health check:**
   ```bash
   curl http://localhost:8765/health
   ```

## Publishing a new image

Publishing is automated via GitHub Actions (`.github/workflows/release.yml`)
- there's no manual build/push step for maintainers anymore. When a pull
request is merged into `main`:

1. Lint and tests re-run as a safety net.
2. A new version tag is computed from the highest existing `vX.Y.Z` git tag -
   **patch** by default, or **minor**/**major** if the PR has a
   `bump:minor`/`bump:major` label.
3. The image is built and pushed to
   `ghcr.io/reubensinha/sonarr-seadex-grabber`, tagged both `vX.Y.Z` and
   `latest`.
4. A GitHub Release is created for the new tag.

To ship a change that's more than a patch bump, add the `bump:minor` or
`bump:major` label to its pull request before merging.
