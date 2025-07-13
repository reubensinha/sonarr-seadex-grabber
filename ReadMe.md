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

   # qBittorrent configuration
   qbittorrent:
     url: "http://your-qbittorrent-host:8080"
     username: "your_username"
     password: "your_password"

   # Webhook Server configuration
   webhook:
     host: "localhost"
     port: 8765
     enabled: true
   ```

### 3. Configuration Options

- **Data Settings**: Configure where cache files are stored
- **Scheduling**: Set how often the sync runs (default: 24 hours)
- **Sonarr**: Your Sonarr instance URL and API key
- **AniList**: API endpoint for anime metadata
- **Seadex**: Torrent collection URLs
- **qBittorrent**: Your torrent client settings
- **Webhook**: Server settings for real-time updates

**Note**: The `config.yaml` file contains sensitive information (API keys, passwords) and should not be committed to version control. A `.gitignore` entry ensures it stays local.

## Running the Application

```bash
python main.py
```

## Planned

- [x] Move config.py to more persistent location.
