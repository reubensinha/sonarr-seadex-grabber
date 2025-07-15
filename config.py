"""Configuration for Sonarr and external metadata services"""

import os
from pathlib import Path
import yaml

# Get the directory where this script is located
_SCRIPT_DIR = Path(__file__).parent


def load_config():
    """Load configuration from config.yaml file"""
    config_file = _SCRIPT_DIR / "config.yaml"

    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_env_or_config(env_var, config_value, default=None):
    """Get value from environment variable first, then config file, then default"""
    env_value = os.getenv(env_var)
    if env_value is not None:
        return env_value
    return config_value if config_value is not None else default


# Load the configuration
_config = load_config()

# General settings
STARTUP_SCAN = get_env_or_config(
    "STARTUP_SCAN", _config["general"].get("startup_scan"), True
)

# Data directory for persistent cache
DATA_DIR = get_env_or_config("DATA_DIR", _config["data"]["dir"], "data")
KNOWN_SERIES_FILE = get_env_or_config(
    "KNOWN_SERIES_FILE", _config["data"]["known_series_file"], "known_series.json"
)

# Scheduling
SYNC_INTERVAL = int(
    get_env_or_config("SYNC_INTERVAL", _config["scheduling"]["sync_interval"], 86400)
)

# Sonarr (sensitive - prefer environment variables)
SONARR_URL = get_env_or_config("SONARR_URL", _config["sonarr"]["url"])
SONARR_API_KEY = get_env_or_config("SONARR_API_KEY", _config["sonarr"]["api_key"])
SONARR_SERIES_TYPE = get_env_or_config(
    "SONARR_SERIES_TYPE", _config["sonarr"]["series_type"], ""
)

# Handle SONARR_TAGS as environment variable (comma-separated) or YAML list
env_tags = os.getenv("SONARR_TAGS")
if env_tags:
    SONARR_TAGS = [tag.strip() for tag in env_tags.split(",") if tag.strip()]
else:
    SONARR_TAGS = _config["sonarr"].get("tags", [])

# AniList
ANILIST_API_URL = get_env_or_config(
    "ANILIST_API_URL", _config["anilist"]["api_url"], "https://graphql.anilist.co"
)

# Seadex
COLLECTIONS_URL = get_env_or_config(
    "COLLECTIONS_URL",
    _config["seadex"]["collections_url"],
    "https://releases.moe/api/collections/entries/records",
)
TORRENT_URL = get_env_or_config(
    "TORRENT_URL",
    _config["seadex"]["torrent_url"],
    "https://releases.moe/api/collections/torrents/records",
)

# Scoring
SCORING_IS_BEST_WEIGHT = int(
    get_env_or_config("SCORING_IS_BEST_WEIGHT", _config["scoring"]["is_best_weight"], 2)
)
SCORING_DUAL_AUDIO_WEIGHT = int(
    get_env_or_config(
        "SCORING_DUAL_AUDIO_WEIGHT", _config["scoring"]["dual_audio_weight"], 1
    )
)
SCORING_TRACKER_WEIGHTS = _config["scoring"][
    "tracker_weights"
]  # Keep as YAML since it's a dict

# qBittorrent (sensitive - prefer environment variables)
QB_URL = get_env_or_config("QB_URL", _config["qbittorrent"]["url"])
QB_USER = get_env_or_config("QB_USER", _config["qbittorrent"]["username"])
QB_PASS = get_env_or_config("QB_PASS", _config["qbittorrent"]["password"])
QB_CATEGORY = get_env_or_config(
    "QB_CATEGORY", _config["qbittorrent"]["category"], "tv-sonarr"
)

# Webhook Server (sensitive - prefer environment variables)
WEBHOOK_HOST = get_env_or_config(
    "WEBHOOK_HOST", _config["webhook"]["host"], "localhost"
)
WEBHOOK_PORT = int(get_env_or_config("WEBHOOK_PORT", _config["webhook"]["port"], 8765))
USE_WEBHOOK = get_env_or_config("USE_WEBHOOK", _config["webhook"]["enabled"], False)
