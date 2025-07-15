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

## Configuration

### Environment Variables
The application supports the following environment variables:

**Required:**
- `SONARR_URL` - Your Sonarr instance URL
- `SONARR_API_KEY` - Your Sonarr API key
- `QB_URL` - Your qBittorrent Web UI URL
- `QB_USER` - qBittorrent username
- `QB_PASS` - qBittorrent password
- `QB_CATEGORY` - qBittorrent category for downloads (default: anime-sonarr)

**Optional Sonarr Filtering:**
- `SONARR_SERIES_TYPE` - Type of series to monitor (e.g., "anime", "standard")
- `SONARR_TAGS` - Comma-separated list of tags to filter series (e.g., "anime,imported")

**Optional:**
- `WEBHOOK_HOST` - Webhook server host (default: 0.0.0.0)
- `WEBHOOK_PORT` - Webhook server port (default: 8765)
- `USE_WEBHOOK` - Enable webhook server (default: false)
- `STARTUP_SCAN` - Perform scan on startup (default: false)
- `SYNC_INTERVAL` - Sync interval in seconds (default: 86400)

### Custom Configuration
You can mount a custom `config.yaml` file:
```yaml
volumes:
  - ./config.yaml:/app/config.yaml:ro
```

## Accessing the Application

- **Webhook Server:** http://localhost:8000
- **Health Check:** http://localhost:8000/health
- **Sonarr (if using full stack):** http://localhost:8989
- **qBittorrent (if using full stack):** http://localhost:8080

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
   curl http://localhost:8000/health
   ```
