"""Configuration for Sonarr and external metadata services"""

from pathlib import Path
import yaml

# Get the directory where this script is located
_SCRIPT_DIR = Path(__file__).parent


# Load configuration from YAML file
def load_config():
    """Load configuration from config.yaml file"""
    config_file = _SCRIPT_DIR / "config.yaml"

    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# Load the configuration
_config = load_config()

# Data directory for persistent cache
DATA_DIR = _config["data"]["dir"]
KNOWN_SERIES_FILE = _config["data"]["known_series_file"]

# Scheduling
SYNC_INTERVAL = _config["scheduling"]["sync_interval"]

# Sonarr
SONARR_URL = _config["sonarr"]["url"]
SONARR_API_KEY = _config["sonarr"]["api_key"]
SONARR_SERIES_TYPE = _config["sonarr"]["series_type"]
SONARR_TAGS = _config["sonarr"].get("tags", [])

# AniList
ANILIST_API_URL = _config["anilist"]["api_url"]

# Seadex
COLLECTIONS_URL = _config["seadex"]["collections_url"]
TORRENT_URL = _config["seadex"]["torrent_url"]

# qBittorrent
QB_URL = _config["qbittorrent"]["url"]
QB_USER = _config["qbittorrent"]["username"]
QB_PASS = _config["qbittorrent"]["password"]
QB_CATEGORY = _config["qbittorrent"]["category"]

# Webhook Server
WEBHOOK_HOST = _config["webhook"]["host"]
WEBHOOK_PORT = _config["webhook"]["port"]
USE_WEBHOOK = _config["webhook"]["enabled"]
