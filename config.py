"""Configuration for Sonarr and external metadata services"""

# Data directory for persistent cache
DATA_DIR = "data"
SONARR_ANILIST_MAP_FILE = "sonarr_anilist_map.json"
SEEN_TRS_FILE = "seen_trs.json"
KNOWN_SERIES_FILE = "known_series.json"

# Scheduling
SYNC_INTERVAL = 60 * 60 * 24     # 24 hours in seconds

# Sonarr
SONARR_URL = "http://localhost:8989"  # Change to your Sonarr host
SONARR_API_KEY = "your_sonarr_api_key"

# AniList
ANILIST_API_URL = "https://graphql.anilist.co"

# Seadex
COLLECTIONS_URL = "https://releases.moe/api/collections/entries/records"
TORRENT_URL = "https://releases.moe/api/collections/torrents/records"



# qBittorrent
QB_URL = "http://localhost:8080"  # Replace with your actual qBittorrent URL
QB_USER = "admin"  # Replace with your actual username
QB_PASS = "adminadmin"  # Replace with your actual password

# Webhook Server
WEBHOOK_HOST = "localhost"
WEBHOOK_PORT = 8765
USE_WEBHOOK = True  # Set to False to disable webhook and use only scheduled updates
