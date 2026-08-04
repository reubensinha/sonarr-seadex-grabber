# Seadex-Sonarr Connector

A Python application that monitors your Sonarr library and automatically fetches high-quality releases from Seadex.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configuration

1. Copy the example configuration file:

   ```bash
   cp config.yaml.example config.yaml
   ```

2. Edit `config.yaml` with your specific settings:

   ```yaml
   # Sonarr configuration
   sonarr:
     url: "http://your-sonarr-host:8989"
     api_key: "your_actual_sonarr_api_key"
     series_type: "anime"              # Filter by series type (optional)
     tags: [1, 2]                      # Filter by tag IDs (optional)

   # Torrent scoring configuration
   scoring:
     is_best_weight: 2                 # Points for "best" torrents
     dual_audio_weight: 1              # Points for dual audio
     tracker_weights:
       "Nyaa": 0                       # Baseline tracker
       "AnimeTosho": -2                # Small penalty
       "default": -10                  # Default penalty

   # qBittorrent configuration
   qbittorrent:
     url: "http://your-qbittorrent-host:8080"
     username: "your_username"
     password: "your_password"
     category: "tv-sonarr"             # Category for downloads

   # Webhook Server configuration
   webhook:
     host: "localhost"
     port: 8765
     enabled: true
   ```

### 3. Configuration Options

- **Data Settings**: Configure where cache files are stored
- **Scheduling**: Set how often the sync runs (default: 24 hours)
- **Sonarr**:
  - URL and API key for your Sonarr instance
  - `series_type`: Filter series by type (e.g., "anime", "standard")
  - `tags`: Filter series by tag IDs (use tag numbers, not names)
- **AniList**: API endpoint for anime metadata
- **Seadex**: Torrent collection URLs
- **Scoring**: Configure how torrents are ranked for selection
  - `is_best_weight`: Points awarded for "best" torrents (default: 2)
  - `dual_audio_weight`: Points awarded for dual audio (default: 1)
  - `tracker_weights`: Points per tracker, can be positive or negative
    - Use "default" key for unknown trackers
    - Example: `{"Nyaa": 0, "AnimeTosho": -2, "default": -10}`
- **qBittorrent**:
  - Connection settings for your torrent client
  - `category`: Automatically assign downloads to a specific category
- **Webhook**: Server settings for real-time updates

## Running the Application

```bash
python main.py
```

This starts the sync loop plus a web server on `webhook.host:webhook.port`
(default `http://localhost:8765`) that serves both the dashboard and the
Sonarr webhook endpoint - it's always running, regardless of whether
`webhook.enabled` is turned on.

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

## Planned

- [x] Move config.py to more persistent location.
- [x] Add a WebUI.
