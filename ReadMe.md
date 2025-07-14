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

## Planned

- [x] Move config.py to more persistent location.
